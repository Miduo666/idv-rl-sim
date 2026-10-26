# -*- coding: utf-8 -*-
"""从录像反推修机站位：修机时修机者相对密码机的位置（密码机局部坐标系）与朝向。
用法: fixpos_from_replay.py <录像对局目录> [输出 json]
- 密码机：snapshot_0 的 entities 里 unit_type==3，pos / angle(度) / pos_id；朝向约定同 WorldBattleClientBase._preload_unit：forward=(sin a, 0, cos a)
- 修机者位置：沿事件流取 handle_joystick_move_self_event 里 et=80 的 {uid,pos,dir} 最新值（修机时站定不动，最新值即站位）
- 谁在修哪台：RPC client_update_process(id=密码机网络号, args=[进度, 速度, {修机者uid: 系数}, …])；网络号↔密码机按修机者离哪台最近配对
录像含其他玩家昵称/账号，只在本地用，结果里只留 uid。"""
import sys, os, math, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay_scan, replay_genius as rg

D = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
ents = rg.读(replay_scan.snaps(D)[0])["data"][0]["snap_shot"]["event_data"]["entities"]
gens = {int(k): (tuple(e["pos"]), float(e["angle"]), e.get("pos_id")) for k, e in ents.items() if e.get("unit_type") == 3}
roles = {int(k): e.get("unit_type") for k, e in ents.items() if e.get("unit_type") in (1, 2)}

last = {}                                  # uid -> (时间, pos, dir)
obs = collections.defaultdict(list)        # 网络号 -> [(时间, 修机者uid, pos, dir, 位置的陈旧秒数, 进度)]
t0 = None
for k, ts, et, data in replay_scan.events(D):
    t0 = ts if t0 is None else t0
    if et != 10999 or not isinstance(data, dict):
        continue
    fn, args = data.get("func"), data.get("args") or ()
    if fn == "handle_joystick_move_self_event":
        for m in args:                         # args 本身是 [{et:80, uid, pos, dir, speed, …}, …]
            if isinstance(m, dict) and m.get("uid") is not None and m.get("pos") is not None:
                last[int(m["uid"])] = (ts, tuple(m["pos"]), tuple(m.get("dir") or (0, 0, 0)))
    elif fn == "client_update_process" and len(args) >= 3 and isinstance(args[2], dict):
        for u in args[2]:
            u = int(u)
            if u in last:
                lt, p, d = last[u]
                obs[data.get("id")].append((ts - t0, u, p, d, ts - lt, float(args[0])))


def local(gpos, ang, p):
    a = math.radians(ang)
    fwd, right = (math.sin(a), math.cos(a)), (math.cos(a), -math.sin(a))
    dx, dz = p[0] - gpos[0], p[2] - gpos[2]
    return dx * fwd[0] + dz * fwd[1], dx * right[0] + dz * right[1], p[1] - gpos[1]


res = []
for nid, rows in obs.items():
    # 网络号 -> 密码机：修机者位置的中位离哪台最近
    best = min(gens, key=lambda g: sum(math.dist((r[2][0], r[2][2]), (gens[g][0][0], gens[g][0][2])) for r in rows))
    gp, ga, pid = gens[best]
    sessions = collections.defaultdict(list)
    for r in rows: sessions[r[1]].append(r)
    for u, rs in sessions.items():
        rs.sort()
        tl = rs[-1]
        f, rt, dy = local(gp, ga, tl[2])
        to_gen = (gp[0] - tl[2][0], gp[2] - tl[2][2]); n = math.hypot(*to_gen) or 1
        facing = (tl[3][0] * to_gen[0] + tl[3][2] * to_gen[1]) / n / (math.hypot(tl[3][0], tl[3][2]) or 1)
        res.append(dict(net_id=nid, gen_uid=best, gen_pos_id=pid, gen_angle=ga, fixer=u, role=roles.get(u),
                        n_updates=len(rs), t=[round(rs[0][0], 1), round(tl[0], 1)], progress=[round(rs[0][5], 1), round(tl[5], 1)],
                        dist=round(math.hypot(f, rt), 2), local_fwd=round(f, 2), local_right=round(rt, 2), dy=round(dy, 2),
                        local_angle_deg=round(math.degrees(math.atan2(rt, f)), 1), facing_cos=round(facing, 3),
                        pos_staleness_s=round(tl[4], 2)))
res.sort(key=lambda r: (r["gen_uid"], r["t"][0]))
print("密码机 %d 台；有修机记录的网络号 %d 个；修机段 %d 个" % (len(gens), len(obs), len(res)))
for r in res:
    print("  机%s(pos_id %s, 角 %.0f°) 修机者%s %s段 t=%s 进度%s  距离 %.2f  局部(前 %.2f, 右 %.2f, 高 %.2f) 方位角 %.1f°  面向机 cos %.3f  位置陈旧 %.2fs" % (
        r["gen_uid"], r["gen_pos_id"], r["gen_angle"], r["fixer"], r["n_updates"], r["t"], r["progress"], r["dist"],
        r["local_fwd"], r["local_right"], r["dy"], r["local_angle_deg"], r["facing_cos"], r["pos_staleness_s"]))
if OUT:
    json.dump(dict(gens={str(k): v for k, v in gens.items()}, sessions=res), open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
