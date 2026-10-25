# -*- coding: utf-8 -*-
"""3.11 字节码 -> 伪源码（栈模拟折叠表达式，跳转写成 goto）。比 dis 好读，不是真反编译。
用法: python pseudo.py <std_pyc 下相对路径> [qualname 正则]"""
import sys, os, re, dis, marshal, opcode

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "std_pyc"))
CMP = {"POP_JUMP_FORWARD_IF_FALSE": "if not %s", "POP_JUMP_BACKWARD_IF_FALSE": "if not %s",
       "POP_JUMP_FORWARD_IF_TRUE": "if %s", "POP_JUMP_BACKWARD_IF_TRUE": "if %s",
       "POP_JUMP_FORWARD_IF_NONE": "if %s is None", "POP_JUMP_BACKWARD_IF_NONE": "if %s is None",
       "POP_JUMP_FORWARD_IF_NOT_NONE": "if %s is not None", "POP_JUMP_BACKWARD_IF_NOT_NONE": "if %s is not None"}


def r(v):
    return v if isinstance(v, str) else repr(v)


def func(co, out, ind=""):
    args = co.co_varnames[:co.co_argcount + co.co_kwonlyargcount]
    out.append("%sdef %s(%s):" % (ind, co.co_qualname, ", ".join(args)))
    ind2 = ind + "    "
    ins = list(dis.get_instructions(co))
    targets = {i.argval for i in ins if i.opcode in opcode.hasjrel or i.opcode in opcode.hasjabs}
    st, kw, line = [], None, None

    def emit(s):
        out.append("%s%-5s %s" % (ind2, line or "", s))

    def pop(n=1):
        if n == 0: return []
        v = st[-n:] if len(st) >= n else ["?"] * (n - len(st)) + st[:]
        del st[-n:]
        return v

    for i in ins:
        if i.positions and i.positions.lineno: line = i.positions.lineno
        if i.offset in targets:
            if st: emit("# stack: %s" % ", ".join(map(str, st))[:200])
            out.append("%sL%d:" % (ind2, i.offset))
        op, a = i.opname, i.argval
        if op in ("RESUME", "NOP", "PRECALL", "CACHE", "EXTENDED_ARG", "COPY_FREE_VARS", "MAKE_CELL", "RETURN_GENERATOR"):
            continue
        if op in ("LOAD_FAST", "LOAD_NAME", "LOAD_DEREF", "LOAD_CLOSURE", "LOAD_CLASSDEREF"): st.append(a)
        elif op == "LOAD_GLOBAL":
            if i.arg & 1: st.append(None)
            st.append(a)
        elif op == "LOAD_CONST":
            st.append("<code %s>" % a.co_qualname if hasattr(a, "co_code") else repr(a))
        elif op == "PUSH_NULL": st.append(None)
        elif op == "LOAD_ATTR": st.append("%s.%s" % (r(pop()[0]), a))
        elif op == "LOAD_METHOD":
            o = pop()[0]; st.append(None); st.append("%s.%s" % (r(o), a))
        elif op == "KW_NAMES": kw = co.co_consts[i.arg]
        elif op == "CALL":
            av = pop(i.arg); f = pop(2)
            fn = f[1] if f[1] is not None else f[0]
            if f[0] is not None and f[1] is not None: av = [f[1]] + av; fn = f[0]
            pos = av[:len(av) - len(kw or ())]
            parts = [r(x) for x in pos] + ["%s=%s" % (k, r(v)) for k, v in zip(kw or (), av[len(pos):])]
            kw = None
            st.append("%s(%s)" % (r(fn), ", ".join(parts)))
        elif op == "CALL_FUNCTION_EX":
            kwa = pop()[0] if i.arg & 1 else None
            ar, f = pop(), pop()
            if st and st[-1] is None: st.pop()
            st.append("%s(*%s%s)" % (r(f[0]), r(ar[0]), ", **%s" % r(kwa) if kwa else ""))
        elif op == "BINARY_OP":
            b, c = pop(2); st.append("(%s %s %s)" % (r(b), i.argrepr, r(c)))
        elif op in ("COMPARE_OP",):
            b, c = pop(2); st.append("(%s %s %s)" % (r(b), a, r(c)))
        elif op == "IS_OP":
            b, c = pop(2); st.append("(%s is%s %s)" % (r(b), " not" if i.arg else "", r(c)))
        elif op == "CONTAINS_OP":
            b, c = pop(2); st.append("(%s %sin %s)" % (r(b), "not " if i.arg else "", r(c)))
        elif op == "BINARY_SUBSCR":
            b, c = pop(2); st.append("%s[%s]" % (r(b), r(c)))
        elif op == "BUILD_SLICE":
            v = pop(i.arg); st.append(":".join("" if x == "None" else r(x) for x in v))
        elif op == "UNARY_NOT": st.append("(not %s)" % r(pop()[0]))
        elif op == "UNARY_NEGATIVE": st.append("(-%s)" % r(pop()[0]))
        elif op == "UNARY_INVERT": st.append("(~%s)" % r(pop()[0]))
        elif op in ("BUILD_LIST", "BUILD_TUPLE", "BUILD_SET"):
            v = pop(i.arg); b = {"BUILD_LIST": "[%s]", "BUILD_TUPLE": "(%s)", "BUILD_SET": "{%s}"}[op]
            st.append(b % ", ".join(map(r, v)))
        elif op == "BUILD_MAP":
            v = pop(2 * i.arg); st.append("{%s}" % ", ".join("%s: %s" % (r(v[k]), r(v[k + 1])) for k in range(0, len(v), 2)))
        elif op == "BUILD_CONST_KEY_MAP":
            ks = eval(pop()[0]); v = pop(i.arg); st.append("{%s}" % ", ".join("%r: %s" % (k, r(x)) for k, x in zip(ks, v)))
        elif op == "BUILD_STRING": st.append("+".join(map(r, pop(i.arg))))
        elif op == "FORMAT_VALUE":
            if (i.arg & 4): pop()
            st.append("str(%s)" % r(pop()[0]))
        elif op in ("LIST_EXTEND", "SET_UPDATE", "DICT_UPDATE", "DICT_MERGE"):
            v = pop()[0]; st[-1] = "%s+%s" % (r(st[-1]), r(v))
        elif op in ("LIST_APPEND", "SET_ADD"):
            v = pop()[0]; emit("<append %s>" % r(v))
        elif op == "MAP_ADD":
            pop(2)
        elif op == "LIST_TO_TUPLE": pass
        elif op in ("STORE_FAST", "STORE_NAME", "STORE_GLOBAL", "STORE_DEREF"):
            emit("%s = %s" % (a, r(pop()[0])))
        elif op == "STORE_ATTR":
            o, v = pop(), pop(); emit("%s.%s = %s" % (r(o[0]), a, r(v[0])))
        elif op == "STORE_SUBSCR":
            k, o, v = pop(), pop(), pop(); emit("%s[%s] = %s" % (r(o[0]), r(k[0]), r(v[0])))
        elif op == "DELETE_SUBSCR":
            k, o = pop(), pop(); emit("del %s[%s]" % (r(o[0]), r(k[0])))
        elif op in ("DELETE_FAST", "DELETE_NAME", "DELETE_ATTR"):
            if op == "DELETE_ATTR": emit("del %s.%s" % (r(pop()[0]), a))
            else: emit("del %s" % a)
        elif op == "POP_TOP":
            v = pop()[0]
            if v is not None and not str(v).startswith("<iter"): emit(r(v))
        elif op == "RETURN_VALUE": emit("return %s" % r(pop()[0]))
        elif op in CMP: emit("%s: goto L%d" % (CMP[op] % r(pop()[0]), a))
        elif op in ("JUMP_IF_TRUE_OR_POP", "JUMP_IF_FALSE_OR_POP"):
            v = st[-1] if st else "?"; emit("%s: goto L%d   # keep value" % (("if %s" if "TRUE" in op else "if not %s") % r(v), a)); pop()
        elif op in ("JUMP_FORWARD", "JUMP_BACKWARD", "JUMP_BACKWARD_NO_INTERRUPT"): emit("goto L%d" % a)
        elif op == "GET_ITER": st.append("<iter %s>" % r(pop()[0]))
        elif op == "FOR_ITER":
            it = st[-1]; st.append("<item of %s>" % it[6:-1] if str(it).startswith("<iter") else "<item>")
            emit("for-next %s else goto L%d" % (it, a))
        elif op == "UNPACK_SEQUENCE":
            v = pop()[0]; st.extend("%s[%d]" % (r(v), k) for k in reversed(range(i.arg)))
        elif op == "MAKE_FUNCTION":
            c = pop()[0]
            for bit in (8, 4, 2, 1):
                if i.arg & bit: pop()
            st.append("<func %s>" % c[6:-1])
        elif op == "IMPORT_NAME":
            pop(2); st.append("import(%s)" % a)
        elif op == "IMPORT_FROM": st.append("%s.%s" % (r(st[-1]), a))
        elif op == "COPY": st.append(st[-i.arg] if len(st) >= i.arg else "?")
        elif op == "SWAP":
            if len(st) >= i.arg: st[-1], st[-i.arg] = st[-i.arg], st[-1]
        elif op == "RAISE_VARARGS": emit("raise %s" % ", ".join(map(r, pop(i.arg))))
        elif op == "LOAD_ASSERTION_ERROR": st.append("AssertionError")
        elif op == "LOAD_BUILD_CLASS": st.append("__build_class__")
        elif op in ("PUSH_EXC_INFO",): st.append("<exc>")
        elif op in ("POP_EXCEPT", "RERAISE", "CHECK_EXC_MATCH", "BEFORE_WITH", "WITH_EXCEPT_START"):
            emit("<%s>" % op)
            if op == "CHECK_EXC_MATCH": st.append("<exc match %s>" % r(pop()[0]))
            if op == "BEFORE_WITH": st.append("<with>")
        elif op in ("YIELD_VALUE",): emit("yield %s" % r(pop()[0])); st.append("<sent>")
        else:
            emit("<%s %s>" % (op, i.argrepr))
    out.append("")
    for k in co.co_consts:
        if hasattr(k, "co_code"): func(k, out, ind)


def find(c, pat):
    res = []
    if pat.search(c.co_qualname): res.append(c)
    else:
        for k in c.co_consts:
            if hasattr(k, "co_code"): res += find(k, pat)
    return res


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    co = marshal.loads(open(os.path.join(ROOT, sys.argv[1]), "rb").read()[16:])
    cs = find(co, re.compile(sys.argv[2])) if len(sys.argv) > 2 else [co]
    out = []
    for c in cs: func(c, out)
    print("\n".join(out))
