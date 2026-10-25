# -*- coding: utf-8 -*-
"""NeoX physx_collision / bullet_collision 的替代（接口同形，CollisionManager.init_collision_module 按 room.use_bullet 二选一）。
现阶段：碰撞体是真对象（cid/位置/旋转/尺寸），scene_col 记录动态体；查询一律"未命中"并计数 —— 地图网格 + 胶囊扫掠待实现。
查询的未命中返回值按调用处反推：
  sweep_test(_new) / hit_by_ray(_new) -> [hit, ...6 项]，[0] 为是否命中（CollisionManager.sweep_test_offset_new 无碰撞体时返回 [False]+[None]*5）
  static_test(_new) / sweep_intersect(_new) -> 碰到的碰撞体列表（调用处 `if not res` / 遍历）"""
import itertools, collections
import simenv
from math3d import vector, matrix

QUERIES = collections.Counter()
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

    def __bool__(self): return True
    def add_to_world(self, *a): pass
    def update(self, *a): pass

    def load(self, path, offset=None, *a):
        self.path = path
        return True

    def load_col_mesh_data(self, path, *a):
        self.col_meshes.append(path)
        return True

    def add_object(self, o, *a):
        self.objects[o.cid] = o
        o.scene = self

    def remove_object(self, o, *a):
        self.objects.pop(getattr(o, "cid", None), None)

    def _q(self, name, ret):
        QUERIES[name] += 1
        return ret

    def sweep_test(self, *a): return self._q("sweep_test", list(NO_HIT))
    def sweep_test_new(self, *a): return self._q("sweep_test_new", list(NO_HIT))
    def hit_by_ray(self, *a): return self._q("hit_by_ray", list(NO_HIT))
    def hit_by_ray_new(self, *a): return self._q("hit_by_ray_new", list(NO_HIT))
    def static_test(self, *a): return self._q("static_test", [])
    def static_test_new(self, *a): return self._q("static_test_new", [])
    def sweep_intersect(self, *a): return self._q("sweep_intersect", [])
    def sweep_intersect_new(self, *a): return self._q("sweep_intersect_new", [])


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    simenv.ACCESS["physx_collision." + name] += 1
    return simenv.Stub("physx_collision." + name)
