"""紧凑反汇编: 每个源码行一行，指令压成短记号。用法: cdis.py 相对路径子串 函数名[,函数名...]"""
import marshal, os, sys, types, dis

ROOT = r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\std_pyc"
SHORT = {
    'LOAD_FAST': '', 'LOAD_CONST': '', 'LOAD_GLOBAL': '', 'LOAD_NAME': '', 'LOAD_DEREF': '',
    'LOAD_ATTR': '.', 'LOAD_METHOD': '.', 'STORE_FAST': '=>', 'STORE_ATTR': '=>.', 'STORE_NAME': '=>',
    'STORE_DEREF': '=>', 'STORE_SUBSCR': '=>[]', 'BINARY_SUBSCR': '[]', 'COMPARE_OP': '', 'BINARY_OP': '',
    'CALL': 'call', 'RETURN_VALUE': 'return', 'POP_TOP': ';', 'IS_OP': 'is', 'CONTAINS_OP': 'in',
}
SKIP = {'CACHE', 'RESUME', 'PRECALL', 'PUSH_NULL', 'NOP', 'KW_NAMES', 'COPY_FREE_VARS', 'MAKE_CELL'}


def walk(co):
    yield co
    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            yield from walk(c)


def fmt(ins):
    op = ins.opname
    if op in SKIP:
        return None
    if op.startswith('POP_JUMP') or op.startswith('JUMP'):
        return f'{op.replace("POP_JUMP_","PJ_").replace("FORWARD_","F_").replace("BACKWARD_","B_")}->{ins.argval}'
    if op == 'CALL':
        return f'call{ins.arg}'
    if op in SHORT:
        p = SHORT[op]
        a = ins.argrepr if op not in ('LOAD_CONST',) else repr(ins.argval)
        if op == 'IS_OP':
            return 'is not' if ins.arg else 'is'
        if op == 'CONTAINS_OP':
            return 'not in' if ins.arg else 'in'
        if op in ('CALL', 'RETURN_VALUE', 'POP_TOP', 'BINARY_SUBSCR', 'STORE_SUBSCR'):
            return p
        return f'{p}{a}'
    return f'{op}({ins.argrepr})' if ins.argrepr else op


def show(co):
    print('=' * 8, co.co_qualname, 'args=', co.co_varnames[:co.co_argcount])
    line = None; buf = []; off0 = 0
    for ins in dis.get_instructions(co):
        ln = ins.positions.lineno if ins.positions else None
        if ins.starts_line is not None and ins.starts_line != line:
            if buf:
                print(f'{line:5} @{off0:<5} ' + ' '.join(buf))
            line = ins.starts_line; buf = []; off0 = ins.offset
        if ins.is_jump_target and buf:
            buf.append(f'[{ins.offset}:]')
        t = fmt(ins)
        if t:
            buf.append(t)
    if buf:
        print(f'{line:5} @{off0:<5} ' + ' '.join(buf))


pf = sys.argv[1]
names = sys.argv[2].split(',')
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith('.pyc'):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
        if pf not in rel:
            continue
        co = marshal.loads(open(p, 'rb').read()[16:])
        for c in walk(co):
            if any(c.co_qualname == n or c.co_qualname.endswith('.' + n) for n in names):
                print('#', rel)
                show(c)
