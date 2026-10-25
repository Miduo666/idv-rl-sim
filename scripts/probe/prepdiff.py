# -*- coding: utf-8 -*-
# 读 prepdiff60.ps1 采到的样本目录，输出差分报告。
# 用法: python prepdiff.py <样本目录>
import sys, os, glob, collections

d = sys.argv[1]
files = sorted(glob.glob(os.path.join(d, "s_*.txt")))
samples = []
for f in files:
    lines = open(f, encoding="utf-8-sig", errors="replace").read().splitlines()
    t = None; keys = {}; attrs = {}; panel = ""
    for ln in lines:
        p = ln.split("\t")
        if p[0] == "TIME": t = float(p[1])
        elif p[0] == "PANEL": panel = "\t".join(p[1:])
        elif p[0] == "KEY":
            src = p[1]; ident = "\t".join(p[2:-1]); keys[(src, ident)] = p[-1]
        elif p[0] == "ATTR" and len(p) >= 4:
            attrs[p[1]] = (p[2], p[3])
    if t is not None: samples.append((os.path.basename(f), t, panel, keys, attrs))

out = []
if not samples:
    print("没有有效样本"); sys.exit(1)
t0 = samples[0][1]
out.append("样本 %d 个，跨度 %.1f 秒；首个样本面板: %s" % (len(samples), samples[-1][1] - t0, samples[0][2]))

# 一、已知候选源：每个 (源, 玩家) 的天赋时间线
out.append("\n== 一、候选源的天赋时间线(只列变化点) ==")
all_keys = sorted({k for s in samples for k in s[3]})
changed_src = collections.Counter()
for k in all_keys:
    prev = None; line = []
    for name, t, _, keys, _ in samples:
        v = keys.get(k, "<无>")
        if v != prev:
            line.append("t+%.1f=%s" % (t - t0, v)); prev = v
    if len(line) > 1: changed_src[k[0]] += 1
    out.append("  %-7s %-40s %s" % (k[0], k[1], "  ->  ".join(line)))
out.append("\n  变化过的(源: 玩家数): %s" % (dict(changed_src) or "无 —— 所有候选源都没变"))

# 二、属性哈希差分：哪些属性在变
out.append("\n== 二、UIRoomWait(ui.) / g_avatar(av.) 上发生过变化的属性 ==")
names = sorted({a for s in samples for a in s[4]})
for a in names:
    vals = [s[4].get(a, ("<无>", ""))[0] for s in samples]
    n_change = sum(1 for i in range(1, len(vals)) if vals[i] != vals[i - 1])
    if n_change == 0: continue
    firsts = []
    prev = None
    for s in samples:
        h, pv = s[4].get(a, ("<无>", ""))
        if h != prev:
            firsts.append("t+%.1f %s" % (s[1] - t0, pv[:100])); prev = h
    out.append("  %-40s 变化 %d 次" % (a, n_change))
    for x in firsts[:6]: out.append("        %s" % x)
    if len(firsts) > 6: out.append("        ... 共 %d 个不同值" % len(firsts))

rep = "\n".join(out)
open(os.path.join(d, "report.txt"), "w", encoding="utf-8").write(rep)
print(rep)
print("\n[报告已存] %s" % os.path.join(d, "report.txt"))
