# -*- coding: utf-8 -*-
"""跑一整局 1v4（服务端模式 AI 孤岛），每段打印密码机进度与求生者状态，所有求生者离场(is_leave)或到上限即停。
用法: python run_full.py [最多帧=18000] [每段帧=900] [种子=0]
结束判定同 WorldBattleClientBase.check_game_over（监管为"自己"时：所有求生者 is_leave）。"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simcore
simcore.ensure_hashseed()
from simcore import SimCore

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
MAXF = int(ARGS[0]) if len(ARGS) > 0 else 18000
SEG = int(ARGS[1]) if len(ARGS) > 1 else 900
SEED = int(ARGS[2]) if len(ARGS) > 2 else 0
core = SimCore(verbose="--verbose" in sys.argv, server_ai=True, seed=SEED)   # --verbose：打印每种被吞异常第一次的调用栈
import sim1v4
from common_cs.states.StatesConst import CIVILIAN_STATE
w = sim1v4.make_1v4(core)
t0 = core.real_time()


def civ_state(u):
    sm = u.state_machine
    tags = []
    for name in ("HANG", "HANGING", "FALL", "CARRY", "CATCHED", "STRUGGLE_DROP", "HURT", "FIX"):
        st = getattr(CIVILIAN_STATE, name, None)
        try:
            if st is not None and sm.has_state_ex(st):
                tags.append(name)
        except Exception:
            pass
    return "%s%s%s" % ("离场" if getattr(u, "is_leave", False) else "在场", "/" + ",".join(tags) if tags else "",
                       " 挂椅%s" % u.hook_uid if getattr(u, "hook_uid", None) else "")


done = 0
civ_uids = []   # 开局后才有角色：第一段跑完再记
fate = {}       # uid -> (结局, 模拟秒)：淘汰后单位从单位表移除；逃生者 is_leave
while done < MAXF:
    core.run(SEG)
    done += SEG
    now = done * simcore.DT_MS / 1000.0
    if not civ_uids:
        civ_uids = [u.uid for u in core.characters() if u.uid != 1]
    gens = [round(g.get_cur_process_nosync(), 1) for g in w.unit_mgr.get_generator_units()]
    civs = [u for u in core.characters() if u.uid != 1]
    alive = {u.uid for u in civs}
    for uid in civ_uids:
        if uid in fate:
            continue
        if uid not in alive:
            fate[uid] = ("淘汰/移除", now)
        elif getattr(w.unit_mgr.get_unit(uid), "is_leave", False):
            fate[uid] = ("离场(逃生)", now)
    print("[%5.0fs 模拟 %6.1fs] 机 %s 合计 %.0f | %s" % (core.real_time() - t0, now, gens, sum(gens),
          " | ".join("c%d %s" % (u.uid, civ_state(u)) for u in civs) or "（无在场求生者）"), flush=True)
    if len(fate) == len(civ_uids):
        print("== 对局结束（模拟 %.0f 秒）：%s" % (now, "  ".join("c%d %s@%.0fs" % (k, v[0], v[1]) for k, v in sorted(fate.items()))), flush=True)
        break
else:
    print("== 到上限 %d 帧仍未结束；已有结局: %s" % (MAXF, fate))
core.report(top=10)
print("== 服务端垫片统计:", dict(sim1v4.SHIM_STATS))
