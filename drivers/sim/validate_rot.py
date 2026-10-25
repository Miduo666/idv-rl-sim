# -*- coding: utf-8 -*-
"""只看两种矩阵约定下占地(xz 包围盒)明显不同的物体：统计落进物体水平占地、且高度在物体竖直范围内的导航顶点数。
导航顶点不该在实体内部 → 侵入少的约定是对的。"""
import sys, os, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import scncol, navmesh

z = zipfile.ZipFile(sys.argv[1])
objs = scncol.parse(z.read(sys.argv[2]))
nav = navmesh.load_nav(z, sys.argv[3])
P = np.array([v for t in nav["tiles"] for v in t["verts"]], dtype=np.float64)


def inside_count(o, mode):
    W = np.array(scncol.world_verts(o, mode))
    mn, mx = W.min(0), W.max(0)
    if mx[1] - mn[1] < 15:          # 太矮的(台阶/地面)不算
        return 0, (mn, mx)
    sel = (P[:, 0] > mn[0] + 1) & (P[:, 0] < mx[0] - 1) & (P[:, 2] > mn[2] + 1) & (P[:, 2] < mx[2] - 1) & \
          (P[:, 1] > mn[1] + 2) & (P[:, 1] < mx[1] - 2)
    return int(sel.sum()), (mn, mx)


modes = ("row", "col", "none")
tot = {m: 0 for m in modes}
diff_objs = 0
votes = {m: 0 for m in modes}; votes["tie"] = 0
for o in objs:
    res = {m: inside_count(o, m) for m in modes}
    bbs = [res[m][1] for m in modes]
    if all(np.abs(bbs[0][0] - b[0]).max() < 2 and np.abs(bbs[0][1] - b[1]).max() < 2 for b in bbs[1:]):
        continue
    diff_objs += 1
    for m in modes: tot[m] += res[m][0]
    best = min(res[m][0] for m in modes)
    winners = [m for m in modes if res[m][0] == best]
    votes[winners[0] if len(winners) == 1 else "tie"] += 1
print("各约定占地不同的物体: %d" % diff_objs)
print("侵入的导航顶点总数:", tot)
print("逐物体投票(侵入最少者胜):", votes)
