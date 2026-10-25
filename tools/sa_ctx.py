import marshal, os, sys, types, dis, io
ROOT = r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\std_pyc"
key = sys.argv[1]; files = sys.argv[2:]
def walk(co):
    yield co
    for c in co.co_consts:
        if isinstance(c, types.CodeType): yield from walk(c)
for rel in files:
    co = marshal.loads(open(os.path.join(ROOT, rel), 'rb').read()[16:])
    for c in walk(co):
        if any(key in n for n in c.co_names):
            s = io.StringIO(); dis.dis(c, file=s, depth=0)
            lines = [l for l in s.getvalue().splitlines() if l.strip() and 'CACHE' not in l and 'PRECALL' not in l]
            idx = [i for i, l in enumerate(lines) if key in l]
            print('==', rel, c.co_qualname)
            shown = set()
            for i in idx:
                for j in range(max(0, i-8), min(len(lines), i+6)):
                    if j not in shown: shown.add(j); print(lines[j])
                print('   ...')
