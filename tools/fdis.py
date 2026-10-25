"""在 std_pyc 里按函数名找并反汇编。用法: fdis.py [--files 路径子串] 函数名(qualname 以它结尾即可) [...]"""
import marshal, os, sys, types, dis, io
ROOT = r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\std_pyc"
args = sys.argv[1:]
pf = None
if args and args[0] == '--files':
    pf = args[1]; args = args[2:]
def walk(co):
    yield co
    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            yield from walk(c)
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith('.pyc'): continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
        if pf and pf not in rel: continue
        try:
            co = marshal.loads(open(p, 'rb').read()[16:])
        except Exception:
            continue
        for c in walk(co):
            for a in args:
                if c.co_qualname == a or c.co_qualname.endswith('.' + a):
                    print('=' * 10, rel, c.co_qualname)
                    s = io.StringIO()
                    try:
                        dis.dis(c, file=s, depth=0)
                    except Exception as e:
                        s.write('ERR %r' % e)
                    out = []
                    for line in s.getvalue().splitlines():
                        if ' CACHE' in line or 'RESUME' in line: continue
                        out.append(line)
                    print('\n'.join(out))
