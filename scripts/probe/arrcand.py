# -*- coding: utf-8 -*-
"""枚举 bss 里所有满足数组签名的候选，逐个用活体数据判分"""
import sys, struct
SP = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-----\3d04aa5f-eccd-4e15-a4af-0eb66ba48c11\scratchpad"
sys.path.insert(0, SP)
from devread import Mem

BSSB = 0x77abf28000
LIB = 0x77a180b000
M = 0x00FFFFFFFFFFFFFF
d = open(SP + r"\bss.bin", "rb").read()

# 复刻原代码: u64[p]==16384 且 u32[p-8]==257 且 f32[p-16]==1.0 -> 数组头 = p+56
cands = []
for p in range(16, len(d) - 64, 8):
    if struct.unpack_from("<Q", d, p)[0] != 16384:
        continue
    if struct.unpack_from("<I", d, p - 8)[0] != 257:
        continue
    if abs(struct.unpack_from("<f", d, p - 16)[0] - 1.0) > 1e-9:
        continue
    cands.append(BSSB + p + 56)
print("bss 内数组签名候选: %d 个" % len(cands))
for c in cands:
    print("  头地址=0x%X  模块偏移=0x%X%s" % (c, c - LIB,
          "   <<< 当前代码选中的" if (c - LIB) == 0xb40a638 else ""))

m = Mem(17226)
m.fetch([c for c in cands] + [c + 8 for c in cands], "(候选头)")
print("\n--- 活体判分 ---")
good = []
for c in cands:
    a, e = m.q(c), m.q(c + 8)
    if a is None or e is None:
        print("  0x%X: 头不可读" % c)
        continue
    a &= M
    e &= M
    n = (e - a) // 8 if e > a else -1
    print("  0x%X: arr=0x%X end=0x%X count=%d" % (c, a, e, n))
    if 0 < n < 20000:
        good.append((c, a, n))

for c, a, n in good:
    m.fetch([a + i * 8 for i in range(n)], "")
    objs = [m.q(a + i * 8) & M for i in range(n)
            if m.q(a + i * 8) and (m.q(a + i * 8) & M) > 0x5000000000]
    m.fetch([o + k for o in objs for k in (0, 0x100, 0x200)], "")
    rd = [o for o in objs if m.q(o + 0x1a0) is not None]
    f450 = [o for o in rd if m.f(o + 0x1a0) in (450.0, 500.0)]
    m.fetch([(m.q(o + 0x28) & M) + k for o in rd if m.q(o + 0x28) for k in (0, 0xa0)], "")
    withxyz = 0
    for o in rd:
        cc = m.q(o + 0x28)
        if cc and m.f((cc & M) + 0xa0) is not None:
            withxyz += 1
    print("\n  [候选 0x%X] 指针%d 可读%d 有坐标%d  +0x1a0在(450,500)的: %d 个"
          % (c, len(objs), len(rd), withxyz, len(f450)))
    for o in f450[:12]:
        cc = m.q(o + 0x28)
        ccm = (cc & M) if cc else 0
        xyz = [m.f(ccm + 0xa0 + i * 4) for i in range(3)] if ccm else [None] * 3
        reg = m.region(ccm) if ccm else None
        print("      0x%X +0x1a0=%.0f coor=0x%X[%s] xyz=%s" % (
            o, m.f(o + 0x1a0), ccm, (reg[2] if reg else "未映射"),
            ("(%8.1f,%6.2f,%8.1f)" % tuple(xyz)) if all(v is not None for v in xyz) else "N/A"))
