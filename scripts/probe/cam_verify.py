# -*- coding: utf-8 -*-
"""同一次读取里同时取 VP 矩阵与候选相机三连，验证能否从矩阵反解相机坐标"""
import sys, time
SP = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-----\3d04aa5f-eccd-4e15-a4af-0eb66ba48c11\scratchpad"
sys.path.insert(0, SP)
from devread import Mem

LIB = 0x77a180b000
M = 0x00FFFFFFFFFFFFFF
SIG = LIB + 0xA9E9038
CANDS = [-0x1e0, -0x110, -0xd0, -0x290]


def inv3(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        return None, det
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d)] ], det


def inv3b(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    adj = [[(e * i - f * h), (c * h - b * i), (b * f - c * e)],
           [(f * g - d * i), (a * i - c * g), (c * d - a * f)],
           [(d * h - e * g), (b * g - a * h), (a * e - b * d)]]
    return [[adj[r][k] / det for k in range(3)] for r in range(3)], det


for t in range(3):
    m = Mem(17226, refresh=(t == 0))
    m.fetch([SIG + 0x440], "")
    p1 = m.q(SIG + 0x440) & M
    m.fetch([p1 + 0xa58], "")
    MAT = (m.q(p1 + 0xa58) & M) + 0x2c0
    m.fetch([MAT + d for d in (-0x400, -0x200, 0, 0x40)] + [MAT + c for c in CANDS], "")
    row = [m.f(MAT + i * 4) for i in range(16)]
    if any(r is None for r in row):
        print("矩阵读取不全"); continue
    print("\n=== 采样 %d  (Matrix=0x%X) ===" % (t + 1, MAT))
    A = [row[0:3], row[4:7], row[8:11]]
    tr = row[12:15]
    Ai, det = inv3b(A)
    cam = [-sum(tr[k] * Ai[k][j] for k in range(3)) for j in range(3)]
    print("  矩阵反解相机 = (%9.2f, %7.2f, %9.2f)   det=%.4f" % (cam[0], cam[1], cam[2], det))
    for c in CANDS:
        v = [m.f(MAT + c + i * 4) for i in range(3)]
        if any(x is None for x in v):
            print("  Matrix%+#07x = 不可读" % c)
            continue
        err = max(abs(v[j] - cam[j]) for j in range(3))
        print("  Matrix%+#07x = (%9.2f, %7.2f, %9.2f)   与反解最大差 %8.2f %s" % (
            c, v[0], v[1], v[2], err, "  <<< 吻合" if err < 5 else ""))
    time.sleep(2)
