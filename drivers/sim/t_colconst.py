# -*- coding: utf-8 -*-
"""打印碰撞适配要用的真实常量（运行期导入，不靠伪源码）：过滤模式、Layer/Group/形状常量、Filter/RoleFilter 的默认参数与实例属性、
运行期见过的单位类型编号对应的名字。用法: python t_colconst.py [额外的单位类型编号 ...]"""
import sys, os, inspect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot

simboot.boot(verbose=False)
from common_cs import CollisionConst as CC


def consts(obj):
    return {k: v for k, v in sorted(vars(obj).items()) if not k.startswith("_") and isinstance(v, (int, float, str, tuple, frozenset, set))}


def show(title, f):
    try:
        print("== %s:" % title, f())
    except Exception as e:
        print("== %s: <%s: %s>" % (title, type(e).__name__, e))


show("模块级常量", lambda: consts(CC))
for name in ("Layer", "Group", "FaceFilter", "Shape"):
    if hasattr(CC, name):
        show(name, lambda name=name: consts(getattr(CC, name)))
show("类", lambda: sorted(k for k, v in vars(CC).items() if inspect.isclass(v)))
for name in ("Filter", "RoleFilter"):
    show("%s 签名" % name, lambda name=name: str(inspect.signature(getattr(CC, name).__init__)))
    show("%s() 实例属性" % name, lambda name=name: {k: v for k, v in sorted(vars(getattr(CC, name)()).items())})
    show("%s 方法" % name, lambda name=name: sorted(k for k in dir(getattr(CC, name)) if not k.startswith("__")))

from common_cs import ComuKeys
UT = ComuKeys.UNIT_TYPE_CONF
names = {}
for k in dir(UT):
    v = getattr(UT, k)
    if not k.startswith("_") and isinstance(v, int):
        names.setdefault(v, []).append(k)
want = [1, 2, 146] + [int(x) for x in sys.argv[1:]]
print("== UNIT_TYPE_CONF 编号 → 名字:", {v: names.get(v) for v in want})
print("== UNIT_TYPE_CONF 共 %d 个编号" % len(names))
