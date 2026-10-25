# -*- coding: utf-8 -*-
"""只用"几种变换方式下位置不同"的物体的三角形，测导航顶点处的水平净空；墙穿过可行走区 → 近距离命中多。"""
import sys, os, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import scncol, navmesh
from colgeo import horiz_clearance

z = zipfile.ZipFile(sys.argv[1])
objs = scncol.parse(z.read(sys.argv[2]))
nav = navmesh.load_nav(z, sys.argv[3])
P = np.array([v for t in nav["tiles"] for v in t["verts"]], dtype=np.float64)
modes = ("row", "col", "none")
diff = []
for o in objs:
    bbs = []
    for m in modes:
        W = np.array(scncol.world_verts(o, m)); bbs.append((W.min(0), W.max(0)))
    if not all(np.abs(bbs[0][0] - b[0]).max() < 2 and np.abs(bbs[0][1] - b[1]).max() < 2 for b in bbs[1:]):
        diff.append(o)
print("差异物体", len(diff))
for m in modes:
    T = []
    for o in diff:
        wv = scncol.world_verts(o, m)
        for i in range(0, len(o.idx), 3):
            T.append((wv[o.idx[i]], wv[o.idx[i + 1]], wv[o.idx[i + 2]]))
    T = np.array(T)
    hc = horiz_clearance(T, P)
    print("[%-4s] tris=%d  净空<2: %d  <4: %d  <6: %d" % (m, len(T), (hc < 2).sum(), (hc < 4).sum(), (hc < 6).sum()))
