# -*- coding: utf-8 -*-
"""三角网格上的简单射线查询（numpy + 均匀网格加速），用于离线校验碰撞/导航。T: (n,3,3) 世界坐标三角形。"""
import collections
import numpy as np


def _grid(T, cell, pad=0.0):
    mn = T.min(1); mx = T.max(1)
    grid = collections.defaultdict(list)
    for k in range(len(T)):
        for gx in range(int((mn[k, 0] - pad) // cell), int((mx[k, 0] + pad) // cell) + 1):
            for gz in range(int((mn[k, 2] - pad) // cell), int((mx[k, 2] + pad) // cell) + 1):
                grid[(gx, gz)].append(k)
    return grid


def heights_below(T, P, cell=32.0, above=5.0):
    """每个点做竖直射线：返回 点.y - 下方(允许高出 above)最近碰撞面高度；没有则 nan。"""
    grid = _grid(T, cell)
    out = np.full(len(P), np.nan)
    for j, (x, y, zc) in enumerate(P):
        ks = grid.get((int(x // cell), int(zc // cell)))
        if not ks: continue
        A = T[ks, 0]; B = T[ks, 1]; C = T[ks, 2]
        v0 = C[:, [0, 2]] - A[:, [0, 2]]; v1 = B[:, [0, 2]] - A[:, [0, 2]]; v2 = np.array([x, zc]) - A[:, [0, 2]]
        d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1)
        d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
        den = d00 * d11 - d01 * d01
        ok = np.abs(den) > 1e-9
        u = np.where(ok, (d11 * d20 - d01 * d21) / np.where(ok, den, 1), -1)
        v = np.where(ok, (d00 * d21 - d01 * d20) / np.where(ok, den, 1), -1)
        inside = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6)
        if not inside.any(): continue
        h = (A[:, 1] + u * (C[:, 1] - A[:, 1]) + v * (B[:, 1] - A[:, 1]))[inside]
        cand = h[h <= y + above]
        if len(cand):
            out[j] = y - cand.max()
    return out


def horiz_clearance(T, P, height=12.0, R=20.0, ndir=8, cell=32.0):
    """在 点.y+height 处向 ndir 个水平方向打长度 R 的射线，返回最近命中距离（无命中=R）。"""
    grid = _grid(T, cell, pad=R)
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
