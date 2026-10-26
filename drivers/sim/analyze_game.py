# -*- coding: utf-8 -*-
"""分析 record_game.py 录的一局：求生者挨刀后的反应、有人挂椅时其他人在干什么、各策略占比与"站着不动"比例。
用法: python analyze_game.py <jsonl> [挨刀后观察秒数=8]
"站着不动" = 相邻快照水平位移 / 时间 < 3 单位/秒（求生者跑速 25 单位/秒左右）。"""
import sys, json, math, collections

PATH = sys.argv[1]
WIN = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0
STILL = 3.0

lines = open(PATH, encoding="utf-8").read().splitlines()
head = json.loads(lines[0])
frames = [json.loads(x) for x in lines[1:]]
roles = {int(k): v for k, v in head["roles"].items()}
but = [u for u, r in roles.items() if r["role"] == "butcher"][0]
civs = sorted(u for u, r in roles.items() if r["role"] == "civilian")
hook_pos = {h["uid"]: h["pos"] for h in head["hooks"]}
print("== 对局 %s  %d 帧快照（%.1f 秒）  监管 %s(%s)  求生者 %s" % (PATH, len(frames), frames[-1]["t"], but, roles[but]["name"], civs,
      ))


def d2(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def byuid(fr):
    return {c["uid"]: c for c in fr["chars"]}


F = [byuid(fr) for fr in frames]
T = [fr["t"] for fr in frames]


def speed(i, uid):
    if i == 0 or uid not in F[i] or uid not in F[i - 1]:
        return None
    dt = T[i] - T[i - 1]
    return d2(F[i][uid]["pos"], F[i - 1][uid]["pos"]) / dt if dt > 0 else None


# ---- 1. 各求生者策略占比 + 每种策略里站着不动的比例
print("\n== 1. 策略占比（在场且未倒地/挂椅/被扛时）与站着不动比例")
for uid in civs:
    cnt, still = collections.Counter(), collections.Counter()
    for i in range(1, len(F)):
        c = F[i].get(uid)
        if not c or c["leave"] or set(c["tags"]) & {"FALL", "HANG", "HANGING", "CARRY", "CATCHED"}:
            continue
        p = c["policy"] or "-"
        cnt[p] += 1
        v = speed(i, uid)
        if v is not None and v < STILL:
            still[p] += 1
    tot = sum(cnt.values()) or 1
    print("  c%d %s: %s" % (uid, roles[uid]["name"], "  ".join("%s %.0f%%(不动 %.0f%%)" % (p, 100.0 * n / tot, 100.0 * still[p] / n)
                                                          for p, n in cnt.most_common())))

# ---- 2. 挨刀（tags 新出现 HURT 或 FALL）之后 WIN 秒
print("\n== 2. 挨刀后 %.0f 秒：策略序列、站着不动比例、与监管距离变化" % WIN)
for uid in civs:
    prev = set()
    for i in range(len(F)):
        c = F[i].get(uid)
        if not c:
            prev = set()
            continue
        tg = set(c["tags"])
        new = tg - prev
        prev = tg
        if not (new & {"HURT", "FALL"}):
            continue
        t0 = T[i]
        seq, still_n, n = [], 0, 0
        d_start = d2(c["pos"], F[i][but]["pos"]) if but in F[i] else None
        d_end = None
        for j in range(i + 1, len(F)):
            if T[j] - t0 > WIN:
                break
            cj = F[j].get(uid)
            if not cj:
                break
            if not seq or seq[-1][0] != (cj["policy"] or "-"):
                seq.append([cj["policy"] or "-", round(T[j] - t0, 1)])
            v = speed(j, uid)
            if v is not None:
                n += 1
                still_n += v < STILL
            if but in F[j]:
                d_end = d2(cj["pos"], F[j][but]["pos"])
        print("  c%d @%.1fs 新增 %s  不动 %d/%d  距监管 %s→%s  策略: %s" % (
            uid, t0, sorted(new), still_n, n, d_start and round(d_start), d_end and round(d_end),
            " → ".join("%s@%s" % (p, s) for p, s in seq)))

# ---- 3. 有人挂椅期间，其他在场自由求生者的策略与离椅子的距离
print("\n== 3. 挂椅期间其他求生者")
for uid in civs:
    i = 0
    while i < len(F):
        c = F[i].get(uid)
        if c and c.get("hook"):
            hk = c["hook"]
            t0 = T[i]
            j = i
            others = collections.defaultdict(collections.Counter)
            mind = {}
            while j < len(F) and F[j].get(uid) and F[j][uid].get("hook") == hk:
                for o in civs:
                    co = F[j].get(o)
                    if o == uid or not co or co["leave"] or co.get("hook"):
                        continue
                    others[o][(co["policy"] or "-") + ("/" + co["ptarget"].__str__() if co["policy"] == "QAAI_SAVE" else "")] += 1
                    if hk in hook_pos:
                        dd = d2(co["pos"], hook_pos[hk])
                        mind[o] = min(mind.get(o, 1e9), dd)
                j += 1
            t1 = T[j - 1]
            print("  c%d 挂椅 %s  %.1f→%.1fs（%.0f 秒）" % (uid, hk, t0, t1, t1 - t0))
            for o, cnt in sorted(others.items()):
                tot = sum(cnt.values())
                print("     c%d 最近离椅 %s  %s" % (o, round(mind.get(o, -1)), "  ".join("%s %.0f%%" % (p, 100.0 * n / tot) for p, n in cnt.most_common(5))))
            i = j
        else:
            i += 1
