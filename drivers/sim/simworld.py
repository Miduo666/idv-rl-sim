# -*- coding: utf-8 -*-
"""第 2 步试验台：无引擎环境里实例化本地对局世界，逐步推进生命周期，记录运行期依赖。"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot, simenv

GK = simboot.boot()

# GK 上没被游戏启动流程赋值的 g_* 全局对象 -> 记录型桩
filled = []
for k in dir(GK):
    if not k.startswith("__") and getattr(GK, k) is None:
        setattr(GK, k, simenv.Stub("GK." + k))
        filled.append(k)
print("[world] GK 全局打桩 %d 个" % len(filled))


def step(name, fn):
    try:
        r = fn()
        print("[ok]   %s" % name)
        return r
    except BaseException:
        print("[FAIL] %s" % name)
        traceback.print_exc(limit=-6, file=sys.stdout)
        raise SystemExit(1)


from common_cs import ComuKeys
wt = ComuKeys.GAME_WORLD_TYPE.NOVICE_BATTLE
print("[world] NOVICE_BATTLE =", wt)
from worlds.WorldBattleClientNovice import WorldBattleClientNovice
w = step("WorldBattleClientNovice()", WorldBattleClientNovice)
simenv.report(40)
