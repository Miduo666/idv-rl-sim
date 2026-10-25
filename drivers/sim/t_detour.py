# -*- coding: utf-8 -*-
"""导航层自测（真实资源）：官方 Detour 载入游戏 .nav/.tile，验证载入、取高度、寻路，并用 .scn_col 交叉检查路径是否穿墙。
用法: t_detour.py [nav 路径] [scn_col 路径] [抽样对数]   资源 zip 同 physx_collision（IDV_RES_ZIP 或默认导出包）"""
import sys, os, random, math, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "natives"))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
import detour, navmesh, colworld, physx_collision

NAV = sys.argv[1] if len(sys.argv) > 1 else "scene/scene_battle/ordnance_factory1/nav/ordnance_factory_test1.nav"
COL = sys.argv[2] if len(sys.argv) > 2 else "scene/scene_battle/ordnance_factory1/nav/ordnance_factory1.scn_col"
N = int(sys.argv[3]) if len(sys.argv) > 3 else 300
FAIL = []


def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok: FAIL.append(msg)


d = detour.scene_detour()
d.add_mesh("ai_t")
t0 = time.time()
check(d.load_mesh("ai_t", NAV), "load_mesh 成功  %s" % detour.LOADED[-1][2])
m = d.meshes["ai_t"]
nb = physx_collision._res_bytes(NAV)
names = navmesh.tile_names(nb)
check(m.ntiles == len(names) and m.bad_tiles == 0, "块数 %d = 块名表 %d，addTile 失败 %d（%.2fs）" % (m.ntiles, len(names), m.bad_tiles, time.time() - t0))
d.set_detour_flag("ai_t", 65531)
d.set_detour_extension("ai_t", (1, 4, 1))

# 多边形中心（由 navmesh.py 独立解析）：最近点应几乎重合、高度应一致
rng = random.Random(0)
tdir = NAV.rsplit("/", 1)[0] + "/" + NAV.rsplit("/", 1)[1][:-4]
centers = []
for tn in names:
    t = navmesh.parse_tile(physx_collision._res_bytes(tdir + "/" + tn))
    for p in t["polys"]:
        # 只取可走区域：flags=0 的多边形（军工厂 AI 导航占 1/3）与 flags≠0 的块内无一条相邻边，是地图外/屋顶等不连通区域，
        # Detour 过滤规则 (flags & include) != 0 永远排除它们（与游戏同库行为一致）
        if p["type"] != 0 or not p["verts"] or not (p["flags"] & 65531): continue
        vs = np.array([t["verts"][i] for i in p["verts"]]); centers.append((tuple(vs.mean(0)), float(np.ptp(vs[:, 1]))))
rng.shuffle(centers)
errs = []
for c, span in centers[:2000]:
    h = d.get_height("ai_t", c[0], c[1] + 0.5, c[2])
    # 参照是多边形顶点的平均高度；斜坡多边形上 Detour 用细节网格的真实高度，容差放宽到竖直跨度的一半
    errs.append((abs(h - c[1]) - span / 2) if h is not None else 1e9)
errs = np.array(errs)
check(np.mean(errs < 0.5) > 0.995, "2000 个多边形中心 get_height 误差 <0.5+跨度/2 的比例 %.4f" % np.mean(errs < 0.5))
centers = [c for c, span in centers]

# 随机点对寻路
w = colworld.ColWorld(); w.add_scn_col(physx_collision._res_bytes(COL)); w.build()
ok = longer = segs = flat = 0
wall = {8: 0, 15: 0, 25: 0}
flat_wall = collections.Counter()           # 平地段（两端高差 <1）上、法线水平（墙而非天花板/地面）的命中，按物体计
t0 = time.time()
for k in range(N):
    a, b = centers[rng.randrange(len(centers))], centers[rng.randrange(len(centers))]
    pts = d.get_path("ai_t", a, b)
    if not pts: continue
    ok += 1
    L = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
    longer += L >= math.dist(a, b) - 1.0
    for i in range(len(pts) - 1):            # 路径段抬高后不应穿过静态墙；分高度统计以区分矮障碍与真墙
        segs += 1
        for hh in wall:
            p0 = np.array([pts[i].x, pts[i].y + hh, pts[i].z]); p1 = np.array([pts[i + 1].x, pts[i + 1].y + hh, pts[i + 1].z])
            hit = w.raycast(p0, p1)
            wall[hh] += hit is not None
            if hh == 8 and abs(pts[i].y - pts[i + 1].y) < 1:
                flat += 1
                if hit is not None and abs(hit.normal[1]) < 0.5:
                    flat_wall[hit.key] += 1
dt = time.time() - t0
check(ok > 0.95 * N, "可走区域随机点对寻路成功 %d/%d（%.2f ms/次，含穿墙检查）" % (ok, N, 1000 * dt / max(N, 1)))
check(longer == ok, "路径长度 ≥ 直线距离：%d/%d" % (longer, ok))
print("     路径段被静态网格挡住的比例（离地 8/15/25）: %s  共 %d 段" % (
    " / ".join("%.3f" % (wall[h] / max(segs, 1)) for h in wall), segs))
nf = sum(flat_wall.values())
print("     平地段离地 8 撞到墙(法线水平) %d/%d，涉及物体 %d 个，最多: %s" % (nf, flat, len(flat_wall), flat_wall.most_common(6)))
# 只作统计、不作通过条件：这是游戏自身两份数据（AI 导航 vs .scn_col）的一致性，不是封装正确性。
# 军工厂实测 ~7%，集中在主厂房(352/355)与两处地下室(343/927)附近，原因待查（门洞/地下室盖板/导航边缘简化），见 SKILL §9.10
print("     （信息）平地段离地 8 撞墙比例 %.3f" % (nf / max(flat, 1)))
print("部分路径(终点不可达)次数:", dict(detour.PARTIAL))

# 回退：未载入的网格查询落到 ai_ 网格
d.add_mesh("tc_t"); check(not d.load_mesh("tc_t", NAV.replace(".nav", "_dynamic.nav")), "缺失的 _dynamic.nav 载入返回 False")
check(d.get_height("tc_t", *centers[0]) is not None and detour.FALLBACK["tc_t"] == 1, "缺失网格回退到 AI 导航并计数")
print("\n全部通过" if not FAIL else "\n失败 %d 项" % len(FAIL))
