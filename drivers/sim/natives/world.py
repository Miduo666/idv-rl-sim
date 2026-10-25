# -*- coding: utf-8 -*-
"""NeoX world 模块替代（无渲染）：scene 立即"加载完成"；模型只保存位置/朝向等逻辑上要读写的量。
未实现的属性回退成记录型桩。"""
import simenv
from math3d import vector, matrix

SPACE_TYPE_WORLD = 0
BIND_TYPE_ALL = 0
ANIM_TYPE_SKELETAL = 0


class _Base(object):
    _kind = "obj"

    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        simenv.ACCESS["world.%s.%s" % (self._kind, n)] += 1
        return simenv.Stub("world.%s.%s" % (self._kind, n))


# 场景里有逻辑意义的具名模型（板/窗/门/柜/开关…）：name -> (位置, 16 个 f32 旋转矩阵)。
# 来自配表 DM.pos_info[scene_id]（每类是 (模型名, 位置, 矩阵, ...) 的列表），由 register_scene_models 填入。
SCENE_MODELS = {}


def register_scene_models(pos_info):
    SCENE_MODELS.clear()
    for kind, rows in pos_info.items():
        for r in rows or ():
            if len(r) >= 3:
                SCENE_MODELS[r[0]] = (kind, r[1], r[2])
    return len(SCENE_MODELS)


class scene(_Base):
    _kind = "scene"

    def __init__(self, *a, **k):
        self.__dict__["path"] = None
        self.__dict__["_models"] = []
        self.__dict__["_named"] = {}
        self.__dict__["valid"] = True

    @property
    def scene_detour(self):
        # 原生导航对象（NavManager.load_scene_nav_mesh: self._detour = self.room.scene.scene_detour），官方 Detour 替代见 natives/detour.py
        d = self.__dict__.get("_detour")
        if d is None:
            import detour
            d = self.__dict__["_detour"] = detour.scene_detour()
        return d

    def get_model(self, name, *a):
        m = self._named.get(name)
        if m is None and name in SCENE_MODELS:
            kind, pos, rot = SCENE_MODELS[name]
            m = model(None)
            m.name = name
            rm = matrix(*rot)
            m.rotation_matrix = rm
            m.world_rotation_matrix = rm
            m.position = vector(*pos)
            self._named[name] = m
        return m

    def load(self, path=None, *a, **k):
        self.__dict__["path"] = path
        return True

    def get_progress(self, *a):
        return 1.0

    def is_scene_done(self, *a):
        return True

    def add_object(self, o, *a, **k):
        self._models.append(o)

    def remove_object(self, o, *a, **k):
        if o in self._models: self._models.remove(o)


class model(_Base):
    _kind = "model"

    # NeoX 的位置/旋转取值返回副本：调用方常写 `p = m.position; p.y += h`，返回内部对象会把模型本身改掉
    # （10-26 角色 Y 坐标每帧匀速上涨就是这个）。模型无父子层级，局部 = 世界。
    _POS = ("position", "world_position")
    _ROT = ("rotation_matrix", "world_rotation_matrix")

    def __init__(self, path=None, *a, **k):
        d = self.__dict__
        d["filename"] = path
        d["valid"] = True
        d["visible"] = True
        d["_pos"] = vector()
        d["_rot"] = matrix()
        d["scale"] = vector(1, 1, 1)
        d["anim_rate"] = 1.0
        d["cur_anim_name"] = ""
        d["anim_time"] = 0.0

    def __getattr__(self, n):
        if n in model._POS: return vector(self.__dict__["_pos"])
        if n in model._ROT: return matrix(self.__dict__["_rot"])
        return _Base.__getattr__(self, n)

    def __setattr__(self, n, v):
        if n in ("world_transformation", "transformation"):
            return model.world_transformation.fset(self, v)
        if n in model._POS: self.__dict__["_pos"] = vector(v); return
        if n in model._ROT: self.__dict__["_rot"] = matrix(v); return
        self.__dict__[n] = v

    @property
    def world_transformation(self):
        m = matrix(self._rot)
        m.translation = self._pos
        return m

    @world_transformation.setter
    def world_transformation(self, m):
        r = matrix(m); r.m[3][0] = r.m[3][1] = r.m[3][2] = 0.0
        self.__dict__["_rot"] = r
        self.__dict__["_pos"] = m.translation
    transformation = world_transformation


class sfx(model):
    _kind = "sfx"


class light(_Base):
    _kind = "light"


class camera(_Base):
    _kind = "camera"


class decal(_Base):
    _kind = "decal"


class deferred_decal(_Base):
    _kind = "deferred_decal"


class particlesystem(model):
    _kind = "particlesystem"


class speaker(_Base):
    _kind = "speaker"


class empty_object(model):
    _kind = "empty"


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    simenv.ACCESS["world." + name] += 1
    return simenv.Stub("world." + name)
