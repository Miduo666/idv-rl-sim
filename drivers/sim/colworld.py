# -*- coding: utf-8 -*-
"""碰撞内核（只依赖 numpy）：静态三角网格(.scn_col) + 动态体(板/窗/门/角色，统一表示成三角形) 上的
射线、胶囊重叠、胶囊扫掠。只管几何，不管游戏接口；physx_collision.scene_col 的参数/返回值适配另做（要先从调用处反推）。

    w = ColWorld(); w.add_scn_col(open(p, "rb").read()); w.build()
    w.raycast(p0, p1)                    -> Hit 或 None（线段 p0→p1 上最近的命中）
    w.capsule_overlap(a, b, r)           -> [(物体键, 距离)]（胶囊 = 线段 a-b 加半径 r）
    w.capsule_sweep(a, b, r, delta)      -> Hit 或 None（胶囊平移 delta，Hit.t 是可走的比例）
物体键：静态物体 = ("s", scn_col 里的物体序号)；动态体 = add_dynamic 时给的键。
坐标约定同 scncol.world_verts(row)（§9.7 判定为行向量约定）。为什么不用 pybullet：Windows + Python 3.11 没有预编译包，
要装 MSVC 现编，而且它的 Python 接口没有凸体扫掠；这里的接口留着，以后要换后端只换本文件。"""
import numpy as np

EPS = 1e-9


class Hit(object):
    __slots__ = ("t", "point", "normal", "key", "tri", "start_overlap")

    def __init__(self, t, point, normal, key, tri, start_overlap=False):
        self.t, self.point, self.normal, self.key, self.tri = t, point, normal, key, tri
        self.start_overlap = start_overlap       # 扫掠：起点就已重叠（t=0）

    def __repr__(self):
        return "<Hit t=%.4f p=%s n=%s key=%r%s>" % (self.t, np.round(self.point, 3), np.round(self.normal, 3),
                                                   self.key, " start_overlap" if self.start_overlap else "")


class _Tris(object):
    """一组三角形的预计算量。"""

    def __init__(self, T):
        T = np.asarray(T, dtype=np.float64).reshape(-1, 3, 3)
        self.T = T
        self.A, self.B, self.C = T[:, 0], T[:, 1], T[:, 2]
        self.E1, self.E2 = self.B - self.A, self.C - self.A
        n = np.cross(self.E1, self.E2)
        ln = np.linalg.norm(n, axis=1)
        self.ok = ln > 1e-12                      # 退化三角形：射线不测，距离只按边算
        self.N = n / np.where(self.ok, ln, 1.0)[:, None]
        self.mn, self.mx = T.min(1), T.max(1)

    def __len__(self):
        return len(self.T)

    def sub(self, ks):
        s = _Tris.__new__(_Tris)
        for f in ("T", "A", "B", "C", "E1", "E2", "ok", "N", "mn", "mx"):
            setattr(s, f, getattr(self, f)[ks])
        return s


# ---------------- 向量化几何（对一组三角形） ----------------

def ray_tris(p0, d, tr):
    """线段 p0 + t·d (t∈[0,1]) 与每个三角形求交（Möller–Trumbore），不相交为 inf。"""
    pv = np.cross(d, tr.E2)
    det = (tr.E1 * pv).sum(1)
    ok = tr.ok & (np.abs(det) > EPS)
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    tv = p0 - tr.A
    u = (tv * pv).sum(1) * inv
    qv = np.cross(tv, tr.E1)
    v = (qv @ d) * inv
    t = (tr.E2 * qv).sum(1) * inv
    hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t >= 0) & (t <= 1)
    return np.where(hit, t, np.inf)


def _clip01(x):
    return np.clip(x, 0.0, 1.0)


def _seg_seg(p1, d1, P2, D2):
    """固定线段 p1+s·d1 与一组线段 P2+t·D2 的最近点（Ericson 5.1.9）。返回 (线段1上的点, 线段2上的点)，形状 (n,3)。"""
    r = p1 - P2
    a = float(d1 @ d1)
    e = (D2 * D2).sum(1)
    f = (D2 * r).sum(1)
    n = len(P2)
    eok = e > EPS
    if a <= EPS:
        s = np.zeros(n)
        t = np.where(eok, _clip01(f / np.where(eok, e, 1.0)), 0.0)
    else:
        c = r @ d1
        b = D2 @ d1
        den = a * e - b * b
        s = np.where(den > EPS, _clip01((b * f - c * e) / np.where(den > EPS, den, 1.0)), 0.0)
        t = np.where(eok, (b * s + f) / np.where(eok, e, 1.0), 0.0)
        lo, hi = t < 0, t > 1
        s = np.where(lo, _clip01(-c / a), np.where(hi, _clip01((b - c) / a), s))
        t = np.where(eok, _clip01(t), 0.0)
        s = np.where(eok, s, _clip01(-c / a))
    return p1 + s[:, None] * d1, P2 + t[:, None] * D2


def _pt_seg(P, A, D):
    """点 P(3,) 到一组线段 A+t·D 的最近点。"""
    e = (D * D).sum(1)
    t = np.where(e > EPS, _clip01(((P - A) * D).sum(1) / np.where(e > EPS, e, 1.0)), 0.0)
    return A + t[:, None] * D


def _pt_tris(P, tr):
    """点 P 到每个三角形的最近点 (n,3)：投影在三角形内取投影点，否则取三条边上最近者。"""
    dpl = ((P - tr.A) * tr.N).sum(1)
    Q = P - dpl[:, None] * tr.N
    c0 = (np.cross(tr.B - tr.A, Q - tr.A) * tr.N).sum(1)
    c1 = (np.cross(tr.C - tr.B, Q - tr.B) * tr.N).sum(1)
    c2 = (np.cross(tr.A - tr.C, Q - tr.C) * tr.N).sum(1)
    inside = tr.ok & (c0 >= 0) & (c1 >= 0) & (c2 >= 0)
    best = Q.copy()
    bd = np.full(len(tr), np.inf)
    bd[inside] = np.abs(dpl[inside])
    for A_, B_ in ((tr.A, tr.B), (tr.B, tr.C), (tr.C, tr.A)):
        q = _pt_seg(P, A_, B_ - A_)
        dq = np.linalg.norm(P - q, axis=1)
        m = ~inside & (dq < bd)
        best[m] = q[m]
        bd[m] = dq[m]
    return best


def seg_tris(a, b, tr):
    """线段 a-b 到每个三角形的距离与最近点对。返回 (dist(n,), 线段上的点(n,3), 三角形上的点(n,3))。
    最近点对只可能是：线段端点对三角形 / 线段对三条边 / 线段穿过三角形(距离 0)，逐项取最小，是精确值。"""
    d = b - a
    n = len(tr)
    bd = np.full(n, np.inf)
    PS = np.zeros((n, 3))
    PT = np.zeros((n, 3))

    def take(ps, pt):
        dd = np.linalg.norm(ps - pt, axis=1)
        m = dd < bd
        bd[m] = dd[m]; PS[m] = ps[m]; PT[m] = pt[m]

    for P in (a, b):
        take(np.broadcast_to(P, (n, 3)), _pt_tris(P, tr))
    for A_, B_ in ((tr.A, tr.B), (tr.B, tr.C), (tr.C, tr.A)):
        take(*_seg_seg(a, d, A_, B_ - A_))
    t = ray_tris(a, d, tr)
    x = np.isfinite(t)
    if x.any():
        ip = a + t[x, None] * d
        bd[x] = 0.0; PS[x] = ip; PT[x] = ip
    return bd, PS, PT


def box_tris(center, half, rot=None):
    """有向包围盒 → 12 个三角形。rot: 3×3，行向量约定（局部点 v → v·rot + center）。"""
    hx, hy, hz = half
    c = np.array([[sx * hx, sy * hy, sz * hz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], dtype=np.float64)
    if rot is not None:
        c = c @ np.asarray(rot, dtype=np.float64)
    c = c + np.asarray(center, dtype=np.float64)
    F = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
         (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return c[np.array(F)]


# ---------------- 世界 ----------------

class ColWorld(object):
    def __init__(self, cell=16.0):
        self.cell = float(cell)
        self._static = []          # [(三角形 (n,3,3), 物体序号)]
        self._nobj = 0             # 已加入的 scn_col 物体数（多个文件时序号接着排）
        self.st = None             # 静态 _Tris
        self.st_obj = None         # 每个静态三角形所属的 scn_col 物体序号
        self.dyn = {}              # 键 -> _Tris
        self._dyn_all = None       # (合并后的 _Tris, 每个三角形的键)；动态体变化时作废

    # ---- 建立 ----
    def add_scn_col(self, data, mode="row"):
        import scncol
        objs = scncol.parse(data)
        base, self._nobj = self._nobj, self._nobj + len(objs)
        for i, o in enumerate(objs):
            if not o.idx:
                continue
            wv = np.asarray(scncol.world_verts(o, mode), dtype=np.float64)
            self._static.append((wv[np.asarray(o.idx).reshape(-1, 3)], base + i))
        return len(objs)

    def add_static(self, T, obj_id):
        self._static.append((np.asarray(T, dtype=np.float64).reshape(-1, 3, 3), obj_id))

    def build(self):
        if self._static:
            T = np.concatenate([t for t, _ in self._static])
            self.st_obj = np.concatenate([np.full(len(t), i, dtype=np.int64) for t, i in self._static])
        else:
            T = np.zeros((0, 3, 3)); self.st_obj = np.zeros(0, dtype=np.int64)
        self.st = _Tris(T)
        self._build_grid()
        return self

    def _build_grid(self):
        """XZ 平面均匀网格，CSR 存每格的三角形号。"""
        T, c = self.st.T, self.cell
        if not len(T):
            self.g0 = np.zeros(2); self.gn = (1, 1)
            self.g_off = np.zeros(2, dtype=np.int64); self.g_tri = np.zeros(0, dtype=np.int64)
            return
        xz = T[:, :, [0, 2]]
        mn, mx = xz.min(1), xz.max(1)
        self.g0 = mn.min(0)
        lo = np.floor((mn - self.g0) / c).astype(np.int64)
        hi = np.floor((mx - self.g0) / c).astype(np.int64)
        NX, NZ = int(hi[:, 0].max()) + 1, int(hi[:, 1].max()) + 1
        self.gn = (NX, NZ)
        w = hi[:, 0] - lo[:, 0] + 1
        cnt = w * (hi[:, 1] - lo[:, 1] + 1)
        k = np.repeat(np.arange(len(T)), cnt)
        loc = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        gx = lo[k, 0] + loc % w[k]
        gz = lo[k, 1] + loc // w[k]
        cell_id = gx * NZ + gz
        order = np.argsort(cell_id, kind="stable")
        self.g_tri = k[order]
        self.g_off = np.concatenate([[0], np.cumsum(np.bincount(cell_id, minlength=NX * NZ))])

    # ---- 动态体 ----
    def add_dynamic(self, key, T):
        self.dyn[key] = _Tris(T)
        self._dyn_all = None

    def add_box(self, key, center, half, rot=None):
        self.add_dynamic(key, box_tris(center, half, rot))

    def remove_dynamic(self, key):
        if self.dyn.pop(key, None) is not None:
            self._dyn_all = None

    def _dyn_merged(self):
        if self._dyn_all is None:
            keys = list(self.dyn)
            if keys:
                tr = _Tris(np.concatenate([self.dyn[k].T for k in keys]))
                owner = [k for k in keys for _ in range(len(self.dyn[k]))]
            else:
                tr, owner = _Tris(np.zeros((0, 3, 3))), []
            self._dyn_all = (tr, owner)
        return self._dyn_all

    # ---- 候选三角形 ----
    def _cells_rect(self, mn, mx):
        c, (NX, NZ) = self.cell, self.gn
        lo = np.floor((np.asarray(mn) - self.g0) / c).astype(np.int64)
        hi = np.floor((np.asarray(mx) - self.g0) / c).astype(np.int64)
        lo = np.maximum(lo, 0); hi = np.minimum(hi, (NX - 1, NZ - 1))
        if (hi < lo).any():
            return np.zeros(0, dtype=np.int64)
        gx, gz = np.meshgrid(np.arange(lo[0], hi[0] + 1), np.arange(lo[1], hi[1] + 1), indexing="ij")
        return (gx * NZ + gz).ravel()

    def _cells_segment(self, p0, p1):
        """线段在 XZ 上经过的格子（Amanatides–Woo 2D 遍历）。"""
        c, (NX, NZ) = self.cell, self.gn
        a = (np.array([p0[0], p0[2]]) - self.g0) / c
        b = (np.array([p1[0], p1[2]]) - self.g0) / c
        d = b - a
        cur = np.floor(a).astype(np.int64)
        end = np.floor(b).astype(np.int64)
        step = np.where(d > 0, 1, -1)
        with np.errstate(divide="ignore", invalid="ignore"):
            tdel = np.where(d != 0, np.abs(1.0 / d), np.inf)
            nxt = np.where(d > 0, cur + 1 - a, a - cur)
            tmax = np.where(d != 0, nxt * tdel, np.inf)
        out = []
        for _ in range(int(np.abs(end - cur).sum()) + 1):
            if 0 <= cur[0] < NX and 0 <= cur[1] < NZ:
                out.append(cur[0] * NZ + cur[1])
            ax = 0 if tmax[0] < tmax[1] else 1
            if tmax[ax] > 1.0:
                break
            cur[ax] += step[ax]
            tmax[ax] += tdel[ax]
        return np.asarray(out, dtype=np.int64)

    def _tris_in(self, cells):
        if not len(cells):
            return np.zeros(0, dtype=np.int64)
        s, e = self.g_off[cells], self.g_off[cells + 1]
        if (e - s).sum() == 0:
            return np.zeros(0, dtype=np.int64)
        return np.unique(np.concatenate([self.g_tri[i:j] for i, j in zip(s, e) if j > i]))

    def _candidates(self, ks, ignore):
        """(静态子集, 静态键, 动态 _Tris, 动态键)；ignore 是不参与的动态体键集合。"""
        st = self.st.sub(ks)
        skeys = [("s", int(i)) for i in self.st_obj[ks]]
        dtr, owner = self._dyn_merged()
        if ignore and owner:
            m = np.array([o not in ignore for o in owner])
            dtr = dtr.sub(np.nonzero(m)[0]); owner = [o for o, keep in zip(owner, m) if keep]
        return st, skeys, dtr, owner

    # ---- 查询 ----
    def raycast(self, p0, p1, ignore=()):
        """线段 p0→p1 上最近的命中；法线朝向射线起点一侧（三角形绕序没有约定，见文件头）。"""
        p0 = np.asarray(p0, dtype=np.float64); p1 = np.asarray(p1, dtype=np.float64)
        d = p1 - p0
        st, skeys, dtr, owner = self._candidates(self._tris_in(self._cells_segment(p0, p1)), ignore)
        best = None
        for tr, keys in ((st, skeys), (dtr, owner)):
            if not len(tr):
                continue
            t = ray_tris(p0, d, tr)
            i = int(np.argmin(t))
            if np.isfinite(t[i]) and (best is None or t[i] < best[0]):
                best = (float(t[i]), tr.N[i], keys[i], i)
        if best is None:
            return None
        t, n, key, i = best
        if n @ d > 0:
            n = -n
        return Hit(t, p0 + t * d, n.copy(), key, i)

    def _box_query(self, lo, hi, ignore):
        """包围盒 [lo,hi] 内（按三角形的 3D 包围盒判）的候选：先按格子，再按包围盒细筛。"""
        ks = self._tris_in(self._cells_rect(lo[[0, 2]], hi[[0, 2]]))
        if len(ks):
            ks = ks[np.all((self.st.mx[ks] >= lo) & (self.st.mn[ks] <= hi), axis=1)]
        st, skeys, dtr, owner = self._candidates(ks, ignore)
        if len(dtr):
            m = np.nonzero(np.all((dtr.mx >= lo) & (dtr.mn <= hi), axis=1))[0]
            dtr = dtr.sub(m); owner = [owner[i] for i in m]
        return [(tr, keys) for tr, keys in ((st, skeys), (dtr, owner)) if len(tr)]

    def capsule_overlap(self, a, b, r, ignore=(), margin=0.0):
        """与胶囊(线段 a-b, 半径 r)重叠的物体：[(键, 最近距离-r)]，按穿透深度从深到浅。"""
        a = np.asarray(a, dtype=np.float64); b = np.asarray(b, dtype=np.float64)
        pad = max(r + margin, 0.0)
        res = {}
        for tr, keys in self._box_query(np.minimum(a, b) - pad, np.maximum(a, b) + pad, ignore):
            dist = seg_tris(a, b, tr)[0]
            for i in np.nonzero(dist < r + margin)[0]:
                k = keys[i]
                res[k] = min(res.get(k, np.inf), float(dist[i]) - r)
        return sorted(res.items(), key=lambda kv: kv[1])

    def capsule_sweep(self, a, b, r, delta, ignore=(), skin=1e-3, max_iter=64):
        """胶囊平移 delta 的首次接触（保守推进：每步按当前最近距离前进，平移下距离的减小速度不超过 |delta|）。
        返回 Hit：t = 接触前可走的比例，point = 接触点(三角形上)，normal = 从接触点指向胶囊。起点已重叠时 t=0、start_overlap。"""
        a = np.asarray(a, dtype=np.float64); b = np.asarray(b, dtype=np.float64)
        delta = np.asarray(delta, dtype=np.float64)
        L = float(np.linalg.norm(delta))
        lo = np.minimum(a, b) + np.minimum(delta, 0) - r
        hi = np.maximum(a, b) + np.maximum(delta, 0) + r
        groups = self._box_query(lo, hi, ignore)
        if not groups:
            return None

        def nearest(off, prune=None):
            best = (np.inf, None, None, None, None)
            kept = []
            for tr, keys in groups:
                dist, PS, PT = seg_tris(a + off, b + off, tr)
                i = int(np.argmin(dist))
                if dist[i] < best[0]:
                    best = (float(dist[i]), PS[i], PT[i], keys[i], (tr, i))
                if prune is not None:          # 起点距离 > r + 位移长度的三角形整段都碰不到，后续迭代不再算
                    m = np.nonzero(dist <= prune)[0]
                    if len(m):
                        kept.append((tr.sub(m), [keys[j] for j in m]))
            if prune is not None:
                groups[:] = kept
            return best

        t = 0.0
        dist, ps, pt, key, ti = nearest(np.zeros(3), prune=r + L + skin)
        if dist < r - skin:
            return Hit(0.0, pt, self._normal(ps, pt, ti, a, b), key, ti[1], start_overlap=True)
        if L < EPS:
            return None
        for _ in range(max_iter):
            gap = dist - r
            if gap <= skin:
                return Hit(t, pt, self._normal(ps, pt, ti, a + t * delta, b + t * delta), key, ti[1])
            t += gap / L
            if t >= 1.0:
                # 终点处再看一眼：保守推进越过 1 说明整段都没碰到
                return None
            dist, ps, pt, key, ti = nearest(t * delta)
        return Hit(t, pt, self._normal(ps, pt, ti, a + t * delta, b + t * delta), key, ti[1])

    @staticmethod
    def _normal(ps, pt, ti, a, b):
        v = ps - pt
        ln = np.linalg.norm(v)
        if ln > 1e-9:
            return v / ln
        tr, i = ti                       # 线段已插进三角形：用面法线，朝向胶囊中点一侧
        n = tr.N[i].copy()
        if n @ ((a + b) / 2 - pt) < 0:
            n = -n
        return n

    def stats(self):
        NX, NZ = self.gn
        per = np.diff(self.g_off)
        return {"static_tris": len(self.st), "dynamic": len(self.dyn), "grid": (NX, NZ), "cell": self.cell,
                "tris_per_cell_mean": float(per[per > 0].mean()) if (per > 0).any() else 0.0,
                "tris_per_cell_max": int(per.max()) if len(per) else 0}
