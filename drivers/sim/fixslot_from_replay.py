# -*- coding: utf-8 -*-
"""从录像的状态切换事件(et=202)取修机站位真值：params.new_state_args.inter_pos_params = {uid: 交互目标, angle: 方位键}，
here_pos = 进入状态时被放到的位置。只保留交互目标是密码机(unit_type 3)的，换算到密码机局部坐标系并与公式
pos = 机位置 + 方位向量(键) × inter_dis × 0.5（iLogicGenerator.get_pos_for_ai，inter_dis = DM.ui_inter[FIX] = 30）对照。
用法: fixslot_from_replay.py <录像对局目录> [输出 json]"""
import sys, os, math, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import replay_scan, replay_genius as rg

D = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
R = 15.0                                         # inter_dis(30) × 0.5
ents = rg.读(replay_scan.snaps(D)[0])["data"][0]["snap_shot"]["event_data"]["entities"]
gens = {int(k): (tuple(e["pos"]), float(e["angle"])) for k, e in ents.items() if e.get("unit_type") == 3}


def slot(gpos, ang, key):
    """iLogicGenerator.check_fix_range / get_pos_for_ai 的方位向量：dir2 = 机朝向 (sin a, cos a)；
    90 → 逆时针转 -π/2，180 → 转 π（取反），270 → 转 +π/2。"""
    a = math.radians(ang)
    x, z = math.sin(a), math.cos(a)
    t = {0: 0.0, 90: -math.pi / 2, 180: math.pi, 270: math.pi / 2}[key]
    c, s = math.cos(t), math.sin(t)
    dx, dz = x * c - z * s, x * s + z * c          # UtilsMath.get_anticlockwise_angle_vector2：标准逆时针旋转（待核对，见下方自检）
    return gpos[0] + dx * R, gpos[2] + dz * R


rows = []
t0 = None
for k, ts, et, data in replay_scan.events(D):
    t0 = ts if t0 is None else t0
rows_raw = []
for p in replay_scan.snaps(D)[1:]:
    for blk in rg.读(p).get("data", []):
        for ev in blk.get("battle_event") or []:
            body = ev[1]
            if body.get("et") != 202: continue
            prm = body.get("params") or {}
            nsa = prm.get("new_state_args") or {}
            ipp = nsa.get("inter_pos_params") or {}
            tgt = ipp.get("uid")
            if tgt is None or int(tgt) not in gens: continue
            # range_key = 方位键（fix_pos 的键）；a_r_s_p/a_r_s_d 推断为动画根运动起点的位置/方向 = 吸附后的站位
            rows_raw.append((ev[0] - t0, body.get("uid"), body.get("state_id"), int(tgt), nsa.get("range_key"),
                             nsa.get("a_r_s_p") or nsa.get("here_pos"), nsa.get("a_r_s_d"), nsa.get("anim_index")))
print("以密码机为交互目标的状态切换 %d 条" % len(rows_raw))
for t, u, sid, g, key, here, hdir, anim in rows_raw[:40]:
    gp, ga = gens[g]
    line = "  t=%6.1f 单位%s 状态%s 机%s(角%.0f) range_key %s anim %s" % (t, u, sid, g, ga, key, anim)
    if here is not None and key in (0, 90, 180, 270):
        sx, sz = slot(gp, ga, key)
        d = math.dist((here[0], here[2]), (sx, sz)); r = math.dist((here[0], here[2]), (gp[0], gp[2]))
        near = min((0, 90, 180, 270), key=lambda kk: math.dist((here[0], here[2]), slot(gp, ga, kk)))
        line += "  站位离机心 %.2f  离公式点 %.2f  最近的公式点是键 %s  朝向 %s" % (r, d, near, None if hdir is None else [round(x, 3) for x in hdir])
        rows.append(dict(t=round(t, 2), unit=u, state=sid, gen=g, key=key, here=list(here), r=round(r, 3), err=round(d, 3), nearest_key=near))
    else:
        line += "  站位=%s" % (here,)
    print(line)
if rows:
    errs = sorted(r["err"] for r in rows); rs = sorted(r["r"] for r in rows)
    print("有 here_pos 的 %d 条：离机心 中位 %.2f [%.2f, %.2f]；离公式点 中位 %.2f 最大 %.2f；方位键分布 %s" % (
        len(rows), rs[len(rs) // 2], rs[0], rs[-1], errs[len(errs) // 2], errs[-1], dict(collections.Counter(r["key"] for r in rows))))
if OUT:
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
