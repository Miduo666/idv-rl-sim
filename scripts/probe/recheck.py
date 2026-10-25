# -*- coding: utf-8 -*-
import sys, struct, collections
SP = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-----\3d04aa5f-eccd-4e15-a4af-0eb66ba48c11\scratchpad"
sys.path.insert(0, SP)
from devread import Mem

LIB = 0x77a180b000
M = 0x00FFFFFFFFFFFFFF
SIG = LIB + 0xA9E9038          # "(PerObjectParamBuffer" 签名地址
m = Mem(17226)

print("=== 1. 局内重新解析矩阵链 ===")
m.fetch([SIG + d for d in (0x330, 0x3B8, 0x440)], "(签名邻域)")
roots = {}
for d in (0x330, 0x3B8, 0x440):
    p1 = m.q(SIG + d)
    roots[d] = (p1 & M) if p1 else None
    print("  签名+0x%03X -> p1=%s" % (d, ("0x%X" % roots[d]) if roots[d] else "N/A"))

m.fetch([p + 0xa58 for p in roots.values() if p], "(p1+0xa58)")
mats = {}
for d, p1 in roots.items():
    if not p1:
        continue
    p2 = m.q(p1 + 0xa58)
    if p2:
        mats[d] = (p2 & M) + 0x2c0
        print("  签名+0x%03X -> Matrix=0x%X" % (d, mats[d]))

MAT = list(mats.values())[0] if mats else None
if MAT:
    m.fetch([MAT + d for d in range(-0x400, 0x200, 0x400)] + [MAT - 0x400, MAT, MAT + 0x100], "(矩阵区)")
    print("\n  旧规则相机 Matrix-0x290 = ", ["%.2f" % m.f(MAT - 0x290 + i * 4) if m.f(MAT - 0x290 + i * 4) is not None else "N/A" for i in range(3)])
    row = [m.f(MAT + i * 4) for i in range(16)]
    if all(r is not None for r in row):
        print("  VP矩阵:")
        for r in range(4):
            print("    " + " ".join("%12.4f" % row[r * 4 + c] for c in range(4)))

print("\n=== 2. 按 +0x1a0 筛玩家对象 ===")
AA = LIB + 0xb40a638
m.fetch([AA, AA + 8], "(数组头)")
arr = m.q(AA) & M
end = m.q(AA + 8) & M
cnt = (end - arr) // 8
m.fetch([arr + i * 8 for i in range(cnt)], "(指针区)")
objs = [m.q(arr + i * 8) & M for i in range(cnt)
        if m.q(arr + i * 8) and (m.q(arr + i * 8) & M) > 0x5000000000]
m.fetch([o + k for o in objs for k in (0, 0x100, 0x200)], "(对象本体)")

dist = collections.Counter()
rows = []
for o in objs:
    cf = m.f(o + 0x1a0)
    if cf is None:
        continue
    dist[round(cf, 1)] += 1
    if cf in (450.0, 500.0):
        rows.append((o, cf))
print("  +0x1a0 值分布:", dict(dist.most_common(8)))

m.fetch([(m.q(o + 0x28) & M) + k for o, _ in rows if m.q(o + 0x28) for k in (0, 0xa0)], "(coor)")
print("\n  候选角色:")
for o, cf in rows:
    c = m.q(o + 0x28)
    cc = (c & M) if c else 0
    xyz = [m.f(cc + 0xa0 + i * 4) for i in range(3)] if cc else [None] * 3
    jx = m.q(o + 0x70)
    jx = (jx & 0xFFFFFFFF) if jx is not None else None
    pd2 = m.f(o + 0x298)
    print("    0x%X  +0x1a0=%-5.0f +0x70=%-10s +0x298=%-8s xyz=%s" % (
        o, cf, ("0x%X" % jx) if jx is not None else "N/A",
        ("%.1f" % pd2) if pd2 is not None else "N/A",
        ("(%8.1f,%6.1f,%8.1f)" % tuple(xyz)) if all(v is not None for v in xyz) else "N/A"))
