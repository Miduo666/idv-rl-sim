# -*- coding: utf-8 -*-
"""NeoX physx_collision / bullet_collision 的替代（接口同形，CollisionManager.init_collision_module 按 room.use_bullet 二选一）。
现阶段：碰撞体是真对象（cid/位置/旋转/尺寸），scene_col 记录动态体；load(.scn_col) 已把地图网格读进 colworld.ColWorld（self.world），
查询仍一律"未命中"并计数 —— 参数含义/返回字段还没从调用处反推出来，先记录每种查询前 SAMPLE_N 次的实参与调用位置(QUERY_SAMPLES)。
地图资源：环境变量 IDV_RES_ZIP，否则 <仓库>/res_pull/resdump_1025_015456/res_recovered.zip（§9.5.4）。
查询的未命中返回值按调用处反推：
  sweep_test(_new) / hit_by_ray(_new) -> [hit, ...6 项]，[0] 为是否命中（CollisionManager.sweep_test_offset_new 无碰撞体时返回 [False]+[None]*5）
  static_test(_new) / sweep_intersect(_new) -> 碰到的碰撞体列表（调用处 `if not res` / 遍历）"""
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
    f = sys._getframe(depth)                     # 默认：_caller <- _q <- 查询方法 <- 游戏调用处
    co = f.f_code
    return "%s:%s:%d" % (os.path.basename(co.co_filename), co.co_name, f.f_lineno)


_cid = itertools.count(1)
NO_HIT = (False, None, None, None, None, None)


class _Base(object):
    _kind = "obj"

    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        simenv.ACCESS["physx_collision.%s.%s" % (self._kind, n)] += 1
        return simenv.Stub("physx_collision.%s.%s" % (self._kind, n))


class col_object(_Base):
    _kind = "col_object"

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

    def _q(self, name, ret, a):
        QUERIES[name] += 1
        if len(QUERY_SAMPLES[name]) < SAMPLE_N:
            QUERY_SAMPLES[name].append((_caller(), _fmt(a)))
        return ret

    def sweep_test(self, *a): return self._q("sweep_test", list(NO_HIT), a)
    def sweep_test_new(self, *a): return self._q("sweep_test_new", list(NO_HIT), a)
    def hit_by_ray(self, *a): return self._q("hit_by_ray", list(NO_HIT), a)
    def hit_by_ray_new(self, *a): return self._q("hit_by_ray_new", list(NO_HIT), a)
    def static_test(self, *a): return self._q("static_test", [], a)
    def static_test_new(self, *a): return self._q("static_test_new", [], a)
    def sweep_intersect(self, *a): return self._q("sweep_intersect", [], a)
    def sweep_intersect_new(self, *a): return self._q("sweep_intersect_new", [], a)


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    simenv.ACCESS["physx_collision." + name] += 1
    return simenv.Stub("physx_collision." + name)
