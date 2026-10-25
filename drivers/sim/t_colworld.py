# -*- coding: utf-8 -*-
"""colworld 自测：合成 .scn_col（按 §9.7 格式打包）+ 与暴力解对拍。不需要游戏资源。用法: python t_colworld.py"""
import sys, os, struct, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import scncol, colworld
from colworld import ColWorld, _Tris, ray_tris, seg_tris

rng = np.random.default_rng(1234)
FAIL = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)


def pack_obj(verts, idx, mat=None, pos=None):
    b = struct.pack("<4I", 1, 0, 1, len(verts)) + b"".join(struct.pack("<3f", *v) for v in verts)
    nt = len(idx) // 3
    b += struct.pack("<I", nt) + struct.pack("<%dI" % nt, *([0] * nt))
    b += struct.pack("<I", len(idx)) + struct.pack("<%dI" % len(idx), *idx)
    if mat is not None:
        b += struct.pack("<I16f", 4, *mat)
    if pos is not None:
        b += struct.pack("<I3f", 3, *pos)
    return b


def box_mesh(hx, hy, hz):
    T = colworld.box_tris((0, 0, 0), (hx, hy, hz))
    V = [tuple(v) for v in T.reshape(-1, 3)]
    return V, list(range(len(V)))


def roty(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    # 行向量约定：v' = v·M；绕 Y 轴
    return (c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1)


# ---- 合成地图：地板 100×100（细分成 20×20 网格，跨很多格子）+ x=20 处的墙 + 旋转 45° 的箱子 ----
fv, fi = [], []
N = 20
for i in range(N + 1):
    for j in range(N + 1):
        fv.append((-50 + 100.0 * i / N, 0.0, -50 + 100.0 * j / N))
for i in range(N):
    for j in range(N):
        a = i * (N + 1) + j
        fi += [a, a + 1, a + N + 2, a, a + N + 2, a + N + 1]
data = pack_obj(fv, fi)
wv, wi = box_mesh(1, 15, 50)
data += pack_obj(wv, wi, mat=(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1), pos=(20, 15, 0))   # 墙面 x∈[19,21]
bv, bi = box_mesh(4, 4, 4)
data += pack_obj(bv, bi, mat=roty(45), pos=(-20, 4, -20))

print("== 解析与建网格")
w = ColWorld(cell=16.0)
nobj = w.add_scn_col(data)
w.build()
check(nobj == 3, "scn_col 物体数 3（得到 %d）" % nobj)
st = w.stats()
print("  ", st)
check(st["static_tris"] == 800 + 12 + 12, "静态三角形数 824")

# 旋转箱子的世界顶点与 scncol.world_verts(row) 一致
objs = scncol.parse(data)
ref = np.array(scncol.world_verts(objs[2], "row"))
got = w.st.T[w.st_obj == 2].reshape(-1, 3)
check(np.allclose(np.sort(ref, 0), np.sort(got, 0), atol=1e-5), "旋转物体世界坐标 = scncol.world_verts(row)")

print("== 射线")
h = w.raycast((3, 10, 7), (3, -10, 7))
check(h is not None and abs(h.t - 0.5) < 1e-9 and abs(h.point[1]) < 1e-9 and np.allclose(h.normal, (0, 1, 0)) and h.key == ("s", 0),
      "竖直向下打地板 t=0.5 y=0 法线朝上 键=(s,0)：%r" % h)
h = w.raycast((0, 10, 0), (40, 10, 0))
check(h is not None and abs(h.point[0] - 19) < 1e-6 and np.allclose(h.normal, (-1, 0, 0)) and h.key == ("s", 1),
      "水平打墙 x=19 法线朝 -x：%r" % h)
check(w.raycast((0, 10, 0), (10, 10, 0)) is None, "够不到墙 → None")
h = w.raycast((-20, 2, 0), (-20, 2, -40))       # 箱子绕 Y 45°，角朝 +z，角点在 z=-20+4√2
check(h is not None and abs(h.point[2] - (-20 + 4 * math.sqrt(2))) < 1e-4, "打旋转箱子的棱 z=%.4f" % (h.point[2] if h else float("nan")))

# 对拍：随机线段，网格加速 vs 全量暴力
all_tr = w.st
bad = 0
for _ in range(3000):
    p0 = rng.uniform((-60, -5, -60), (60, 35, 60)); p1 = p0 + rng.normal(0, 30, 3)
    h = w.raycast(p0, p1)
    t = ray_tris(p0, p1 - p0, all_tr)
    tb = t.min()
    if (h is None) != (not np.isfinite(tb)) or (h is not None and abs(h.t - tb) > 1e-9):
        bad += 1
check(bad == 0, "3000 条随机线段与暴力解一致（不一致 %d）" % bad)

print("== 线段-三角形距离（与密集采样对拍）")
worst = 0.0
under = 0
for _ in range(300):
    T = rng.normal(0, 5, (1, 3, 3)); tr = _Tris(T)
    a = rng.normal(0, 6, 3); b = a + rng.normal(0, 4, 3)
    d, PS, PT = seg_tris(a, b, tr)
    s = np.linspace(0, 1, 60)[:, None]
    segp = a + s * (b - a)
    u, v = np.meshgrid(np.linspace(0, 1, 60), np.linspace(0, 1, 60))
    m = (u + v) <= 1
    trip = T[0, 0] + u[m][:, None] * (T[0, 1] - T[0, 0]) + v[m][:, None] * (T[0, 2] - T[0, 0])
    sampled = np.sqrt(((segp[:, None, :] - trip[None]) ** 2).sum(-1)).min()
    if d[0] > sampled + 1e-9:
        under += 1                                        # 精确值不可能比采样值大
    worst = max(worst, sampled - d[0])
    if abs(np.linalg.norm(PS[0] - PT[0]) - d[0]) > 1e-9:
        under += 1
check(under == 0, "精确距离 ≤ 采样最小值，且最近点对的距离 = 返回距离")
check(worst < 0.5, "采样最小值与精确值之差 < 0.5（最大 %.3f，采样步长约 0.1–0.3）" % worst)

print("== 胶囊重叠")
ov = w.capsule_overlap((0, 2, 0), (0, 20, 0), 3.0)
check([k for k, _ in ov] == [("s", 0)] and abs(ov[0][1] - (-1.0)) < 1e-9, "底端离地 2、半径 3 → 只碰地板，穿透 1：%r" % ov)
check(w.capsule_overlap((0, 5, 0), (0, 20, 0), 3.0) == [], "离地 5 → 不碰")
ov = w.capsule_overlap((17, 5, 0), (17, 20, 0), 3.0)
check([k for k, _ in ov] == [("s", 1)], "x=17 半径 3 → 碰墙：%r" % ov)

print("== 胶囊扫掠")
h = w.capsule_sweep((0, 5, 0), (0, 20, 0), 3.0, (40, 0, 0))
check(h is not None and abs(h.t - 0.4) < 1e-3 and np.allclose(h.normal, (-1, 0, 0), atol=1e-6) and h.key == ("s", 1),
      "向 +x 扫 40 → t=0.4（x=16 贴墙），法线 -x：%r" % h)
check(w.capsule_sweep((0, 5, 0), (0, 20, 0), 3.0, (0, 0, 30)) is None, "平行地板扫、离地 2 余量 → 无命中")
h = w.capsule_sweep((0, 2, 0), (0, 20, 0), 3.0, (5, 0, 0))
check(h is not None and h.start_overlap and h.t == 0.0, "起点已压地板 → start_overlap")
h = w.capsule_sweep((0, 10, 0), (0, 20, 0), 3.0, (0, -20, 0))
check(h is not None and abs(h.t - 0.35) < 1e-3 and np.allclose(h.normal, (0, 1, 0), atol=1e-6), "向下落 → t=0.35 落地，法线朝上：%r" % h)

# 对拍：随机扫掠，命中处距离≈r、命中前无重叠；无命中则路径上采样也不重叠
bad = 0
for _ in range(200):
    a = rng.uniform((-45, 3.5, -45), (45, 25, 45)); b = a + np.array([0, rng.uniform(0, 10), 0])
    r = rng.uniform(1, 4)
    if w.capsule_overlap(a, b, r):
        continue
    delta = rng.normal(0, 25, 3)
    h = w.capsule_sweep(a, b, r, delta)
    ts = np.linspace(0, 1 if h is None else max(h.t - 1e-3, 0), 40)
    for t in ts:
        if w.capsule_overlap(a + t * delta, b + t * delta, r, margin=-2e-3):
            bad += 1; break
    if h is not None:
        dd = seg_tris(a + h.t * delta, b + h.t * delta, w.st)[0].min()
        if abs(dd - r) > 2e-3:
            bad += 1
check(bad == 0, "200 次随机扫掠：命中前无重叠、命中时距离=r（问题 %d）" % bad)

print("== 动态体")
w.add_box("pallet1", (10, 5, 0), (0.5, 5, 3))
h = w.raycast((0, 5, 0), (40, 5, 0))
check(h is not None and h.key == "pallet1" and abs(h.point[0] - 9.5) < 1e-9, "射线先打到动态板 x=9.5：%r" % h)
h = w.raycast((0, 5, 0), (40, 5, 0), ignore={"pallet1"})
check(h is not None and h.key == ("s", 1), "ignore 动态板 → 打到墙")
h = w.capsule_sweep((0, 5, 0), (0, 20, 0), 3.0, (40, 0, 0))
check(h is not None and h.key == "pallet1" and abs(h.t - 6.5 / 40) < 1e-3, "胶囊扫到动态板 t=%.4f" % (h.t if h else -1))
w.remove_dynamic("pallet1")
check(w.raycast((0, 5, 0), (40, 5, 0)).key == ("s", 1), "移除后 → 打到墙")

print("== 射线 + 动态体 + 忽略集合（与暴力解对拍）")
w2 = ColWorld(cell=8.0)
w2.add_static(colworld.box_tris((0, -1, 0), (60, 1, 60)), 0); w2.add_static(colworld.box_tris((20, 10, 0), (1, 10, 40)), 1); w2.build()
keys = []
for i in range(60):
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    k = "d%d" % i; keys.append(k)
    if i % 3:
        w2.add_box(k, rng.uniform(-50, 50, 3) * [1, 0.2, 1] + [0, 8, 0], rng.uniform(0.5, 4, 3), q)
    else:
        w2.add_dynamic(k, colworld.capsule_tris(rng.uniform(-50, 50, 3) * [1, 0, 1] + [0, 5, 0],
                                                rng.uniform(-50, 50, 3) * [1, 0, 1] + [0, 15, 0], rng.uniform(1, 3)))
bad = 0
for n in range(1500):
    p0 = rng.uniform((-60, -2, -60), (60, 25, 60)); p1 = p0 + rng.normal(0, 40, 3)
    ign = frozenset(rng.choice(keys, size=rng.integers(0, 10), replace=False)) if n % 2 else frozenset()
    h = w2.raycast(p0, p1, ignore=ign)
    best = min([ray_tris(p0, p1 - p0, w2.st).min()] + [ray_tris(p0, p1 - p0, w2.dyn[k]).min() for k in keys if k not in ign])
    if (h is None) != (not np.isfinite(best)) or (h is not None and abs(h.t - best) > 1e-9):
        bad += 1
check(bad == 0, "1500 条随机线段（60 个动态体、半数带忽略集合）与暴力解一致（不一致 %d）" % bad)

print("\n%s" % ("全部通过" if not FAIL else "失败 %d 项" % len(FAIL)))
sys.exit(1 if FAIL else 0)
