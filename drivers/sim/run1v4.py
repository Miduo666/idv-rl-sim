# -*- coding: utf-8 -*-
"""跑一局 1v4 模拟对局并打印角色轨迹/行为树状态/卡点。用法: run1v4.py [scene_id] [帧数]"""
import sys, os, traceback, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simcore import SimCore

SCENE_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 300

core = SimCore()
import sim1v4
from common_cs.ai import BehaviorTree as BT

BT_CALLS, BT_ERRS = collections.Counter(), collections.Counter()
_bstep = BT.behavior_step


def counted_step(name, owner):
    BT_CALLS[owner.uid] += 1
    try:
        return _bstep(name, owner)
    except Exception:
        k = traceback.format_exc().strip().splitlines()[-1]
        if not BT_ERRS[(owner.uid, k)]:
            print("[bt 异常 uid=%s] %s" % (owner.uid, "".join(traceback.format_exc(limit=-5).splitlines(True)[-10:])))
        BT_ERRS[(owner.uid, k)] += 1
BT.behavior_step = counted_step


def pos(u):
    p = u.get_position3()
    return (round(p.x, 1), round(p.y, 1), round(p.z, 1))


w = sim1v4.make_1v4(core, SCENE_ID)
start = {}


def snap(i):
    if not core.started: return
    if not start:
        start.update({u.uid: pos(u) for u in core.characters()})
    print("  帧 %4d  " % i + "  ".join("%s%d@%s" % (w.roles.get(u.uid, ("?",))[0][0], u.uid, pos(u)) for u in core.characters()))


core.run(FRAMES, every=60, cb=snap)
print("== 单位按类别:", collections.Counter(type(u).__name__ for u in w.unit_mgr.units.values()).most_common())
print("== 角色:")
for u in core.characters():
    role, pid, bt = w.roles.get(u.uid, ("?", None, None))
    print("   uid=%-3s %-8s pid=%-3s %-22s ai=%-16s bt=%-20s 步数=%-4d %s -> %s" % (
        u.uid, role, pid, type(u).__name__, type(u.ai_controller).__name__, bt, BT_CALLS[u.uid], start.get(u.uid), pos(u)))
if BT_ERRS:
    print("== 行为树异常:", [(k, n) for k, n in BT_ERRS.most_common(8)])
core.report()
