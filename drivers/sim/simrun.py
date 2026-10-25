# -*- coding: utf-8 -*-
"""新手局(WorldBattleClientNovice)诊断：无引擎跑生命周期，打印卡点。1v4 对局见 run1v4.py。
用法: simrun.py [scene_id] [帧数]   环境变量 SIM_PID 指定自己的角色(默认 1=厂长)"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simcore import SimCore

SCENE_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 60

core = SimCore()
from worlds.WorldBattleClientNovice import WorldBattleClientNovice
w = core.make_world(WorldBattleClientNovice, SCENE_ID, int(os.environ.get("SIM_PID", "1")))


def frame_log(i):
    print("  frame %d  loading_finish=%s init_done=%s units=%d" % (
        i, getattr(w, "is_loading_finish", None), getattr(w, "is_init_done", None), len(w.unit_mgr.units)))


core.run(FRAMES, every=20, cb=frame_log)
print("== 世界状态: tick=%s is_scene_ok=%s is_loading_ok=%s is_loading_finish=%s" % (
    getattr(w.tick, "__name__", w.tick), w.is_scene_ok, w.is_loading_ok, w.is_loading_finish))
print("== 单位按类别:", collections.Counter(type(u).__name__ for u in w.unit_mgr.units.values()).most_common())
core.report()
