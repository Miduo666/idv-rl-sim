# -*- coding: utf-8 -*-
"""模拟器运行环境：sys.path + 缺失模块自动打桩(记录访问/调用)。
用法: import simenv; simenv.setup(); 之后正常 import 游戏模块。"""
import sys, os, io, types, collections, importlib.abc, importlib.machinery

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "std_pyc"))

ACCESS = collections.Counter()     # 属性访问路径 -> 次数
CALLS = collections.Counter()      # 调用路径 -> 次数
CALL_SIG = {}                      # 调用路径 -> 首次调用的参数类型
STUBMODS = collections.Counter()
REAL = {}                          # 模块名 -> 真实替代模块(优先于打桩)
NATIVES = os.path.join(HERE, "natives")   # 原生模块的 Python 替代实现，放在 sys.path 最前
# 与对局无关、导入链又会绕进 game_init 造成循环导入的模块：强制打桩
FORCE_STUB = ("nets", "core.sdk", "core.SDKManager", "game_init")
# 游戏导入时自带 `try: from X import f  except ImportError: <纯 Python 兜底>` 的 Cython 模块：不能打桩（桩"导入成功"会挡掉兜底），
# 要让导入真的失败。CommonUtils.deepcopy_only_builtin_ref_py 打成桩时返回假值 → Buff.__init__ 的 `self.data = deepcopy(...)` 为假
# 提前 return → 所有 Buff 半初始化、效果全不生效（加速/减速等）；AICommonTrigger.scene_datas 等同病（§9.16）。
# 导入方 BuffMgr/AICommonTrigger/AIEnvCombatUtilityNew/ActivityButcherUnit/ActivityCivilianUnit/SunFlare 都有 except → copy.deepcopy；
# SkillModifyManager 只在 SERVER_MODE 分支直接导入（它不在 AI 孤岛里）；game_init 已强制打桩。
FORCE_MISSING = ("common_cs.cython_src.CommonUtils",)


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
    def __call__(self, *a, **kw):
        CALLS[self._p] += 1
        if self._p not in CALL_SIG:
            CALL_SIG[self._p] = ([type(x).__name__ for x in a], sorted(kw))
        return Stub(self._p + "()")
    def __mro_entries__(self, bases):
        nm = self._p.replace(".", "_").replace("()", "")
        return (type(nm, (object,), {"__init__": lambda s, *a, **k: None}),)
    def __iter__(self): return iter(())
    def __bool__(self): return False
    def __len__(self): return 0
    def __getitem__(self, k): return Stub(self._p + "[]")
    def __setitem__(self, k, v): pass
    def __int__(self): return 0
    def __float__(self): return 0.0
    def __index__(self): return 0
    def __hash__(self): return hash(self._p)
    def __eq__(self, o): return self is o
    def __lt__(self, o): return False
    __gt__ = __le__ = __ge__ = __lt__
    def __add__(self, *o): return self
    __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __rtruediv__ = __add__
    __floordiv__ = __rfloordiv__ = __mod__ = __rmod__ = __pow__ = __rpow__ = __add__
    __or__ = __ror__ = __and__ = __rand__ = __xor__ = __rxor__ = __lshift__ = __rshift__ = __add__
    __neg__ = __pos__ = __abs__ = __invert__ = __add__
    __iadd__ = __isub__ = __imul__ = __itruediv__ = __ior__ = __iand__ = __add__
    def __round__(self, n=None): return 0
    def __str__(self): return ""
    def __format__(self, spec): return ""
    def __contains__(self, o): return False
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __repr__(self): return "<Stub %s>" % self._p


class TStub(Stub):
    """真值为 True 的桩：用于"对象存在才继续"的守卫（如 WorldBattleBase.game_tick 的 `if not GK.input: return`）。"""
    def __bool__(self): return True


class StubModule(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__") and k.endswith("__"):
            raise AttributeError(k)
        p = self.__name__ + "." + k
        ACCESS[p] += 1
        return Stub(p)


class StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path, target=None):
        if name in REAL:
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        if name in FORCE_MISSING:
            STUBMODS["<强制缺失>" + name] += 1
            return None
        if any(name == p or name.startswith(p + ".") for p in FORCE_STUB):
            STUBMODS[name] += 1
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
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
        if spec.name in REAL:
            return REAL[spec.name]
        m = StubModule(spec.name)
        m.__path__ = []
        return m

    def exec_module(self, module): pass


_done = False


def setup():
    global _done
    if _done: return
    _done = True
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "cython"))
    sys.path.insert(0, NATIVES)
    sys.dont_write_bytecode = True
    sys.meta_path.insert(0, StubFinder())   # 放最前：FORCE_STUB/REAL 要先于正常查找生效


def report(top=60):
    print("== stub modules (%d):" % len(STUBMODS), " ".join(sorted(STUBMODS)))
    print("== calls (%d distinct):" % len(CALLS))
    for p, n in CALLS.most_common(top):
        print("   %6d  %s  %s" % (n, p, CALL_SIG.get(p, "")))
