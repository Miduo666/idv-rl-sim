"""打印 bt_code 行为树结构：python bttree.py qaai_civilian_hard [根节点号] [深度]"""
import marshal, sys, types, os, re
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'std_pyc', 'common_cs', 'ai', 'bt_code')
name = sys.argv[1]; root = int(sys.argv[2]) if len(sys.argv) > 2 else None; depth = int(sys.argv[3]) if len(sys.argv) > 3 else 99
co = marshal.loads(open(os.path.join(R, name + '.pyc'), 'rb').read()[16:])
m = types.ModuleType('common_cs'); sys.modules['common_cs'] = m
for n in ['common_cs.ai', 'common_cs.ai.bt', 'common_cs.ai.bt.bt']:
    sys.modules[n] = types.ModuleType(n)
class Any:
    def __getattr__(self, k): return Any()
    def __call__(self, *a, **k): return Any()
sys.modules['common_cs.ai.bt.bt'].bt_consts = Any()
sys.modules['common_cs.ai.bt'].bt = sys.modules['common_cs.ai.bt.bt']
g = {'__name__': 'bt', '__builtins__': __builtins__}
exec(co, g)
funcs = {int(re.match(r'n(\d+)_', k).group(1)): (k, v) for k, v in g.items() if re.match(r'n\d+_', k) and callable(v)}
kids = {}
for k, v in g.items():
    mm = re.match(r'N(\d+)_CHILD_DICT', k)
    if mm: kids[int(mm.group(1))] = v
def consts(fn):
    c = fn.__code__
    return [x for x in c.co_consts if isinstance(x, (int, float, str)) and not isinstance(x, bool) and x not in (None,)][:8]
def show(n, d, seen):
    if n not in funcs or d > depth: return
    k, f = funcs[n]
    print('  ' * d + k, consts(f) if 'CBT' not in k else '')
    if n in seen: return
    seen.add(n)
    ch = kids.get(n)
    if isinstance(ch, dict): ch = [ch[i] for i in sorted(ch)]
    for c in (ch or []):
        cn = c if isinstance(c, int) else (int(re.match(r'n(\d+)_', c.__name__).group(1)) if callable(c) else None)
        if cn is not None: show(cn, d + 1, seen)
if root is None:
    allc = set()
    for v in kids.values():
        for c in (v.values() if isinstance(v, dict) else v):
            if callable(c): allc.add(int(re.match(r'n(\d+)_', c.__name__).group(1)))
            elif isinstance(c, int): allc.add(c)
    roots = [n for n in funcs if n not in allc]
    print('roots', roots[:10])
    root = min(roots)
show(root, 0, set())
