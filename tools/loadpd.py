import sys, types, marshal, os
ROOT = r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\std_pyc"
def _stub():
    td = types.ModuleType('taggeddict'); td.taggeddict = lambda *a, **k: (a[0] if a else dict(k)); sys.modules['taggeddict'] = td
    core = types.ModuleType('core'); fc = types.ModuleType('core.fcpopt')
    class OptDict(dict):
        def __init__(self, *a, **k):
            super().__init__(*(a[:1]) if a and isinstance(a[0], dict) else (), **k)
            self.args = a
    fc.OptDict = OptDict; core.fcpopt = fc
    sys.modules['core'] = core; sys.modules['core.fcpopt'] = fc
_stub()
def load(name):
    co = marshal.loads(open(os.path.join(ROOT, 'pydata', name + '.pyc'), 'rb').read()[16:])
    g = {'__name__': 'pydata.' + name, '__builtins__': __builtins__}
    exec(co, g)
    return g
if __name__ == '__main__':
    g = load(sys.argv[1])
    for k, v in g.items():
        if k.startswith('__'): continue
        r = repr(v)
        print(k, type(v).__name__, (len(v) if hasattr(v, '__len__') else ''), r[:600])
