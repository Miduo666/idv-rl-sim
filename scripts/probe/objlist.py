# -*- coding: utf-8 -*-
"""列出全部可读对象 + 落盘快照，供差分比对"""
import sys, struct, json, collections
SP = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-----\3d04aa5f-eccd-4e15-a4af-0eb66ba48c11\scratchpad"
sys.path.insert(0, SP)
from devread import Mem

LIB = 0x77a180b000
M = 0x00FFFFFFFFFFFFFF
tag = sys.argv[1] if len(sys.argv) > 1 else "A"
m = Mem(17226)

AA = LIB + 0xb40a638
m.fetch([AA, AA + 8], "")
arr = m.q(AA) & M
end = m.q(AA + 8) & M
cnt = (end - arr) // 8
m.fetch([arr + i * 8 for i in range(cnt)], "")
objs = [m.q(arr + i * 8) & M for i in range(cnt)
        if m.q(arr + i * 8) and (m.q(arr + i * 8) & M) > 0x5000000000]
m.fetch([o + k for o in objs for k in (0, 0x100, 0x200)], "")
readable = [o for o in objs if m.q(o + 0xf8) is not None]

# 类名链 + 失败诊断
lvl = [(o, m.q(o + 0xf8)) for o in readable]
fail = collections.Counter()
for hop, add in enumerate((0x0, 0x8, 0x20, 0x20)):
    m.fetch([(v & M) + add for _, v in lvl if v], "")
    nxt = []
    for o, v in lvl:
        if v is None:
            nxt.append((o, None))
            continue
        w = m.q((v & M) + add)
        if w is None:
            fail["第%d跳不可读" % (hop + 1)] += 1
        nxt.append((o, w))
    lvl = nxt
m.fetch([(v & M) for _, v in lvl if v], "")
names, strs = {}, []
for o, v in lvl:
    if not v:
        continue
    p = v & M
    s, ln = m.q(p + 0x8), m.q(p + 0x10)
    if s is None or ln is None:
        fail["末端不可读"] += 1
    elif not (s and 0 < (ln & 0xFFFFFFFF) < 512):
        fail["长度非法"] += 1
    else:
        strs.append((o, s & M, ln & 0xFFFFFFFF))
m.fetch([a + k for _, a, L in strs for k in (0, L)], "")
for o, a, L in strs:
    b = m.get(a, L)
    if b:
        names[o] = b.decode("utf-8", "replace")
    else:
        fail["字符串页不可读"] += 1

m.fetch([(m.q(o + 0x28) & M) + k for o in readable if m.q(o + 0x28) for k in (0, 0xa0)], "")

snap = {}
rows = []
for o in readable:
    c = m.q(o + 0x28)
    cc = (c & M) if c else 0
    xyz = [m.f(cc + 0xa0 + i * 4) for i in range(3)] if cc else [None] * 3
    if any(v is None for v in xyz):
        continue
    jx = m.q(o + 0x70)
    rows.append(dict(o=o, xyz=xyz, nm=names.get(o, ""),
                     jx=(jx & 0xFFFFFFFF) if jx is not None else None,
                     f1a0=m.f(o + 0x1a0), f298=m.f(o + 0x298),
                     b_aa=(m.get(o + 0xaa, 1)[0] if m.get(o + 0xaa, 1) else None)))
    snap["0x%X" % o] = xyz

json.dump(snap, open(SP + r"\snap_%s.json" % tag, "w"))
print("对象 %d, 可读 %d, 有坐标 %d, 类名 %d" % (len(objs), len(readable), len(rows), len(names)))
print("类名失败原因:", dict(fail))

print("\n=== y 在 (0.05, 0.4) 的对象（老版本求生者 y=0.16）===")
for r in sorted(rows, key=lambda r: r["xyz"][0]):
    if 0.05 < r["xyz"][1] < 0.4:
        print("  0x%X (%8.1f,%6.2f,%8.1f) +0x70=%-10s +0x1a0=%-6s +0x298=%-6s +0xaa=%-5s %s" % (
            r["o"], r["xyz"][0], r["xyz"][1], r["xyz"][2],
            ("0x%X" % r["jx"]) if r["jx"] is not None else "N/A",
            ("%.0f" % r["f1a0"]) if r["f1a0"] is not None else "N/A",
            ("%.0f" % r["f298"]) if r["f298"] is not None else "N/A",
            ("0x%02X" % r["b_aa"]) if r["b_aa"] is not None else "N/A",
            r["nm"][:46]))

print("\n=== +0x1a0 值分布 ===")
d = collections.Counter(round(r["f1a0"], 0) for r in rows if r["f1a0"] is not None)
print(" ", dict(d.most_common(10)))
print("\n=== +0x1a0 非零的对象 ===")
for r in rows:
    if r["f1a0"]:
        print("  0x%X (%8.1f,%6.2f,%8.1f) +0x1a0=%-6.0f +0x70=%-10s %s" % (
            r["o"], r["xyz"][0], r["xyz"][1], r["xyz"][2], r["f1a0"],
            ("0x%X" % r["jx"]) if r["jx"] is not None else "N/A", r["nm"][:46]))
