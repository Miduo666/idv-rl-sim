# -*- coding: utf-8 -*-
"""copycat300.ps1 的报告：把 s_NNN.txt 串成每个单位每个字段的时间线。
用法: python copycat_report.py <采样目录>     报告同时写到 <目录>/report.txt
"""
import sys, os, re, glob
from collections import OrderedDict

TRIVIAL = {"None", "0", "0.0", "False", "''", '""', "[]", "{}", "()", "set()", "<缺>"}
FIELD_TAGS = ("A", "AV", "AC", "AO", "CA")


def load(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return [l.rstrip("\n") for l in f]


def main(d):
    files = sorted(glob.glob(os.path.join(d, "s_*.txt")))
    out = []
    P = out.append
    if not files:
        print("没有 s_*.txt"); return
    samples = []   # (idx, t, meta, units{uid: info}, fields{(uid, field): value})
    for f in files:
        idx = int(re.search(r"s_(\d+)", f).group(1))
        t = None; meta = {}; units = OrderedDict(); fields = {}
        for l in load(f):
            p = l.split("\t")
            tag = p[0]
            if tag == "TIME": t = float(p[1])
            elif tag in ("WORLD", "UI", "CAM", "KEYS", "END"): meta[tag] = "\t".join(p[1:])
            elif tag == "U": units[p[1]] = "\t".join(p[2:])
            elif tag in FIELD_TAGS and len(p) >= 4: fields[(p[1], tag + ":" + p[2])] = p[3]
            elif tag == "C" and len(p) >= 4: fields[(p[1], "C:" + p[2])] = p[3]
            elif tag in ("W", "WV", "WC", "WO", "G", "GV", "GO") and len(p) >= 4:
                fields[("<" + tag[0] + ">" + p[1], tag + ":" + p[2])] = p[3]
            elif tag == "GK" and len(p) >= 4: fields[("<GK>", "GK:" + p[1])] = p[2] + " " + p[3]
        samples.append((idx, t, meta, units, fields))
    T0 = samples[0][1] or 0

    def ts(t): return "t+%3ds" % int((t or T0) - T0)

    P("# 模仿者采样报告  %s  共 %d 个快照，跨 %s" % (d, len(samples), ts(samples[-1][1])))
    P("")
    P("## 一、世界 / 面板 / 单位键 的变化")
    for key in ("WORLD", "CAM", "UI", "KEYS"):
        last = None
        for idx, t, meta, _, _ in samples:
            v = meta.get(key, "<缺>")
            if v != last:
                P("  %s %s  %s" % (ts(t), key, v[:600]))
                last = v
    P("")
    P("## 二、单位清单(最后一次出现时的信息)")
    seen = OrderedDict()
    for idx, t, _, units, _ in samples:
        for uid, info in units.items():
            if uid not in seen: seen[uid] = [t, t, info]
            seen[uid][1] = t; seen[uid][2] = info
    for uid, (ta, tb, info) in seen.items():
        P("  uid=%s  出现 %s~%s  %s" % (uid, ts(ta), ts(tb), info.replace("\t", "  ")))
    P("")

    # 时间线
    allkeys = OrderedDict()
    for s in samples:
        for k in s[4]:
            allkeys[k] = 1
    tl = {}
    for k in allkeys:
        seq = []
        for idx, t, _, units, fields in samples:
            owner = k[0]
            present = owner.startswith("<") or owner in units
            if not present: continue
            seq.append((t, fields.get(k, "<缺>")))
        tl[k] = seq

    P("## 三、字段覆盖：每个字段在多少个单位上有非平凡值(看别人的身份有没有下发)")
    byfield = OrderedDict()
    for (owner, field), seq in tl.items():
        if owner.startswith("<"): continue
        nontriv = any(v not in TRIVIAL for _, v in seq)
        byfield.setdefault(field, [0, 0, []])
        byfield[field][1] += 1
        if nontriv:
            byfield[field][0] += 1
            byfield[field][2].append(owner)
    nunits = len(seen)
    for field, (a, b, owners) in sorted(byfield.items(), key=lambda x: (-x[1][0], x[0])):
        if a == 0: continue
        P("  %-50s 非平凡 %2d / 出现 %2d / 单位总数 %d" % (field, a, b, nunits))
    P("")

    P("## 四、会变的字段(时间线)")
    for (owner, field), seq in tl.items():
        vals = [v for _, v in seq]
        if len(set(vals)) <= 1: continue
        parts = []
        last = None
        for t, v in seq:
            if v != last:
                parts.append("%s %s" % (ts(t), v[:120])); last = v
        if len(parts) > 12:
            parts = parts[:6] + ["...(%d 次变化)" % len(parts)] + parts[-3:]
        P("  [%s] %s" % (owner, field))
        for x in parts: P("        " + x)
    P("")

    P("## 五、不变的非平凡字段(按单位)")
    cur = None
    for (owner, field), seq in sorted(tl.items(), key=lambda x: (x[0][0], x[0][1])):
        vals = set(v for _, v in seq)
        if len(vals) != 1: continue
        v = vals.pop()
        if v in TRIVIAL: continue
        if owner != cur:
            P("  -- %s" % owner); cur = owner
        P("     %-48s %s" % (field, v[:160]))

    txt = "\n".join(out)
    with open(os.path.join(d, "report.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)


if __name__ == "__main__":
    main(sys.argv[1])
