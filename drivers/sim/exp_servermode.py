# -*- coding: utf-8 -*-
"""实验：只让 common_cs.ai.* 模块看到 SERVER_MODE=True，统计会冒出多少种新错误。占位值仅用于实验。
用法: python exp_servermode.py <sim目录> [帧数] [on|off]"""
import sys, os, types, collections, traceback
SIM = sys.argv[1]
FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 300
ON = (sys.argv[3] if len(sys.argv) > 3 else "on") == "on"
sys.path.insert(0, SIM)
from simcore import SimCore
core = SimCore(verbose=False)
from etc import dev_config
import simenv, game_kernel, importlib, pkgutil

if ON:
    # servercommon.Netease -> GK（服务端模式下模块导入时 `from servercommon import Netease`）
    sc = types.ModuleType("servercommon"); sc.Netease = game_kernel; sc.__path__ = []
    simenv.REAL["servercommon"] = sc
    for m in [m for m in sys.modules if m.startswith("common_cs.ai")]:
        del sys.modules[m]
    dev_config.SERVER_MODE = True
    root = os.path.join(simenv.ROOT, "common_cs", "ai")
    ok = bad = 0
    BAD = collections.Counter()
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if f.endswith(".pyc") and "bt_code" not in dp:
                rel = os.path.relpath(os.path.join(dp, f), simenv.ROOT)[:-4].replace(os.sep, ".")
                if rel.endswith(".__init__"): rel = rel[:-9]
                try:
                    importlib.import_module(rel); ok += 1
                except Exception as e:
                    bad += 1; BAD[type(e).__name__ + ": " + str(e)[:100]] += 1
    dev_config.SERVER_MODE = False
    print("服务端模式导入 AI 模块: 成功 %d 失败 %d" % (ok, bad), BAD.most_common(8))
import sim1v4
from common_cs.ai import BehaviorTree as BT

ERR = collections.Counter()
FIRST = {}
_b = BT.behavior_step


def step(name, owner):
    try:
        return _b(name, owner)
    except Exception:
        tb = traceback.format_exc()
        k = tb.strip().splitlines()[-1]
        ERR[k] += 1
        FIRST.setdefault(k, "".join(traceback.format_exc(limit=-3).splitlines(True)[-6:]))
BT.behavior_step = step

if ON:
    proxy = types.SimpleNamespace(**{k: getattr(dev_config, k) for k in dir(dev_config) if not k.startswith("__")})
    proxy.SERVER_MODE = True
    n = 0
    for name, m in list(sys.modules.items()):
        if name.startswith("common_cs.ai") and getattr(m, "dev_config", None) is not None:
            m.dev_config = proxy; n += 1
    print("SERVER_MODE 代理注入模块数:", n)

# 实验用占位（不是推断出的真值）
import common_cs.ai.AICivilian as AC
from common_cs.ai.HidingCirCleUtils import MathUtils
AC.MathUtils = MathUtils


def on_start(w):
    for g in w.unit_mgr.get_generator_units():
        p = g.get_position3()
        g.ai_fix_angle = [0, 1, 2, 3]
        g.ai_fix_pos = {i: p for i in range(4)}
    for u in core.characters():
        if not hasattr(u, "punish_start_timestamp"): u.punish_start_timestamp = 0
core.on_start.insert(0, on_start)
w = sim1v4.make_1v4(core, 1)
core.run(FRAMES)
import simpatch
for k, v in list(simpatch.SWALLOWED.items()):
    ERR["[吞] " + k] += v
print("== %s：行为树/吞异常 %d 种" % ("开代理" if ON else "不开代理", len(ERR)))
for k, n in ERR.most_common(40):
    print("  %5d  %s" % (n, k[:170]))
    if k in FIRST: print("         " + FIRST[k].strip().replace("\n", "\n         ")[:600])
print("tick 异常:", [(k[:150], n) for k, n in core.tick_errors.most_common(10)])
import traceback as _tb
w = core.world
try:
    w.tick()
except Exception:
    print(_tb.format_exc(limit=-6))
