# -*- coding: utf-8 -*-
"""录一整局的逐帧快照（给 render_game.py 出视频）。用法: python record_game.py [种子=0] [每几帧记一次=2] [最多帧=18000] [输出]
输出 JSON 行：第一行 header（场景/角色名/静态物件），之后每行一帧 {t, chars, gens, panels, hooks, doors}。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simcore
simcore.ensure_hashseed()
from simcore import SimCore

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 0
EVERY = int(sys.argv[2]) if len(sys.argv) > 2 else 2
MAXF = int(sys.argv[3]) if len(sys.argv) > 3 else 18000
OUT = sys.argv[4] if len(sys.argv) > 4 else os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                                                         "res_pull", "replay_sim", "seed%d.jsonl" % SEED))
os.makedirs(os.path.dirname(OUT), exist_ok=True)
core = SimCore(verbose=False, server_ai=True, seed=SEED)
import sim1v4
from common_cs.states.StatesConst import CIVILIAN_STATE
w = sim1v4.make_1v4(core)
GK = core.GK
TAGS = ("HANG", "HANGING", "FALL", "CARRY", "CATCHED", "STRUGGLE_DROP", "HURT", "FIX", "OPEN_DOOR")
TAG_IDS = [(n, getattr(CIVILIAN_STATE, n)) for n in TAGS if hasattr(CIVILIAN_STATE, n)]


def v3(p):
    return [round(p.x, 2), round(p.y, 2), round(p.z, 2)]


def tags(u):
    out = []
    for n, s in TAG_IDS:
        try:
            if u.state_machine.has_state_ex(s):
                out.append(n)
        except Exception:
            pass
    return out


def policy(u):
    qt = getattr(u, "qaai_targets", None)
    if isinstance(qt, dict) and qt.get("global_policy_name"):
        tgt = qt.get("global_policy_target")
        return qt.get("global_policy_name"), getattr(tgt, "uid", None)
    ac = getattr(u, "ai_controller", None)
    for k in ("global_policy_name", "cur_global_policy_name", "policy_name"):
        if ac is not None and isinstance(getattr(ac, k, None), str):
            return getattr(ac, k), None
    bm = getattr(ac, "base_module", None) if ac is not None else None
    if isinstance(bm, dict):
        for k in ("hang_hook", "catch", "attack", "move"):
            if (bm.get(k) or {}).get("flag"):
                return k, None
    return None, None


def frame(t):
    um = w.unit_mgr
    chars = []
    for u in sorted(core.characters(), key=lambda u: u.uid):
        d = u.get_direction3()
        pn, pt = policy(u)
        chars.append({"uid": u.uid, "pos": v3(u.get_position3()), "dir": [round(d.x, 3), round(d.z, 3)], "tags": tags(u),
                      "hook": getattr(u, "hook_uid", None), "leave": bool(getattr(u, "is_leave", False)),
                      "anim": getattr(u.model, "cur_anim_name", "") if u.model else "", "policy": pn, "ptarget": pt})
    return {"t": round(t, 3),
            "chars": chars,
            "gens": [[g.uid, round(g.get_cur_process_nosync(), 1)] for g in um.get_generator_units()],
            "panels": [[p.uid, p.state, bool(getattr(p, "_destroyed", False))] for p in um.get_panel_units()],
            "hooks": [[h.uid, h.state, round(float(h.cur_process or 0), 1)] for h in um.get_hook_units()],
            "doors": [[d.uid, round(float(d.cur_process or 0), 1), bool(d.can_open), bool(d.has_open)] for d in um.get_door_units()]}


def static():
    um = w.unit_mgr
    def item(u):
        d = u.get_direction3()
        return {"uid": u.uid, "pos": v3(u.get_position3()), "dir": [round(d.x, 3), round(d.z, 3)]}
    names = {}
    for uid, (role, pid, bt) in w.roles.items():
        p = GK.DM.player.get(pid) or {}
        names[uid] = {"role": role, "pid": pid, "name": p.get("name") or p.get("hero_name") or str(pid)}
    return {"scene": w.scene_id, "seed": SEED, "dt": simcore.DT_MS / 1000.0 * EVERY, "roles": names,
            "gens": [item(u) for u in um.get_generator_units()], "panels": [item(u) for u in um.get_panel_units()],
            "windows": [item(u) for u in um.units.values() if type(u).__name__ == "WoodUnit"],
            "hooks": [item(u) for u in um.get_hook_units()], "doors": [item(u) for u in um.get_door_units()],
            "switches": [item(u) for u in um.get_switch_units()]}


STALL_S = 60.0     # 角色位置/状态标签/机进度连续这么久全不变 → 判卡死提前结束（之前两局各白跑到 20 分钟上限）


def stall_key(fr):
    return (tuple((c["uid"], round(c["pos"][0]), round(c["pos"][2]), tuple(c["tags"])) for c in fr["chars"]),
            tuple(g[1] for g in fr["gens"]), tuple(d[1] for d in fr["doors"]))


f = open(OUT, "w", encoding="utf-8")
started, done, end_at = False, 0, None
civ_uids = []
last_key, last_change = None, 0.0
while done < MAXF:
    core.run(EVERY)
    done += EVERY
    if not core.characters():
        continue
    if not started:
        started = True
        f.write(json.dumps(static(), ensure_ascii=False) + "\n")
        civ_uids = [u.uid for u in core.characters() if u.uid != 1]
    t = done * simcore.DT_MS / 1000.0
    fr = frame(t)
    f.write(json.dumps(fr, ensure_ascii=False) + "\n")
    k = stall_key(fr)
    if k != last_key:
        last_key, last_change = k, t
    elif t - last_change >= STALL_S:
        print("卡死 @ 模拟 %.1f 秒：自 %.1f 秒起位置/状态/机进度都没变，提前结束" % (t, last_change), flush=True)
        for c in fr["chars"]:
            print("   uid %d pos %s tags %s policy %s anim %s" % (c["uid"], c["pos"], c["tags"], c["policy"], c["anim"]), flush=True)
        break
    alive = {u.uid for u in core.characters()}
    if end_at is None and all(uid not in alive or getattr(w.unit_mgr.get_unit(uid), "is_leave", False) for uid in civ_uids):
        end_at = done
        print("对局结束 @ 模拟 %.1f 秒" % t, flush=True)
    if end_at is not None and done - end_at >= 60:
        break
    if done % 1800 == 0:
        print("  录到 %.0f 秒" % t, flush=True)
f.close()
print("写出", OUT, os.path.getsize(OUT) // 1024, "KB")
