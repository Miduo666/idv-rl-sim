# -*- coding: utf-8 -*-
"""策略评估：跑到第一个求生者倒地（FALL）为止，输出"首次击倒用时"一行 JSON。
用法: SIM_JACK=master|nightmare python first_down.py [种子=0] [上限秒=240]
同时记击倒前：杰克被板砸(进入 HIT_BY_PANEL)次数、雾刃生成数（新 AIRPOWER 单位）、杰克普攻次数（进入 SKILL_ATTACK）。
状态按"本帧有、上一帧没有"计一次进入。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simcore
simcore.ensure_hashseed()
from simcore import SimCore

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
SEED = int(ARGS[0]) if len(ARGS) > 0 else 0
MAX_S = float(ARGS[1]) if len(ARGS) > 1 else 240.0
core = SimCore(server_ai=True, seed=SEED)
import sim1v4
from common_cs import ComuKeys
from common_cs.states.StatesConst import CIVILIAN_STATE, BUTCHER_STATE
w = sim1v4.make_1v4(core)
t0 = core.real_time()


def has(u, st):
    try:
        return bool(u.state_machine.has_state_ex(st))
    except Exception:
        return False


prev = {"stun": False, "atk": False}
counts = {"stun": 0, "atk": 0, "fog": 0}
seen_fog = set()
result = None
max_frames = int(MAX_S * 1000.0 / simcore.DT_MS)
for f in range(max_frames):
    core.frame()
    if not core.started:
        continue
    jack = w.unit_mgr.get_unit(1)
    if jack is None:
        continue
    for k, st in (("stun", BUTCHER_STATE.HIT_BY_PANEL), ("atk", BUTCHER_STATE.SKILL_ATTACK)):
        now = has(jack, st)
        if now and not prev[k]:
            counts[k] += 1
        prev[k] = now
    for ap in w.unit_mgr.get_units_by_type(ComuKeys.UNIT_TYPE_CONF.AIRPOWER) or ():
        if ap.uid not in seen_fog:
            seen_fog.add(ap.uid)
            counts["fog"] += 1
    down = [u.uid for u in core.characters() if u.uid != 1 and has(u, CIVILIAN_STATE.FALL)]
    if down:
        result = (f + 1) * simcore.DT_MS / 1000.0
        break

ac = w.unit_mgr.get_unit(1).ai_controller
lc = getattr(ac, "level_control", {}) or {}
out = {"jack": os.environ.get("SIM_JACK", "nightmare"), "seed": SEED, "first_down_s": result,
       "victim": down[0] if result else None, "stuns": counts["stun"], "attacks": counts["atk"], "fogs": counts["fog"],
       "controller": type(ac).__name__, "but_level": getattr(ac, "but_level", None),
       "fog_params": {k: lc.get(k) for k in ("fog_ex", "fog_cd", "fog_miss_prob", "fog_dis_min", "fog_dis_max", "is_in_panel")} if lc else None,
       "tick_errors": sum(core.tick_errors.values()),
       "swallowed": {k.strip().splitlines()[-1][:120]: n for k, n in core.simpatch.SWALLOWED.most_common(6)},
       "wall_s": round(core.real_time() - t0, 1)}
print("RESULT " + json.dumps(out, ensure_ascii=False), flush=True)
