# -*- coding: utf-8 -*-
"""游戏前台活跃时跑：一次性取全对象表 + 定位相机坐标偏移 + 落盘矩阵邻域供离线分析"""
import sys, struct, collections
SP = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-----\3d04aa5f-eccd-4e15-a4af-0eb66ba48c11\scratchpad"
sys.path.insert(0, SP)
from devread import Mem

LIB = 0x77a180b000
M = 0x00FFFFFFFFFFFFFF
SIG = LIB + 0xA9E9038
ROLE = {"butcher_sxwd": "小丑", "w_cp": "心理学家", "m_yc": "邮差",
        "m_yxz_bo": "佣兵", "w_xiangshuishi": "调香师"}
m = Mem(17226)

# ---------- 0. 常驻率体检 ----------
AA = LIB + 0xb40a638
m.fetch([AA, AA + 8], "(数组头)")
if m.q(AA) is None:
    print("!! 数组头都读不到，游戏可能不在前台，先切回游戏再跑")
    sys.exit(1)
arr = m.q(AA) & M
end = m.q(AA + 8) & M
cnt = (end - arr) // 8
m.fetch([arr + i * 8 for i in range(cnt)], "(指针区)")
raw = [m.q(arr + i * 8) for i in range(cnt)]
ok = sum(1 for v in raw if v is not None)
print("Count=%d  指针页常驻率 %d/%d" % (cnt, ok, cnt))
if ok < cnt * 0.5:
    print("!! 常驻率过低，游戏多半还在后台。请切到游戏前台停留 10 秒后重跑")
    sys.exit(1)
objs = [v & M for v in raw if v and (v & M) > 0x5000000000]

# ---------- 1. 全对象字段 ----------
m.fetch([o + k for o in objs for k in (0, 0x100, 0x200)], "(对象本体)")
readable = [o for o in objs if m.q(o + 0xf8) is not None]
print("对象可读 %d/%d" % (len(readable), len(objs)))

lvl = [(o, m.q(o + 0xf8)) for o in readable]
for add in (0x0, 0x8, 0x20, 0x20):
    m.fetch([(v & M) + add for _, v in lvl if v], "(类名链)")
    lvl = [(o, (m.q((v & M) + add) if v else None)) for o, v in lvl]
m.fetch([(v & M) for _, v in lvl if v], "(类名末端)")
names, strs = {}, []
for o, v in lvl:
    if v:
        p = v & M
        s, ln = m.q(p + 0x8), m.q(p + 0x10)
        if s and ln and 0 < (ln & 0xFFFFFFFF) < 512:
            strs.append((o, s & M, ln & 0xFFFFFFFF))
m.fetch([a + k for _, a, L in strs for k in (0, L)], "(字符串)")
for o, a, L in strs:
    b = m.get(a, L)
    if b:
        names[o] = b.decode("utf-8", "replace")
print("类名读出 %d/%d" % (len(names), len(readable)))

m.fetch([(m.q(o + 0x28) & M) + k for o in readable if m.q(o + 0x28) for k in (0, 0xa0)], "(coor)")

def coord(o):
    c = m.q(o + 0x28)
    if not c:
        return None
    cc = c & M
    v = [m.f(cc + 0xa0 + i * 4) for i in range(3)]
    return None if any(x is None for x in v) else v

print("\n=== 五人定位 ===")
five = {}
for o in readable:
    nm = names.get(o, "")
    if not nm:
        continue
    for key, role in ROLE.items():
        if key in nm:
            xyz = coord(o)
            if xyz and any(abs(t) > 0.5 for t in xyz):
                five.setdefault(role, []).append((o, xyz, nm))
for role, lst in five.items():
    for o, xyz, nm in lst:
        jx = m.q(o + 0x70)
        print("  %-6s 0x%X xyz=(%8.1f,%6.1f,%8.1f) +0x70=%s +0x1a0=%s +0x298=%s" % (
            role, o, xyz[0], xyz[1], xyz[2],
            ("0x%X" % (jx & 0xFFFFFFFF)) if jx is not None else "N/A",
            ("%.0f" % m.f(o + 0x1a0)) if m.f(o + 0x1a0) is not None else "N/A",
            ("%.0f" % m.f(o + 0x298)) if m.f(o + 0x298) is not None else "N/A"))

print("\n=== 所有 chr\\ 对象 ===")
for o in readable:
    nm = names.get(o, "")
    if "chr\\" not in nm or "crow" in nm or "joseph_camera" in nm:
        continue
    xyz = coord(o)
    print("  0x%X %s  %s" % (o, ("(%8.1f,%6.1f,%8.1f)" % tuple(xyz)) if xyz else "N/A", nm[:70]))

# ---------- 2. 相机坐标 ----------
m.fetch([SIG + 0x440], "(签名)")
p1 = m.q(SIG + 0x440) & M
m.fetch([p1 + 0xa58], "")
MAT = (m.q(p1 + 0xa58) & M) + 0x2c0
print("\n=== 矩阵 0x%X ===" % MAT)
lo, hi = MAT - 0x2000, MAT + 0x800
m.fetch(list(range(lo, hi, 4096)) + [hi], "(矩阵邻域)")
blob = m.get(lo, hi - lo)
if blob:
    open(SP + r"\matrix_area.bin", "wb").write(struct.pack("<Q", lo) + blob)
    print("  已落盘 matrix_area.bin (基址0x%X, %d字节)" % (lo, len(blob)))

joker = five.get("小丑", [])
if joker:
    jx, jy, jz = joker[0][1]
    print("  小丑坐标 (%.1f, %.1f, %.1f) —— 以此为基准找相机" % (jx, jy, jz))
    hits = []
    for d in range(-0x2000, 0x800, 4):
        v = [m.f(MAT + d + i * 4) for i in range(3)]
        if any(x is None for x in v):
            continue
        if abs(v[0] - jx) < 120 and abs(v[2] - jz) < 120 and abs(v[1] - jy) < 250:
            hits.append((abs(v[0] - jx) + abs(v[2] - jz), d, v))
    hits.sort()
    print("  候选相机偏移(按接近度):")
    for dist, d, v in hits[:15]:
        print("    Matrix%+#07x -> (%9.2f,%7.2f,%9.2f)  差 %.1f%s" % (
            d, v[0], v[1], v[2], dist, "   <<< 旧规则位置" if d == -0x290 else ""))
    if not hits:
        print("    未找到；可能相机坐标不在矩阵邻域，需要用移动差分法")
else:
    print("  !! 没定位到小丑，无法做相机基准")
