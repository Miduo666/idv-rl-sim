# -*- coding: utf-8 -*-
"""按字节码还原 pydata TID 模块里的 {key: value}：模拟 LOAD_CONST / BUILD_MAP / BUILD_CONST_KEY_MAP，
不靠相邻常量配对(常量会去重，相邻配对在重复值处会错位)。操作码乱序表用 deobf 的 opcode_names.txt。"""
import os, marshal, opcode

NAMES = open(r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\drivers\opcode_names.txt").read().split()
assert len(NAMES) == 256
CACHE = opcode._inline_cache_entries

def decode(co):
    """返回 (pairs, stats)。pairs = [(k, v), ...]，只收 k、v 都是 str 的。"""
    code, cs = co.co_code, co.co_consts
    stack, pairs = [], []
    i, ext, st = 0, 0, {"maps": 0, "ckmaps": 0, "unknown_ops": set()}
    while i < len(code):
        name = NAMES[code[i]]; arg = code[i + 1] | ext
        op = opcode.opmap.get(name)
        if name == "EXTENDED_ARG":
            ext = arg << 8; i += 2; continue
        ext = 0
        if name == "LOAD_CONST":
            stack.append(cs[arg])
        elif name == "BUILD_MAP":
            n = 2 * arg
            items = stack[-n:] if n else []
            del stack[len(stack) - n:]
            pairs += [(items[j], items[j + 1]) for j in range(0, n, 2)]
            st["maps"] += 1; stack.append(None)
        elif name == "BUILD_CONST_KEY_MAP":
            keys = stack.pop(); vals = stack[-arg:] if arg else []
            del stack[len(stack) - arg:]
            if isinstance(keys, tuple):
                pairs += list(zip(keys, vals))
            st["ckmaps"] += 1; stack.append(None)
        elif op is None:
            st["unknown_ops"].add(name)
        i += 2 + 2 * (CACHE[op] if op is not None and op < len(CACHE) else 0)
    return [(k, v) for k, v in pairs if isinstance(k, str) and isinstance(v, str)], st

KEYRE = __import__("re").compile(r"^[A-Za-z][A-Za-z0-9_]*$")

def decode_refs(co):
    """国际服版：操作码字节多数被置 0，只信操作数。按引用顺序收集 str 常量下标(132=EXTENDED_ARG 前缀)，
    两两配成 (k, v)。去重后的重复值会被再次引用，所以不会错位。返回 (pairs, 坏键数)。"""
    # 语法(实测)：每对 = LOAD k, LOAD v, (0,1)=MAP_ADD 1；(166,1)+缓存 = 合并一段；末段 (95,n) = BUILD_MAP n。
    # const[1] 可能恰好是 str，所以 (0,1) 只有在已攒满 k、v 两个时才当 MAP_ADD。
    # 非 str 的常量也压占位(None)，保证"攒满两个才是 MAP_ADD"的计数不被非字符串值打乱；
    # (166,x) 后面紧跟的 (0,0) 是缓存，跳过。
    b, cs = co.co_code, co.co_consts
    pend, pairs, ext, skip = [], [], 0, False
    for i in range(0, len(b), 2):
        op, arg = b[i], b[i + 1]
        if op == 132:
            ext = (ext | arg) << 8; continue
        val, ext = ext | arg, 0
        if skip:
            skip = False
            if op == 0 and val == 0: continue
        if op == 0:
            if val == 1 and len(pend) >= 2:
                pairs.append((pend[-2], pend[-1])); pend = []
            else:
                pend.append(cs[val] if val < len(cs) else None)
        elif op == 166:
            skip = True
        elif op == 95:   # BUILD_CONST_KEY_MAP n：栈顶是 n 个键的元组，下面 n 个值
            if pend and isinstance(pend[-1], tuple) and len(pend[-1]) == val and len(pend) > val:
                pairs += list(zip(pend[-1], pend[-1 - val:-1])); pend = []
    pairs = [(k, v) for k, v in pairs if isinstance(k, str) and isinstance(v, str)]
    bad = sum(1 for k, _ in pairs if not KEYRE.match(k))
    return pairs, bad, len(pend)

def load_dir(root, lang):
    """base(all_tid_<lang>_N + unusual) 再叠 diff(all_tid_<lang>_diff) 覆盖。"""
    import glob
    m, src, issues = {}, {}, []
    td = os.path.join(root, "pydata", "tid_data")
    for pat in ("all_tid_%s_*.py.marshal", "unusual_all_tid_%s_*.py.marshal"):
        for fp in glob.glob(os.path.join(td, pat % lang)):
            pairs, bad, odd = decode_refs(marshal.loads(open(fp, "rb").read()))
            if bad or odd: issues.append((os.path.basename(fp), bad, odd))
            for k, v in pairs:
                m.setdefault(k, v); src.setdefault(k, "base")
    dp = os.path.join(root, "pydata", "all_tid_%s_diff.py.marshal" % lang)
    if os.path.exists(dp):
        pairs, bad, odd = decode_refs(marshal.loads(open(dp, "rb").read()))
        if bad or odd: issues.append((os.path.basename(dp), bad, odd))
        for k, v in pairs:
            m[k] = v; src[k] = "diff"
    return m, src, issues
