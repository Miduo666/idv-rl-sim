# -*- coding: utf-8 -*-
"""heal60.ps1 的报告：python heal60_report.py <采样目录>   (目录里要有 idv_heal60.jsonl)

输出到控制台，同时写 <目录>/report.txt。四段：
  一  治疗段：按 debug_record_cured_info 的治疗者列表非空(或速度非 0)切段，
      给出 自愈/被治疗、治疗者、进度 起→止、上限、平均速率、显示百分比(进度/上限)
  二  每个求生者的治疗字段时间线(只打有变化的帧)
  三  逐帧变化的标量(找"倒地/受伤"字段用)，按时间排
  四  变化过多被截断的属性 + 关键字字段的取值时间线
"""
import json, os, sys

FIX = ("anim", "cured_process_client", "cured_speed_client", "cured_uid", "debug_record_cured_info", "floor_blood")


def f4(v):
    return ("%.2f" % v) if isinstance(v, float) else repr(v)


def parse_dbg(d):
    """(时间戳, [治疗者...], 进度, 速度, 上限) —— 形状不对就返回 None"""
    if isinstance(d, list) and len(d) >= 5 and isinstance(d[1], list):
        return {"dbg_ts": d[0], "healers": d[1], "prog": d[2], "speed": d[3], "limit": d[4]}
    return None


def main(folder):
    path = os.path.join(folder, "idv_heal60.jsonl")
    head, end, frames, bad = {}, {}, [], []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                bad.append(ln[:120])
                continue
            if r.get("start"):
                head = r
            elif r.get("end") or r.get("fatal"):
                end = r
            else:
                frames.append(r)

    out = []
    P = out.append
    errs = [r for r in frames if "err" in r]
    costs = sorted(r.get("cost_ms", 0) for r in frames)
    P("帧数 %d  时长 %.1fs  间隔 %s  world=%s  出错帧 %d  坏行 %d" % (
        len(frames), frames[-1]["t"] if frames else 0, head.get("interval"), head.get("world"), len(errs), len(bad)))
    if costs:
        P("单帧耗时 ms: 中位 %.1f  最大 %.1f" % (costs[len(costs) // 2], costs[-1]))
    if end.get("fatal"):
        P("!! 采样线程崩溃:\n" + end["fatal"])
    elif not end:
        P("!! 没有结束标记(被中途拉回?)")
    for r in errs[:5]:
        P("  err t=%.2f %s" % (r["t"], r["err"]))

    # 按 uid 收集
    series = {}
    meta = {}
    for r in frames:
        for e in r.get("s", []):
            uid = e.get("uid")
            series.setdefault(uid, []).append((r["t"], e, r.get("h")))
            m = meta.setdefault(uid, {"cls": e.get("cls"), "me": False})
            m["me"] = m["me"] or e.get("me")

    # 一、治疗段
    P("\n==== 一、治疗段 ====")
    for uid, rows in series.items():
        seg = None
        segs = []
        for t, e, _ in rows:
            dbg = parse_dbg(e.get("debug_record_cured_info"))
            spd = e.get("cured_speed_client") or 0
            active = bool(dbg and dbg["healers"]) or (isinstance(spd, (int, float)) and spd != 0)
            if active:
                if seg is None:
                    seg = {"t0": t, "rows": []}
                seg["rows"].append((t, e, dbg))
            elif seg is not None:
                segs.append(seg)
                seg = None
        if seg is not None:
            segs.append(seg)
        for s in segs:
            t0, e0, d0 = s["rows"][0]
            t1, e1, d1 = s["rows"][-1]
            # 非本机单位的 cured_process_client 恒 0(2026-09-25 实测)，进度一律取治疗记录
            p0 = (d0 or {}).get("prog")
            p1 = (d1 or {}).get("prog")
            if d1 and isinstance(e1.get("now"), (int, float)) and isinstance(p1, (int, float)):
                p1 = min(p1 + (d1["speed"] or 0) * (e1["now"] - d1["dbg_ts"]), d1["limit"] or 1e9)
            lim = (d1 or d0 or {}).get("limit")
            healers = sorted({str(h) for _, _, d in s["rows"] if d for h in d["healers"]})
            cu = e1.get("cured_uid")
            # 伤者身上 cured_uid 恒为自己，分不出自愈/被治；看治疗者列表
            kind = "?" if not healers else ("自愈" if healers == [str(uid)] else
                                           ("被治疗" if str(uid) not in healers else "自愈+被治疗"))
            rate = ((p1 - p0) / (t1 - t0)) if isinstance(p0, (int, float)) and isinstance(p1, (int, float)) and t1 > t0 else None
            pct = (p1 / lim * 100) if isinstance(p1, (int, float)) and isinstance(lim, (int, float)) and lim else None
            anims = []
            for _, e, _ in s["rows"]:
                a = e.get("anim")
                if not anims or anims[-1] != a:
                    anims.append(a)
            P("uid=%s%s %s  t=%.2f→%.2f (%.1fs)  %s cured_uid=%s 治疗者=%s" % (
                uid, "(我)" if meta[uid]["me"] else "", meta[uid]["cls"], t0, t1, t1 - t0, kind, cu, healers))
            P("    进度 %s → %s  上限 %s  平均 %s/s  显示 %s  动画 %s" % (
                f4(p0), f4(p1), f4(lim), f4(rate) if rate is not None else "-",
                ("%.0f%%" % pct) if pct is not None else "-", anims[:8]))
            # 记录只在开始/停止/变速时改写，实时进度 = 进度 + 速度 × (now − 记录时间戳)
            for tag, (_, e, d) in (("段首", s["rows"][0]), ("段尾", s["rows"][-1])):
                now = e.get("now")
                if d and isinstance(now, (int, float)) and isinstance(d["prog"], (int, float)):
                    ex = d["prog"] + (d["speed"] or 0) * (now - d["dbg_ts"])
                    P("    %s now=%.2f 记录时间戳=%.2f 差=%.2f  外推进度=%.2f (%.0f%%)" % (
                        tag, now, d["dbg_ts"], now - d["dbg_ts"], ex, ex / d["limit"] * 100 if d["limit"] else 0))
        if not segs:
            P("uid=%s%s %s  无治疗段" % (uid, "(我)" if meta[uid]["me"] else "", meta[uid]["cls"]))

    # 二、治疗字段时间线
    P("\n==== 二、治疗字段时间线(只打变化帧) ====")
    for uid, rows in series.items():
        P("-- uid=%s%s %s" % (uid, "(我)" if meta[uid]["me"] else "", meta[uid]["cls"]))
        last = None
        shown = 0
        for t, e, h in rows:
            cur = tuple(json.dumps(e.get(k), ensure_ascii=False) for k in FIX)
            if cur == last:
                continue
            last = cur
            shown += 1
            if shown > 150:
                P("   ...(截断)")
                break
            P("  t=%6.2f anim=%-22s cpc=%-7s csc=%-6s cured_uid=%-8s floor_blood=%-6s dbg=%s  | 监管=%s" % (
                t, e.get("anim"), f4(e.get("cured_process_client")), f4(e.get("cured_speed_client")),
                e.get("cured_uid"), f4(e.get("floor_blood")),
                json.dumps(e.get("debug_record_cured_info"), ensure_ascii=False), h))

    # 三、逐帧变化
    P("\n==== 三、标量变化事件(找倒地/受伤字段) ====")
    ev = []
    for uid, rows in series.items():
        for t, e, _ in rows:
            for k, a, b in e.get("chg", []):
                ev.append((t, uid, k, a, b, e.get("anim")))
    ev.sort(key=lambda x: (x[0], str(x[1])))
    for t, uid, k, a, b, an in ev[:600]:
        P("  t=%6.2f uid=%s %-40s %s → %s   (anim=%s)" % (t, uid, k, f4(a), f4(b), an))
    if len(ev) > 600:
        P("  ...共 %d 条，截断" % len(ev))

    # 四、噪声属性 + 关键字字段
    na = end.get("noisy_after", 12)
    noisy = sorted(((c, k) for k, c in (end.get("counts") or {}).items() if c > na), reverse=True)
    P("\n==== 四、变化超过 %d 次、逐条记录已截断的属性 ====" % na)
    for c, k in noisy[:60]:
        P("  %5d  %s" % (c, k))
    P("\n---- 关键字字段取值时间线(只打变化) ----")
    for uid, rows in series.items():
        keys = sorted({k for _, e, _ in rows for k in e.get("kw", {})})
        for k in keys:
            seq, lastv = [], object()
            for t, e, _ in rows:
                v = e.get("kw", {}).get(k)   # 不在 kw 里 = 0/None/False
                if v != lastv:
                    seq.append("%.2f:%s" % (t, f4(v)))
                    lastv = v
            if len(seq) > 1:
                P("  uid=%s %-36s %s%s" % (uid, k, "  ".join(seq[:30]), " ..." if len(seq) > 30 else ""))

    text = "\n".join(out)
    with open(os.path.join(folder, "report.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    print("\n[报告已存] %s" % os.path.join(folder, "report.txt"))


if __name__ == "__main__":
    main(sys.argv[1])
