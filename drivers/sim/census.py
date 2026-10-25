# -*- coding: utf-8 -*-
"""依赖摸底：缺失模块一律自动打桩并记录访问路径，然后导入目标包下的全部模块。"""
import sys, io, os, importlib, importlib.abc, importlib.machinery, types, collections, json, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = sys.argv[1]
PKGS = sys.argv[2].split(",")
OUT = sys.argv[3]
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "cython"))   # 游戏把 cython 目录放进 sys.path，import cython 得到 cython/cython.pyc
sys.dont_write_bytecode = True

ACCESS = collections.Counter()      # "math3d.vector" -> 次数
STUBMODS = collections.Counter()    # 被打桩的模块名 -> 首次被谁导入的次数


class Stub:
    def __init__(self, path):
        object.__setattr__(self, "_p", path)

    def __getattr__(self, k):
        if k.startswith("__") and k.endswith("__"):
            raise AttributeError(k)
        p = self._p + "." + k
        ACCESS[p] += 1
        return Stub(p)

    def __setattr__(self, k, v): pass
    def __call__(self, *a, **kw): return Stub(self._p + "()")
    def __mro_entries__(self, bases): return (type(self._p.replace(".", "_").replace("()", ""), (object,), {}),)
    def __iter__(self): return iter(())
    def __bool__(self): return False
    def __len__(self): return 0
    def __getitem__(self, k): return Stub(self._p + "[]")
    def __int__(self): return 0
    def __float__(self): return 0.0
    def __index__(self): return 0
    def __hash__(self): return hash(self._p)
    def __eq__(self, o): return self is o
    def __lt__(self, o): return False
    __gt__ = __le__ = __ge__ = __lt__
    def __add__(self, o): return self
    __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __or__ = __ror__ = __and__ = __add__
    def __contains__(self, o): return False
    def __enter__(self): return self
    def __exit__(self, *a): return False


class StubModule(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__") and k.endswith("__"):
            raise AttributeError(k)
        p = self.__name__ + "." + k
        ACCESS[p] += 1
        return Stub(p)


class StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path, target=None):
        # 只在正常路径都找不到时才接手
        for f in sys.meta_path:
            if f is self: continue
            try:
                if f.find_spec(name, path, target) is not None:
                    return None
            except Exception:
                pass
        STUBMODS[name] += 1
        return importlib.machinery.ModuleSpec(name, self, is_package=True)

    def create_module(self, spec):
        m = StubModule(spec.name)
        m.__path__ = []
        return m

    def exec_module(self, module): pass


sys.meta_path.append(StubFinder())

mods = []
for pkg in PKGS:
    base = os.path.join(ROOT, *pkg.split("."))
    for dp, _, fs in os.walk(base):
        for fn in fs:
            if not fn.endswith(".pyc"): continue
            rel = os.path.relpath(os.path.join(dp, fn), ROOT)[:-4].replace(os.sep, ".")
            if rel.endswith(".__init__"): rel = rel[:-9]
            mods.append(rel)
mods.sort()
ok = 0
fails = collections.Counter()
fail_examples = {}
for m in mods:
    try:
        importlib.import_module(m)
        ok += 1
    except BaseException as e:
        key = "%s: %s" % (type(e).__name__, str(e)[:100])
        fails[key] += 1
        fail_examples.setdefault(key, m)

res = {"total": len(mods), "ok": ok,
       "stub_modules": STUBMODS.most_common(),
       "access": ACCESS.most_common(),
       "fails": [(k, n, fail_examples[k]) for k, n in fails.most_common()]}
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("total", len(mods), "ok", ok)
print("stub modules:", len(STUBMODS))
for k, n in STUBMODS.most_common(40): print("   %5d %s" % (n, k))
print("fail kinds:", len(fails))
for k, n in fails.most_common(15): print("   %5d %s  e.g. %s" % (n, k, fail_examples[k]))
