# -*- coding: utf-8 -*-
"""在真实地图上校验 colworld：建网格耗时、导航顶点下方的地面命中率（应与 validate_col_nav 的 93.9/96.3/97.6% 同量级）、
沿导航多边形边的胶囊扫掠被挡比例、查询吞吐。
用法: colcheck.py <res_recovered.zip> <scn_col路径> <nav路径> [胶囊半径=3] [抽样数=2000]
例:   colcheck.py ..\\..\\res_pull\\resdump_1025_015456\\res_recovered.zip scene/scene_battle/ordnance_factory1/nav/ordnance_factory1.scn_col <军工厂 server_nav>"""
import sys, os, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import colworld, navmesh

zp, col_path, nav_path = sys.argv[1:4]
R = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
NS = int(sys.argv[5]) if len(sys.argv) > 5 else 2000
rng = np.random.default_rng(0)
z = zipfile.ZipFile(zp)

t0 = time.perf_counter()
w = colworld.ColWorld()
nobj = w.add_scn_col(z.read(col_path))
t1 = time.perf_counter()
w.build()
t2 = time.perf_counter()
print("解析 %.2fs  建网格 %.2fs  物体 %d" % (t1 - t0, t2 - t1, nobj), w.stats())

nav = navmesh.load_nav(z, nav_path)
wh, wr, wc = nav["tiles"][0]["walkable"]
P = np.array([v for t in nav["tiles"] for v in t["verts"]], dtype=np.float64)
S = P[rng.choice(len(P), min(NS, len(P)), replace=False)]
print("导航顶点 %d，抽样 %d；walkable 高 %.1f 半径 %.1f 可攀 %.1f" % (len(P), len(S), wh, wr, wc))

# 1) 地面：从顶点上方 5 竖直往下打 60
t0 = time.perf_counter()
dh = []
for p in S:
    h = w.raycast(p + (0, 5, 0), p - (0, 55, 0))
    dh.append(np.nan if h is None else p[1] - h.point[1])
dt = time.perf_counter() - t0
dh = np.array(dh)
has = ~np.isnan(dh)
print("[地面] 下方有碰撞面 %.1f%%  其中距离<12 %.1f%%  中位距离 %.2f   （竖直射线 %.0f 次/秒）" % (
    100 * has.mean(), 100 * (has & (dh < 12)).mean(), np.nanmedian(dh), len(S) / dt))

# 2) 沿导航多边形的边扫胶囊（离地 wc+R 起，高到 wh），被挡说明可走区里有墙——比例应很低
edges = []
for t in nav["tiles"]:
    V = t["verts"]
    for poly in t["polys"]:
        vs = poly["verts"]
        for i in range(len(vs)):
            edges.append((V[vs[i]], V[vs[(i + 1) % len(vs)]]))
E = np.array(edges, dtype=np.float64)
E = E[rng.choice(len(E), min(NS, len(E)), replace=False)]
lift = wc + R
blocked = start = 0
t0 = time.perf_counter()
for a, b in E:
    lo = a + (0, lift, 0); hi = a + (0, max(wh - R, lift), 0)
    h = w.capsule_sweep(lo, hi, R, b - a)
    if h is not None:
        blocked += 1
        start += h.start_overlap
dt = time.perf_counter() - t0
print("[扫掠] 半径 %.1f，沿 %d 条导航边：被挡 %.1f%%（其中起点就重叠 %.1f%%）  （%.0f 次/秒）" % (
    R, len(E), 100 * blocked / len(E), 100 * start / len(E), len(E) / dt))
print("      注：坡道/台阶会让离地 %.1f 的胶囊蹭到地面，被挡比例不是 0 不代表有错；看与半径的变化趋势。" % lift)
