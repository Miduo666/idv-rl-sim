# -*- coding: utf-8 -*-
"""NeoX 原生导航对象 room.scene.scene_detour 的替代：官方 Detour v1.6.0（natives/detour_c，ctypes 调用）。
接口按 core/NavManager.py 的调用处（SKILL §9.10）：
  add_mesh(名) / remove_mesh(名) / load_mesh(名, .nav 路径[, 偏移]) -> bool
  set_detour_flag(名, include_flags)          set_detour_extension(名, vector 半尺寸)
  get_height(名, x, y, z) -> float|None       get_vertical_height(名, x, y, z, floor_flag) -> float|None
  get_nearest_nav_point(名, pos, extent) / find_nearest_poly(名, pos, half) -> vector|None
  get_path(名, s, e[, poly_search]) -> [vector]|None        get_path_with_flag(...) -> ([vector], [flag])|(None, None)
  get_poly_ref(名, bmin, bmax, n) / find_polys_around_circle(名, c, r) -> [ref]
  set_poly_flag(名, ref, flag) / get_poly_flag(名, ref)     get_layer_nav_points(名, pos, extent, …) -> (vector, …)
  tilecache 障碍 add_*_obstacle / remove_* / update_navmesh：NavManager 只在 tc_init_done 时调用，现阶段 tilecache 未载入 -> 空操作计数
.nav = Detour MSET 总表（magic 'TESM'，orig/tileW/tileH/maxTiles/maxPolys + 块名表），块文件 <nav目录>/<nav名>/<x_y_layer>.tile
= [i32 -1][i32 长度] + 标准 Detour tile（= Recast 示例的 NavMeshTileHeader{tileRef, dataSize}，SKILL §9.7）。

缺资源的网格（导出包里没有：普通导航 <场景>/nav/<场景名>.nav、tilecache 的 *_dynamic.nav）载入失败后，查询回退到同场景已载入的 AI 导航（名字 ai_ 开头），
计入 FALLBACK。依据：NavManager.set_poly_flag/get_poly_flag/get_detour_path_check_flag 在 tilecache 未载入时自己就把 NAV_MESH_TILECACHE 换成 NAV_MESH_AI。
普通导航回退是近似（没有这条依据），环境变量 SIM_NAV_FALLBACK=0 关闭回退。"""
import os, sys, struct, ctypes, collections
import simenv
from math3d import vector

QUERIES = collections.Counter()
FALLBACK = collections.Counter()          # 网格名 -> 回退次数
UNIMPL = collections.Counter()            # 推断实现 / 空操作的接口调用次数
PARTIAL = collections.Counter()           # 终点不可达、路径止于最近处
LOADED = []                               # [(网格名, 路径, 块数 或 错误)]
USE_FALLBACK = os.environ.get("SIM_NAV_FALLBACK", "1") != "0"
MAX_PTS = 512
F3 = ctypes.c_float * 3

_lib = None


def lib():
    global _lib
    if _lib is None:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
        p = os.path.join(d, "detour_c.dll" if sys.platform == "win32" else "libdetour_c.so")
        if not os.path.exists(p):
            raise RuntimeError("缺 %s：先运行 natives/detour_c/build.py" % p)
        L = ctypes.CDLL(p)
        vp, f, i, u, us, fp = ctypes.c_void_p, ctypes.c_float, ctypes.c_int, ctypes.c_uint, ctypes.c_ushort, ctypes.POINTER(ctypes.c_float)
        L.dn_create.restype = vp; L.dn_create.argtypes = [fp, f, f, i, i, i, ctypes.POINTER(u)]
        L.dn_destroy.argtypes = [vp]
        L.dn_add_tile.restype = u; L.dn_add_tile.argtypes = [vp, ctypes.c_char_p, i]
        L.dn_nearest.argtypes = [vp, fp, fp, us, us, fp, ctypes.POINTER(u)]
        L.dn_path.argtypes = [vp, fp, fp, fp, us, us, fp, ctypes.POINTER(us), i, ctypes.POINTER(i)]
        L.dn_query_box.argtypes = [vp, fp, fp, us, us, ctypes.POINTER(u), i]
        L.dn_circle.argtypes = [vp, fp, f, fp, us, us, ctypes.POINTER(u), i]
        L.dn_poly_height.argtypes = [vp, u, fp, fp]
        L.dn_poly_height_legacy.argtypes = [vp, u, fp, fp]
        L.dn_closest_on_poly.argtypes = [vp, u, fp, fp]
        L.dn_set_flags.argtypes = [vp, u, us]
        L.dn_get_flags.argtypes = [vp, u, ctypes.POINTER(us)]
        L.dn_tile_count.argtypes = [vp]
        _lib = L
    return _lib


def _v3(p):
    return F3(float(p[0]), float(p[1]), float(p[2])) if isinstance(p, (tuple, list)) else F3(float(p.x), float(p.y), float(p.z))


class NavMesh(object):
    """一份已载入的 Detour 网格 + 查询过滤/搜索范围。坐标进出时按 offset 平移（load_mesh 的第 3 个参数）。"""

    def __init__(self, nav_bytes, tile_bytes, offset=(0.0, 0.0, 0.0), max_nodes=8192):
        magic, ver, ntiles = struct.unpack_from("<4sii", nav_bytes, 0)
        if magic != b"TESM":
            raise ValueError("不是 MSET 导航总表: %r" % magic)
        orig = struct.unpack_from("<3f", nav_bytes, 12)
        tw, th = struct.unpack_from("<2f", nav_bytes, 24)
        mt, mp = struct.unpack_from("<2i", nav_bytes, 32)
        st = ctypes.c_uint(0)
        self.h = lib().dn_create(F3(*orig), tw, th, mt, mp, max_nodes, ctypes.byref(st))
        if not self.h:
            raise RuntimeError("dtNavMesh.init 失败 status=0x%x" % st.value)
        bad = 0
        self.walkable_radius = None     # dtMeshHeader.walkableRadius（数据偏移 64），取第一个分块的
        for b in tile_bytes:
            n = struct.unpack_from("<i", b, 4)[0] if b[:4] != b"VAND" else len(b)
            data = b[8:8 + n] if b[:4] != b"VAND" else b
            if self.walkable_radius is None and len(data) >= 68:
                self.walkable_radius = struct.unpack_from("<f", data, 64)[0]
            s = lib().dn_add_tile(self.h, data, len(data))
            if s & 0x80000000:                         # DT_FAILURE
                bad += 1
        self.ntiles = lib().dn_tile_count(self.h)
        self.bad_tiles = bad
        self.offset = tuple(float(v) for v in offset)
        self.include, self.exclude = 0xFFFF, 0
        self.ext = (1.0, 4.0, 1.0)

    def __del__(self):
        if getattr(self, "h", None) and _lib is not None:
            _lib.dn_destroy(self.h)

    def _in(self, p):
        o = self.offset
        x, y, z = (p[0], p[1], p[2]) if isinstance(p, (tuple, list)) else (p.x, p.y, p.z)
        return F3(x - o[0], y - o[1], z - o[2])

    def _out(self, a, k=0):
        o = self.offset
        return vector(a[k] + o[0], a[k + 1] + o[1], a[k + 2] + o[2])

    def nearest(self, pos, ext=None):
        out = F3(); ref = ctypes.c_uint(0)
        ok = lib().dn_nearest(self.h, self._in(pos), _v3(ext or self.ext), self.include, self.exclude, out, ctypes.byref(ref))
        return (self._out(out), ref.value) if ok else (None, 0)

    def path(self, s, e, ext=None):
        pts = (ctypes.c_float * (3 * MAX_PTS))(); fl = (ctypes.c_ushort * MAX_PTS)(); part = ctypes.c_int(0)
        n = lib().dn_path(self.h, self._in(s), self._in(e), _v3(ext or self.ext), self.include, self.exclude, pts, fl, MAX_PTS, ctypes.byref(part))
        if n <= 0:
            return None, None, False
        return [self._out(pts, 3 * k) for k in range(n)], [fl[k] for k in range(n)], bool(part.value)

    def query_box(self, center, half, maxn=1024):
        refs = (ctypes.c_uint * maxn)()
        n = lib().dn_query_box(self.h, self._in(center), _v3(half), self.include, self.exclude, refs, maxn)
        return [refs[k] for k in range(max(0, n))]

    def circle(self, center, radius, maxn=1024):
        refs = (ctypes.c_uint * maxn)()
        n = lib().dn_circle(self.h, self._in(center), float(radius), _v3(self.ext), self.include, self.exclude, refs, maxn)
        return [refs[k] for k in range(max(0, n))]

    def poly_height(self, ref, pos):
        # NeoX 内置 Detour 的写法（逐细节三角形、含边界），见 detour_c.cpp dn_poly_height_legacy
        h = ctypes.c_float(0)
        return h.value + self.offset[1] if lib().dn_poly_height_legacy(self.h, ref, self._in(pos), ctypes.byref(h)) else None

    def column_heights(self, pos, half):
        """(x, z) 竖直方向上所有多边形的高度（升序）。"""
        hs = set()
        for r in self.query_box(pos, half):
            h = self.poly_height(r, pos)
            if h is not None:
                hs.add(round(h, 4))
        return sorted(hs)


def _res_bytes(path):
    import physx_collision
    return physx_collision._res_bytes(path)


class scene_detour(object):
    def __init__(self):
        self.meshes = {}            # 名 -> NavMesh | None(已 add 未载入或载入失败)
        self.ext = {}               # 名 -> 搜索半尺寸（set_detour_extension 可能先于载入）
        self.flag = {}

    def __bool__(self): return True

    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        simenv.ACCESS["detour.scene_detour." + n] += 1
        return simenv.Stub("detour.scene_detour." + n)

    # ---- 网格管理 ----
    def add_mesh(self, name):
        self.meshes.setdefault(name, None)

    def remove_mesh(self, name):
        self.meshes.pop(name, None)

    def load_mesh(self, name, path, offset=None, *a):
        QUERIES["load_mesh"] += 1
        nb = _res_bytes(path)
        if nb is None:
            LOADED.append((name, path, "资源缺失")); self.meshes[name] = None
            return False
        import navmesh
        d = str(path).replace("\\", "/")
        tdir = d.rsplit("/", 1)[0] + "/" + d.rsplit("/", 1)[1].rsplit(".", 1)[0]
        tiles, miss = [], 0
        for tn in navmesh.tile_names(nb):
            tb = _res_bytes(tdir + "/" + tn)
            if tb is None: miss += 1
            else: tiles.append(tb)
        try:
            m = NavMesh(nb, tiles, tuple(offset) if offset is not None else (0.0, 0.0, 0.0))
        except Exception as e:
            LOADED.append((name, path, "载入失败 %r" % e)); self.meshes[name] = None
            return False
        if name in self.ext: m.ext = self.ext[name]
        if name in self.flag: m.include = self.flag[name]
        self.meshes[name] = m
        LOADED.append((name, path, "%d 块（缺 %d、addTile 失败 %d）" % (m.ntiles, miss, m.bad_tiles)))
        return True

    def _mesh(self, name):
        m = self.meshes.get(name)
        if m is not None or not USE_FALLBACK:
            return m
        for k, v in self.meshes.items():
            if v is not None and k.startswith("ai_"):
                FALLBACK[name] += 1
                return v
        return None

    def set_detour_flag(self, name, flag):
        QUERIES["set_detour_flag"] += 1
        self.flag[name] = int(flag)
        m = self.meshes.get(name)
        if m is not None: m.include = int(flag)

    def set_detour_extension(self, name, ext):
        e = (float(ext.x), float(ext.y), float(ext.z)) if hasattr(ext, "x") else tuple(map(float, ext))
        self.ext[name] = e
        m = self.meshes.get(name)
        if m is not None: m.ext = e

    # ---- 查询 ----
    def get_height(self, name, x, y, z):
        """引擎实现（libclient 热更版反汇编 0x8eb5780，SKILL §9.14）：
        findNearestPoly(中心=(x,y,z), 半尺寸=(ext.x×缩放, 4000, ext.z×缩放)) → getPolyHeight(ref, (x,y,z))，失败返回 None。
        ext 是 set_detour_extension 设的值（游戏设 (1, extent_y, 1)），缩放 = mesh[0x1138]，构造默认 1.0、MSET 载入不改。
        竖直半尺寸写死 4000；NeoX 内置的是 v1.6 之前的 Detour（无 dtNavMesh::getPolyHeight），点不在多边形投影内时 getPolyHeight 失败 → None。
        （旧版推断"投影外取最近点高度"已去掉。）"""
        QUERIES["get_height"] += 1
        m = self._mesh(name)
        if m is None: return None
        p, ref = m.nearest((x, y, z), (m.ext[0], 4000.0, m.ext[2]))
        h = m.poly_height(ref, (x, y, z)) if p is not None else None
        if h is None and self.meshes.get(name) is None and m.walkable_radius:   # 载入失败的网格登记为 None
            # 近似（仅回退查询）：要查的普通/tilecache 网格缺，落到了 AI 网格。两者只差墙边收缩距离（AI 收 walkable_radius=6，
            # 普通网格更少），所以真网格边界最多比 AI 网格往外多 walkable_radius → 在这个水平范围内吸附到 AI 网格最近点取高度。
            p, ref = m.nearest((x, y, z), (m.walkable_radius, 4000.0, m.walkable_radius))
            if p is not None:
                FALLBACK["get_height 回退网格边缘吸附(近似)"] += 1
                h = p.y
        return h

    def get_vertical_height(self, name, x, y, z, floor_flag=True, *a):
        """推断（调用处只在 UGC/跳跃副本分支）：竖直方向所有多边形高度中，floor_flag 取 y 以下最高的，否则取离 y 最近的。"""
        QUERIES["get_vertical_height"] += 1; UNIMPL["get_vertical_height(推断)"] += 1
        m = self._mesh(name)
        if m is None: return None
        hs = m.column_heights((x, y, z), (0.5, 2000.0, 0.5))
        if not hs: return None
        if floor_flag:
            below = [h for h in hs if h <= y + 1e-3]
            return below[-1] if below else None
        return min(hs, key=lambda h: abs(h - y))

    def get_nearest_nav_point(self, name, pos, extent=None):
        QUERIES["get_nearest_nav_point"] += 1
        m = self._mesh(name)
        return m.nearest(pos, _ext(extent))[0] if m is not None else None

    def find_nearest_poly(self, name, pos, half=None):
        QUERIES["find_nearest_poly"] += 1
        m = self._mesh(name)
        return m.nearest(pos, _ext(half))[0] if m is not None else None

    def get_path(self, name, s, e, poly_search=None, *a):
        QUERIES["get_path"] += 1
        m = self._mesh(name)
        if m is None or s is None or e is None: return None
        pts, fl, part = m.path(s, e)
        if part: PARTIAL[name] += 1
        return pts

    def get_path_with_flag(self, name, s, e, poly_search=None, *a):
        """flags 推断为各拐点所在多边形的标志（调用处 get_detour_path_check_flag 的使用方都没读它）。"""
        QUERIES["get_path_with_flag"] += 1
        m = self._mesh(name)
        if m is None: return (None, None)
        pts, fl, part = m.path(s, e)
        if part: PARTIAL[name] += 1
        return (pts, fl) if pts else (None, None)

    def get_poly_ref(self, name, bmin, bmax, maxn=65535, *a):
        QUERIES["get_poly_ref"] += 1
        m = self._mesh(name)
        if m is None: return None
        c = ((bmin.x + bmax.x) / 2, (bmin.y + bmax.y) / 2, (bmin.z + bmax.z) / 2)
        hf = (abs(bmax.x - bmin.x) / 2, abs(bmax.y - bmin.y) / 2, abs(bmax.z - bmin.z) / 2)
        return m.query_box(c, hf, min(int(maxn), 4096)) or None

    def find_polys_around_circle(self, name, center, radius, *a):
        QUERIES["find_polys_around_circle"] += 1
        m = self._mesh(name)
        return m.circle(center, radius) if m is not None else []

    def set_poly_flag(self, name, ref, flag):
        QUERIES["set_poly_flag"] += 1
        m = self._mesh(name)
        return bool(m is not None and lib().dn_set_flags(m.h, int(ref), int(flag) & 0xFFFF))

    def get_poly_flag(self, name, ref):
        QUERIES["get_poly_flag"] += 1
        m = self._mesh(name)
        f = ctypes.c_ushort(0)
        return f.value if m is not None and lib().dn_get_flags(m.h, int(ref), ctypes.byref(f)) else None

    def get_layer_nav_points(self, name, pos, extent, storey_height=None, floor_flag=False, strict_flag=False, *a):
        """推断：(x,z) 竖直方向各层导航点（升序）；storey_height/strict_flag 语义未知，未使用。"""
        QUERIES["get_layer_nav_points"] += 1; UNIMPL["get_layer_nav_points(推断)"] += 1
        m = self._mesh(name)
        if m is None: return ()
        hs = m.column_heights(pos, _ext(extent) or (2.0, 4000.0, 2.0))
        if floor_flag:
            hs = [h for h in hs if h <= pos.y + 1e-3]
        return tuple(vector(pos.x, h, pos.z) for h in hs)

    # ---- tilecache 动态障碍：tilecache 未载入（tc_init_done=False）时 NavManager 不会调用；调用了就计数 ----
    def _noop(self, what):
        UNIMPL[what] += 1
        return None

    def add_obstacle(self, *a): return self._noop("add_obstacle")
    def add_cylinder_obstacle(self, *a): return self._noop("add_cylinder_obstacle")
    def add_box_obstacle(self, *a): return self._noop("add_box_obstacle")
    def add_oriented_box_obstacle(self, *a): return self._noop("add_oriented_box_obstacle")
    def remove_obstacle(self, *a): return self._noop("remove_obstacle")
    def remove_all_obstacle(self, *a): return self._noop("remove_all_obstacle")
    def update_navmesh(self, *a): return self._noop("update_navmesh")


def _ext(e):
    if e is None: return None
    return (float(e.x), float(e.y), float(e.z)) if hasattr(e, "x") else tuple(map(float, e))
