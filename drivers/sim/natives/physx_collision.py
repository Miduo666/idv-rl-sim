# -*- coding: utf-8 -*-
"""NeoX physx_collision / bullet_collision 的替代（接口同形，CollisionManager.init_collision_module 按 room.use_bullet 二选一）。
现阶段：碰撞体是真对象（cid/位置/旋转/尺寸），scene_col 记录动态体；load(.scn_col) 已把地图网格读进 colworld.ColWorld（self.world）。
每种查询记录前 SAMPLE_N 次的实参与调用位置(QUERY_SAMPLES)。地图资源：环境变量 IDV_RES_ZIP，否则 <仓库>/res_pull/resdump_1025_015456/res_recovered.zip（§9.5.4）。

原生接口（CollisionMgr.CollisionManager 的调用处，SKILL §9.6）：
  hit_by_ray(s, e, face_filter, group, layer, filter_type)          无过滤时 hit_by_ray(s, e, 0, 0, Layer.NORMAL)
  hit_by_ray_new(s, e, face_filter, group, ignore_types, extra_types, layer, filter_type)
  sweep_test(col, s, e, group, layer, face_filter, filter_type)     sweep_test_new(col, s, e, group, ignore, extra, layer, face_filter, filter_type)
  sweep_intersect(col, s, e, group, layer, filter_type)             sweep_intersect_new(col, s, e, group, ignore, extra, layer, filter_type)
  static_test(col, group, layer, filter_type)                       static_test_new(col, group, ignore, extra, layer, filter_type)
返回：射线/扫掠 = 6 元组 [命中, 命中点, 法线, ?, ?, 碰撞体]（[3][4] 调用处没见用过，填 None）；static/intersect = 碰撞体列表。
✅ 全部查询已接 ColWorld，过滤见 passes()；动态体在每次查询前按位置同步。查询体/动态体的 size 含义按形状逐个登记（SHAPE_QUERY），
未登记的形状不参与（UNSUPPORTED 计数）—— 目前只有球确认了。"""
import itertools, collections, os, sys, zipfile
import simenv
from math3d import vector, matrix

QUERIES = collections.Counter()
QUERY_SAMPLES = collections.defaultdict(list)    # 查询名 -> [(调用位置, 实参)]，每种前 SAMPLE_N 次
SAMPLE_N = 6
LOADED = []                                      # [(路径, 物体数, 三角形数) 或 (路径, 错误)]
RES_ZIP = os.environ.get("IDV_RES_ZIP") or os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "res_pull", "resdump_1025_015456", "res_recovered.zip"))
_zip = None


def _res_bytes(path):
    """按游戏路径从导出的资源 zip 取文件（大小写、斜杠不敏感）；取不到返回 None。"""
    global _zip
    if _zip is None:
        if not os.path.exists(RES_ZIP):
            _zip = False
        else:
            z = zipfile.ZipFile(RES_ZIP)
            _zip = (z, {n.replace("\\", "/").lower().lstrip("/"): n for n in z.namelist()})
    if not _zip:
        return None
    z, names = _zip
    n = names.get(str(path).replace("\\", "/").lower().lstrip("/"))
    return z.read(n) if n else None


def _fmt(x, depth=0):
    if isinstance(x, (list, tuple)) and depth < 2:
        return type(x)([_fmt(v, depth + 1) for v in x[:8]])
    if isinstance(x, (int, float, str, bool, type(None))):
        return x if not isinstance(x, str) else x[:80]
    r = repr(x)
    return r if len(r) <= 80 else r[:77] + "..."


def _caller(depth=3):
    try:
        f = sys._getframe(depth)                 # 默认：_caller <- _q <- 查询方法 <- 游戏调用处；经 _ray 等再多一层
    except ValueError:
        return "?"
    co = f.f_code
    return "%s:%s:%d" % (os.path.basename(co.co_filename), co.co_name, f.f_lineno)


_cid = itertools.count(1)
NO_HIT = (False, None, None, None, None, None)
QUERY_HITS = collections.Counter()

# 静态地图网格的过滤属性。set_default_filter_info(layer, group, utype, color) 被游戏调用时按实参覆盖（STATIC_SOURCE 记来源）；
# 没调用时的默认值是推断：分组 Group.STATIC_BODY（名字），层 Layer.NORMAL（各"无过滤"调用都传 Layer.NORMAL 且必须打得到地图）
STATIC_FILTER = {"group": None, "layer": None, "utype": None}
STATIC_SOURCE = ["推断默认值"]


def set_default_filter_info(layer, group, utype, color=None, *a):
    STATIC_FILTER.update(group=group, layer=layer, utype=utype)
    STATIC_SOURCE[:] = ["set_default_filter_info%r" % ((layer, group, utype, color) + a,)]


def _cc():
    from common_cs import CollisionConst
    return CollisionConst


def _static_attrs():
    cc = _cc()
    g = STATIC_FILTER["group"]
    l = STATIC_FILTER["layer"]
    return (cc.Group.STATIC_BODY if g is None else g), (cc.Layer.NORMAL if l is None else l), STATIC_FILTER["utype"]


def passes(obj_group, obj_layer, obj_utype, group_value, ignore, extra, layer_value, filter_type):
    """一个碰撞体是否参与查询。依据：
    - 层：air_power_extra_static_test（脚本里手写的 static_test）要求 `col.layer & layer_value`；
    - 分组/类型：CollisionManager._modify_filter_rule —— EXCLUDE 时 extra(T)+un_ignore(T) 使 T 被排除，INCLUDE 时 ignore(T)+un_extra(T) 使 T 不被包含。
      即 选中 = (分组命中 group_value 或 类型 ∈ extra) 且 类型 ∉ ignore；EXCLUDE 模式打"未选中"的，INCLUDE 模式只打"选中"的。"""
    if not (obj_layer & layer_value):
        return False
    sel = bool(obj_group & group_value) or (obj_utype is not None and obj_utype in extra)
    if obj_utype is not None and obj_utype in ignore:
        sel = False
    return (not sel) if filter_type == _cc().EXCLUDE_FILTER else sel


# ---- 碰撞体形状 ----
# 形状常量 CollisionConst：SPHERE 0 / BOX 1 / CAPSULE 2 / CYLINDER 3 / MESH 4 / ORG_CAPSULE 7 / CONVEX_CYLINDER 8。
# size 的含义逐个形状确认后才登记；未登记的形状：作为查询体时查询一律未命中，作为动态体时不放进世界（都计入 UNSUPPORTED）。
#   SPHERE：半径 = size.x（BaseBullet.build_collision 等都传 vector(radius, radius, radius)）
#   BOX / CAPSULE：待确认（看建角色 ghost_col 与 col_conf 的调用处）
UNSUPPORTED = collections.Counter()


def _sphere(o, c):
    return (c, c, float(o.size.x))


SHAPE_QUERY = {0: _sphere}                       # 形状常量 -> fn(col, 中心 tuple) -> (线段端点 a, 端点 b, 半径)
SHAPE_TRIS = {}                                  # 形状常量 -> fn(col) -> 三角形（不在表里的走 SHAPE_QUERY 转胶囊多面体）


def _rot3(o):
    m = getattr(getattr(o, "rotation_matrix", None), "m", None)
    return tuple(tuple(r[:3]) for r in m[:3]) if m else None


def _shape_state(o):
    if o.type not in SHAPE_QUERY and o.type not in SHAPE_TRIS:
        return None
    return (o.type, tuple(o.size), tuple(o.position), _rot3(o))


def _query_shape(o, center):
    fn = SHAPE_QUERY.get(getattr(o, "type", None))
    return fn(o, tuple(center)) if fn else None


def _shape_tris(o):
    import colworld
    if o.type in SHAPE_TRIS:
        return SHAPE_TRIS[o.type](o)
    a, b, r = _query_shape(o, o.position)
    return colworld.capsule_tris(a, b, r)


class _Base(object):
    _kind = "obj"

    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        simenv.ACCESS["physx_collision.%s.%s" % (self._kind, n)] += 1
        return simenv.Stub("physx_collision.%s.%s" % (self._kind, n))


class col_object(_Base):
    _kind = "col_object"

    # 参数顺序已核对：CollisionManager.col_object 调 collision_so.col_object(obj_type, size, unit_type, UNIT_GROUP[unit_type], mass, use_model_when_fail, layer[, convex_gen])
    def __init__(self, obj_type=0, size=None, unit_type=0, group=0, mass=0, use_model_when_fail=False, layer=0, *a):
        self.cid = next(_cid)
        self.type = obj_type
        self.size = vector(size) if size is not None else vector(1, 1, 1)
        self.unit_type, self.group, self.mass, self.layer = unit_type, group, mass, layer
        self.position = vector()
        self.rotation_matrix = matrix()
        self.enable = True
        self.scene = None

    def force_update(self): pass
    def __bool__(self): return True
    def __repr__(self): return "<col_object cid=%d type=%s ut=%s>" % (self.cid, self.type, self.unit_type)


class scene_col(_Base):
    _kind = "scene_col"

    def __init__(self, *a, **k):
        self.objects = {}
        self.path = None
        self.col_meshes = []
        self.world = None
        self._static = None                      # 必须显式初始化：_Base.__getattr__ 对缺失属性返回桩
        self._dyn_state = {}                     # cid -> 上次放进 ColWorld 时的形状状态

    def __bool__(self): return True
    def add_to_world(self, *a): pass
    def update(self, *a): pass

    def load(self, path, offset=None, *a):
        # 返回 True 沿用之前的桩行为（调用处对返回值的用法还没核对）；offset 等其余实参先只记录不使用
        self.path = path
        QUERY_SAMPLES["load"].append((_caller(2), _fmt((path, offset) + a)))
        try:
            data = _res_bytes(path)
            if data is None:
                LOADED.append((path, "资源 zip 里没有（%s）" % RES_ZIP))
                return True
            import colworld
            w = colworld.ColWorld()
            nobj = w.add_scn_col(data)
            w.build()
            self.world = w
            LOADED.append((path, nobj, len(w.st)))
        except Exception as e:                   # 不让几何层的问题挡住对局启动；在 report 里看
            LOADED.append((path, "%s: %s" % (type(e).__name__, e)))
        return True

    def load_col_mesh_data(self, path, *a):
        self.col_meshes.append(path)
        return True

    def add_object(self, o, *a):
        self.objects[o.cid] = o
        o.scene = self

    def remove_object(self, o, *a):
        self.objects.pop(getattr(o, "cid", None), None)

    def _q(self, name, ret, a, depth=3):
        QUERIES[name] += 1
        if len(QUERY_SAMPLES[name]) < SAMPLE_N:
            QUERY_SAMPLES[name].append((_caller(depth), _fmt(a)))
        return ret

    # ---- 过滤 / 动态体同步 ----
    def _norm(self, layer, filter_type):
        cc = _cc()
        if layer is None:
            layer = cc.Layer.NORMAL
        if filter_type is None:                  # 5 参数的无过滤射线：与 sweep/static 的无过滤路径一致，按 EXCLUDE(什么都不排除) 处理（推断）
            filter_type = cc.EXCLUDE_FILTER
        return layer, filter_type

    def _sync(self, flt, self_cid=None):
        """把 add_object 进来的碰撞体同步进 ColWorld（形状约定已确认的才放），返回本次查询要忽略的动态体键集合。"""
        w = self.world
        ignore = set()
        live = set()
        for cid, o in self.objects.items():
            if o is self._static:
                continue
            if cid == self_cid or not getattr(o, "enable", True) or not passes(o.group, o.layer, o.unit_type, *flt):
                ignore.add(cid)
            st = _shape_state(o)
            if st is None:
                UNSUPPORTED["动态体 type=%s" % (o.type,)] += 1
                continue
            live.add(cid)
            if self._dyn_state.get(cid) != st:
                w.add_dynamic(cid, _shape_tris(o))
                self._dyn_state[cid] = st
        for cid in list(self._dyn_state):
            if cid not in live:
                w.remove_dynamic(cid)
                del self._dyn_state[cid]
        return ignore

    def _obj(self, key):
        return self._static_obj() if isinstance(key, tuple) else self.objects.get(key)

    def _static_obj(self):
        """命中静态地图时返回的碰撞体：有 cid（不在 collision_dict 里，get_unit 得 None）、group/layer/unit_type 同静态过滤属性。"""
        o = self._static
        if o is None:
            o = self._static = col_object()
        o.group, o.layer, o.unit_type = _static_attrs()
        return o

    def _prep(self, group, ignore, extra, layer, filter_type, self_cid=None):
        layer, filter_type = self._norm(layer, filter_type)
        flt = (group, set(ignore or ()), set(extra or ()), layer, filter_type)
        return self._sync(flt, self_cid), passes(*_static_attrs(), *flt)

    # ---- 射线 ----
    def _ray(self, name, a, s, e, group, ignore, extra, layer, filter_type):
        self._q(name, None, a, depth=4)
        if self.world is None:
            return list(NO_HIT)
        dyn_ignore, use_static = self._prep(group, ignore, extra, layer, filter_type)
        h = self.world.raycast(tuple(s), tuple(e), ignore=dyn_ignore, static=use_static)
        if h is None:
            return list(NO_HIT)
        QUERY_HITS[name] += 1
        return [True, vector(*map(float, h.point)), vector(*map(float, h.normal)), None, None, self._obj(h.key)]

    def hit_by_ray(self, s, e, face_filter=0, group=0, layer=None, filter_type=None, *a):
        return self._ray("hit_by_ray", (s, e, face_filter, group, layer, filter_type) + a, s, e, group, (), (), layer, filter_type)

    def hit_by_ray_new(self, s, e, face_filter=0, group=0, ignore=(), extra=(), layer=None, filter_type=None, *a):
        return self._ray("hit_by_ray_new", (s, e, face_filter, group, ignore, extra, layer, filter_type) + a,
                         s, e, group, ignore, extra, layer, filter_type)

    # ---- 扫掠 / 静态测试（查询体形状约定未确认时一律未命中，并在 UNSUPPORTED 计数）----
    def _query_geom(self, name, col, center):
        g = _query_shape(col, center)
        if g is None:
            UNSUPPORTED["%s 查询体 type=%s" % (name, getattr(col, "type", None))] += 1
        return g

    def _sweep(self, name, a, col, s, e, group, ignore, extra, layer, filter_type):
        self._q(name, None, a, depth=4)
        if self.world is None:
            return list(NO_HIT)
        g = self._query_geom(name, col, s)
        if g is None:
            return list(NO_HIT)
        dyn_ignore, use_static = self._prep(group, ignore, extra, layer, filter_type, col.cid)
        p0, p1, r = g
        delta = (e.x - s.x, e.y - s.y, e.z - s.z)
        if delta == (0.0, 0.0, 0.0):
            # 起点=终点：check_in_collision_static_ex_sweep_test 把 [-1] 当碰撞体列表遍历、未命中判 None（其余槽位无用例，填 None）
            hits = self.world.capsule_overlap(p0, p1, r, ignore=dyn_ignore, static=use_static)
            if not hits:
                return list(NO_HIT)
            QUERY_HITS[name] += 1
            return [True, None, None, None, None, [self._obj(k) for k, _ in hits]]
        h = self.world.capsule_sweep(p0, p1, r, delta, ignore=dyn_ignore, static=use_static)
        if h is None:
            return list(NO_HIT)
        QUERY_HITS[name] += 1
        if h.start_overlap:
            QUERY_HITS[name + ":起点已重叠"] += 1      # 起点就压着东西时原生怎么返回没有依据，暂按 t=0 命中返回
        return [True, vector(*map(float, h.point)), vector(*map(float, h.normal)), None, None, self._obj(h.key)]

    def sweep_test(self, col, s, e, group=0, layer=None, face_filter=0, filter_type=None, *a):
        return self._sweep("sweep_test", (col, s, e, group, layer, face_filter, filter_type) + a, col, s, e, group, (), (), layer, filter_type)

    def sweep_test_new(self, col, s, e, group=0, ignore=(), extra=(), layer=None, face_filter=0, filter_type=None, *a):
        return self._sweep("sweep_test_new", (col, s, e, group, ignore, extra, layer, face_filter, filter_type) + a,
                           col, s, e, group, ignore, extra, layer, filter_type)

    def _static_test(self, name, a, col, group, ignore, extra, layer, filter_type):
        self._q(name, None, a, depth=4)
        if self.world is None:
            return []
        g = self._query_geom(name, col, col.position)
        if g is None:
            return []
        dyn_ignore, use_static = self._prep(group, ignore, extra, layer, filter_type, col.cid)
        hits = self.world.capsule_overlap(*g, ignore=dyn_ignore, static=use_static)
        if hits:
            QUERY_HITS[name] += 1
        return [self._obj(k) for k, _ in hits]

    def static_test(self, col, group=0, layer=None, filter_type=None, *a):
        return self._static_test("static_test", (col, group, layer, filter_type) + a, col, group, (), (), layer, filter_type)

    def static_test_new(self, col, group=0, ignore=(), extra=(), layer=None, filter_type=None, *a):
        return self._static_test("static_test_new", (col, group, ignore, extra, layer, filter_type) + a,
                                 col, group, ignore, extra, layer, filter_type)

    def _intersect(self, name, a, col, s, e, group, ignore, extra, layer, filter_type):
        """扫过路径上碰到的全部碰撞体（terrain_wall_sweep_test 把结果当集合遍历）。近似：沿路径按半径一半的步长做重叠测试取并集。"""
        self._q(name, None, a, depth=4)
        if self.world is None:
            return []
        g = self._query_geom(name, col, s)
        if g is None:
            return []
        dyn_ignore, use_static = self._prep(group, ignore, extra, layer, filter_type, col.cid)
        p0, p1, r = g
        d = (e.x - s.x, e.y - s.y, e.z - s.z)
        L = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5
        n = max(1, int(L / max(r * 0.5, 1e-3)))
        seen = {}
        for i in range(n + 1):
            t = i / n
            off = (d[0] * t, d[1] * t, d[2] * t)
            for k, _ in self.world.capsule_overlap([p0[j] + off[j] for j in range(3)], [p1[j] + off[j] for j in range(3)], r,
                                                   ignore=dyn_ignore, static=use_static):
                seen.setdefault(k, None)
        if seen:
            QUERY_HITS[name] += 1
        return [self._obj(k) for k in seen]

    def sweep_intersect(self, col, s, e, group=0, layer=None, filter_type=None, *a):
        return self._intersect("sweep_intersect", (col, s, e, group, layer, filter_type) + a, col, s, e, group, (), (), layer, filter_type)

    def sweep_intersect_new(self, col, s, e, group=0, ignore=(), extra=(), layer=None, filter_type=None, *a):
        return self._intersect("sweep_intersect_new", (col, s, e, group, ignore, extra, layer, filter_type) + a,
                               col, s, e, group, ignore, extra, layer, filter_type)


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    simenv.ACCESS["physx_collision." + name] += 1
    return simenv.Stub("physx_collision." + name)
