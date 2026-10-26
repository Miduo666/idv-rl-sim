# -*- coding: utf-8 -*-
"""录像里交互根运动的真值：process_root_motion_event 的 sync_end_pos_dir(anim_name, end_pos) 与该单位动作前最后一次位置的差。
用法: replay_rootmotion.py <录像对局目录> [输出 json]
- 位置来源：et=201 服务端同步 {uid,pos,dir} 与 handle_joystick_move_self_event 里 et=80 的 {uid,pos,dir}
- 网络号↔uid 无映射表：取"动作前位置离 end_pos 最近"的单位（同 §9.11 的就近配对），记下距离供人工筛
录像含其他玩家昵称，只在本地用，结果里只留 uid。"""
import sys, os, math, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay_scan

D = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
last = {}          # uid -> (ts, pos, dir)
rows = []


def put(m, ts):
    if isinstance(m, dict) and m.get("uid") is not None and m.get("pos") is not None:
        last[int(m["uid"])] = (ts, tuple(m["pos"]), tuple(m.get("dir") or (0, 0, 0)))


t0 = None
for k, ts, et, data in replay_scan.events(D):
    t0 = ts if t0 is None else t0
    if et == 201:
        put(data, ts)
        continue
    if et != 10999 or not isinstance(data, dict):
        continue
    fn, args = data.get("func"), data.get("args") or ()
    if fn == "handle_joystick_move_self_event":
        for m in args:
            put(m, ts)
    elif fn == "process_root_motion_event":
        for m in args:
            if not (isinstance(m, dict) and m.get("op") == "sync_end_pos_dir"):
                continue
            e = m["end_pos"]
            best = None
            for uid, (lt, p, dr) in last.items():
                dd = math.hypot(p[0] - e[0], p[2] - e[2])
                if best is None or dd < best[0]:
                    best = (dd, uid, lt, p, dr)
            if best is None:
                continue
            dd, uid, lt, p, dr = best
            fwd = math.hypot(dr[0], dr[2]) or 1.0
            dx, dz = e[0] - p[0], e[2] - p[2]
            rows.append({"t": round(ts - t0, 2), "id": data.get("id"), "anim": m["anim_name"], "uid": uid,
                         "start": p, "end": e, "dist": round(dd, 2), "stale": round(ts - lt, 2),
                         "along_dir": round((dx * dr[0] + dz * dr[2]) / fwd, 2), "dir": dr})

by = collections.defaultdict(list)
for r in rows:
    by[r["anim"]].append(r)
for a, rs in sorted(by.items(), key=lambda x: -len(x[1])):
    ds = sorted(r["dist"] for r in rs)
    print("%-34s %3d 次  水平位移 中位 %.1f  [%s]  沿朝向 %s" % (a, len(rs), ds[len(ds) // 2], " ".join("%.1f" % x for x in ds[:8]),
                                                         " ".join("%.1f" % r["along_dir"] for r in rs[:6])))
if OUT:
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
