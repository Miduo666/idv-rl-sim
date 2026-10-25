# -*- coding: utf-8 -*-
"""哪些游戏类继承自被打桩的 Cython 模块；Cython 模块被访问了哪些名字。"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot, simenv
GK = simboot.boot(False)
from ClientUnits.MyButcherUnit import MyButcherUnit
from ClientUnits.CivilianUnit import CivilianUnit
for cls in (MyButcherUnit, CivilianUnit):
    print(cls.__name__, "MRO:", [(c.__name__, c.__module__) for c in cls.__mro__])
cy = {k: v for k, v in simenv.ACCESS.items() if "cython" in k.lower()}
print("cython 访问:", sorted(cy.items(), key=lambda x: -x[1])[:60])
