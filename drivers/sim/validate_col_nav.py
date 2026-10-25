# -*- coding: utf-8 -*-
"""用导航网格校验碰撞解析：导航顶点正下方(容差内)应有碰撞面。比较矩阵的行/列两种约定。
用法: validate_col_nav.py <res_recovered.zip> <scn_col路径> <nav路径>"""
import sys, os, zipfile, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import scncol, navmesh

z = zipfile.ZipFile(sys.argv[1])
objs = scncol.parse(z.read(sys.argv[2]))
nav = navmesh.load_nav(z, sys.argv[3])
print("nav params", nav["params"], "tiles", nav["ntiles"], "loaded", len(nav["tiles"]),
      "walkable(h,r,climb)", nav["tiles"][0]["walkable"])
pts = np.array([v for t in nav["tiles"] for v in t["verts"]], dtype=np.float64)
print("nav verts", len(pts), "bounds", pts.min(0).round(1), pts.max(0).round(1))


def build(mode):
    T = []
    rotated = 0
    for o in objs:
        wv = scncol.world_verts(o, mode)
        if any(abs(o.mat[i] - (1 if i in (0, 5, 10, 15) else 0)) > 1e-4 for i in range(16)):
            rotated += 1
        for i in range(0, len(o.idx), 3):
            T.append((wv[o.idx[i]], wv[o.idx[i + 1]], wv[o.idx[i + 2]]))
    return np.array(T, dtype=np.float64), rotated


def heights_below(T, P, cell=32.0):
    """对每个点做竖直射线，返回 点.y - 最近的下方(含上方 5 内)碰撞面高度；没有则 nan。"""
    mn = T.min(1); mx = T.max(1)
    grid = collections.defaultdict(list)
    for k in range(len(T)):
        for gx in range(int(mn[k, 0] // cell), int(mx[k, 0] // cell) + 1):
            for gz in range(int(mn[k, 2] // cell), int(mx[k, 2] // cell) + 1):
                grid[(gx, gz)].append(k)
    out = np.full(len(P), np.nan)
    for j, (x, y, zc) in enumerate(P):
        ks = grid.get((int(x // cell), int(zc // cell)))
        if not ks: continue
        A = T[ks, 0]; B = T[ks, 1]; C = T[ks, 2]
        # 2D 重心坐标 (x,z)
        v0 = C[:, [0, 2]] - A[:, [0, 2]]; v1 = B[:, [0, 2]] - A[:, [0, 2]]; v2 = np.array([x, zc]) - A[:, [0, 2]]
        d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1)
        d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
        den = d00 * d11 - d01 * d01
        ok = np.abs(den) > 1e-9
        u = np.where(ok, (d11 * d20 - d01 * d21) / np.where(ok, den, 1), -1)
        v = np.where(ok, (d00 * d21 - d01 * d20) / np.where(ok, den, 1), -1)
        inside = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6)
        if not inside.any(): continue
        h = A[:, 1] + u * (C[:, 1] - A[:, 1]) + v * (B[:, 1] - A[:, 1])
        h = h[inside]
        cand = h[h <= y + 5.0]
        if len(cand):
            out[j] = y - cand.max()
    return out


def horiz_clearance(T, P, height=12.0, R=20.0, ndir=8, cell=32.0):
    """在 点.y+height 处向 ndir 个水平方向打长度 R 的射线，返回最近命中距离（无命中=R）。"""
    mn = T.min(1); mx = T.max(1)
    grid = collections.defaultdict(list)
    for k in range(len(T)):
        for gx in range(int((mn[k, 0] - R) // cell), int((mx[k, 0] + R) // cell) + 1):
            for gz in range(int((mn[k, 2] - R) // cell), int((mx[k, 2] + R) // cell) + 1):
                grid[(gx, gz)].append(k)
    dirs = [np.array([np.cos(a), 0.0, np.sin(a)]) for a in np.linspace(0, 2 * np.pi, ndir, endpoint=False)]
    out = np.full(len(P), R)
    for j, (x, y, zc) in enumerate(P):
        ks = grid.get((int(x // cell), int(zc // cell)))
        if not ks: continue
        A = T[ks, 0]; E1 = T[ks, 1] - A; E2 = T[ks, 2] - A
        o = np.array([x, y + height, zc])
        best = R
        for dvec in dirs:
            pv = np.cross(dvec, E2); det = (E1 * pv).sum(1)
            ok = np.abs(det) > 1e-9
            inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
            tv = o - A
            u = (tv * pv).sum(1) * inv
            qv = np.cross(tv, E1)
            v = (qv * dvec).sum(1) * inv
            t = (E2 * qv).sum(1) * inv
            hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-4) & (t < best)
            if hit.any():
                best = t[hit].min()
        out[j] = best
    return out


for mode in ("row", "col"):
    T, rotated = build(mode)
    dh = heights_below(T, pts)
    has = ~np.isnan(dh)
    near = has & (dh < 12)
    hc = horiz_clearance(T, pts)
    print("[%s] tris=%d rotated_objs=%d  有下方碰撞面 %.1f%%  其中距离<12: %.1f%%  中位距离 %.2f" % (
        mode, len(T), rotated, 100 * has.mean(), 100 * near.mean(), np.nanmedian(dh)))
    print("      水平净空: <2 的顶点 %.2f%%  <4 的 %.2f%%  <6 的 %.2f%%  (导航收缩半径=6)" % (
        100 * (hc < 2).mean(), 100 * (hc < 4).mean(), 100 * (hc < 6).mean()))
