import marshal, sys, types, os

ROOT = r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\all_pyc"


def load(rel):
    p = os.path.join(ROOT, rel.replace('/', os.sep))
    if p.endswith('.py'):
        p = p[:-3] + '.pyc'
    with open(p, 'rb') as f:
        data = f.read()
    return marshal.loads(data[16:])


def walk(co, depth=0, out=None):
    ind = '  ' * depth
    names = list(co.co_names)
    consts = [c for c in co.co_consts if isinstance(c, (str, int, float, tuple)) and not isinstance(c, bool)]
    print(f"{ind}[{co.co_qualname}] names={names}")
    if consts:
        print(f"{ind}    consts={consts}")
    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            walk(c, depth + 1)


if __name__ == '__main__':
    for rel in sys.argv[1:]:
        print('=' * 20, rel)
        try:
            walk(load(rel))
        except Exception as e:
            print('ERR', e)
