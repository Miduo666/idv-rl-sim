# -*- coding: utf-8 -*-
"""NeoX world 模块替代（无渲染）：scene 立即"加载完成"；模型只保存位置/朝向等逻辑上要读写的量。
未实现的属性回退成记录型桩。"""
import time
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
                SCENE_MODELS[r[0]] = (kind, r[1], r[2], r[3] if len(r) >= 4 else None)
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
            kind, pos, rot, attr = SCENE_MODELS[name]
            m = model(None)
            m.name = name
            m._scene_attr = (kind, attr)
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
        d["cur_anim_name"] = ""
        # 播放记录：anim_rate / anim_time / is_playing 由 __getattr__ 按模拟时钟（simpatch 换过的 time.time）算
        d["_play"] = {"t_start": 0.0, "ms0": 0.0, "rate": 1.0, "loop": False, "playing": False, "len": 0.0}

    def __getattr__(self, n):
        if n in model._POS: return vector(self.__dict__["_pos"])
        if n in model._ROT: return matrix(self.__dict__["_rot"])
        if n == "anim_time": return self._anim_time_ms()
        if n == "anim_rate": return self.__dict__["_play"]["rate"]
        if n == "is_playing": return self.__dict__["_play"]["playing"]
        return _Base.__getattr__(self, n)

    def __setattr__(self, n, v):
        if n in ("world_transformation", "transformation"):
            return model.world_transformation.fset(self, v)
        if n in model._POS: self.__dict__["_pos"] = vector(v); return
        if n in model._ROT: self.__dict__["_rot"] = matrix(v); return
        if n in ("anim_rate", "anim_time"):          # 中途改速率/跳时间：以当前时刻为新起点
            p = self.__dict__["_play"]
            p["ms0"] = float(v) if n == "anim_time" else self._anim_time_ms()
            p["t_start"] = time.time()
            if n == "anim_rate": p["rate"] = float(v)
            return
        self.__dict__[n] = v

    def _anim_time_ms(self):
        p = self.__dict__["_play"]
        t = p["ms0"]
        if p["playing"]:
            t += (time.time() - p["t_start"]) * 1000.0 * p["rate"]
        if p["len"] > 0:
            t = t % p["len"] if p["loop"] else min(t, p["len"])
        return t

    def play_animation(self, anim, transit_time=-1.0, transit_type=16, init_ratio=0.0, loop=2, rate=1.0, *rest):
        """引擎签名(common_tools.utils.play_animation 的调用)：第 4 参是起始位置占动画长度的比例，anim_time 单位毫秒。
        loop: 1 循环 / 0 不循环 / 2 = 用配置默认值（default_loop 还没进数据库，按不循环，计数）。"""
        import animdb
        t = self._anim_table()
        length = t.length_ms(anim) if t is not None else 0.0
        if loop == 2:
            animdb.STATS["loop=2按不循环"] += 1
        self.__dict__["cur_anim_name"] = anim
        self.__dict__["_play"] = {"t_start": time.time(), "ms0": float(init_ratio or 0.0) * length, "rate": float(rate or 1.0),
                                  "loop": loop == 1, "playing": True, "len": length}
        animdb.STATS["play_animation"] += 1

    def stop_animation(self, *a):
        p = self.__dict__["_play"]
        p["ms0"] = self._anim_time_ms(); p["t_start"] = time.time(); p["playing"] = False

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

    # —— 动画查询（数据见 natives/animdb.py）。只做查询，不模拟播放；没有骨骼映射的模型（场景物件等）保持原来的记录型桩 ——
    def _anim_table(self):
        import animdb
        return animdb.table_for(self.__dict__.get("filename"))

    def get_animation_component(self):
        t = self._anim_table()
        return _AnimComponent(t) if t is not None else _Base.__getattr__(self, "get_animation_component")()

    def get_anim_ctrl(self, *a):
        t = self._anim_table()
        return _AnimCtrl(t) if t is not None else _Base.__getattr__(self, "get_anim_ctrl")(*a)

    def get_anim_length(self, name):
        t = self._anim_table()
        return t.length_ms(name) if t is not None else _Base.__getattr__(self, "get_anim_length")(name)

    def get_root_bone(self):
        return 0     # RAWANIMA 骨骼表第 0 根就是 biped（根）

    def get_attr(self, name, *a):
        # 场景模型自带属性：配表 DM.pos_info[场景][类别] 每行 (模型名, 位置, 矩阵, 属性值)，属性名 = 类别名。
        # 例：门 door='2'/'1'、电闸 switch_l='2'/'1'（UnitManager.get_switch_from_door 客户端分支按 switch_l == door 配对）。
        # 其它属性仍是记录型桩（真机来自场景文件，模拟器没有）。
        sa = self.__dict__.get("_scene_attr")
        if sa is not None and sa[0] == name and sa[1] is not None:
            return sa[1]
        return _Base.__getattr__(self, "get_attr")(name, *a)


class _AnimComponent(_Base):
    """world.AnimationComponent 的查询子集；其余方法回退成记录型桩。"""
    _kind = "anim_component"

    def __init__(self, table):
        self.__dict__["_t"] = table

    def get_reference_to_first_frame_transform(self, anim_name, sec):
        m = matrix()
        m.translation = vector(*self._t.offset(anim_name, sec))
        return m

    # 动画图是表现层。组件变成真值后 AnimGraphComponent._play_animation_graph 会走到这里，
    # 返回假值桩它就抛 "play_animation_graph failed!"，所以给真值桩让它按成功走完（之后的调用仍是记录型桩）
    def play_animation_graph(self, *a):
        simenv.ACCESS["world.anim_component.play_animation_graph"] += 1
        return simenv.TStub("world.anim_component.play_animation_graph()")

    def get_or_create_empty_animation_graph_instance(self, *a):
        simenv.ACCESS["world.anim_component.get_or_create_empty_animation_graph_instance"] += 1
        return simenv.TStub("world.anim_component.get_or_create_empty_animation_graph_instance()")

    def get_rootmotion_delta_transform(self):
        # 只有 ROOT_MOTION_MODE（客户端、引擎真在播放动画）才用；模拟器是本地服务端，不该走到，计数
        import animdb
        animdb.STATS["delta_transform(不应调用)"] += 1
        return matrix()


class _AnimCtrl(_Base):
    """骨骼动画控制器的查询子集；其余方法回退成记录型桩。"""
    _kind = "anim_ctrl"

    def __init__(self, table):
        self.__dict__["_t"] = table

    def get_anim_index_by_name(self, name):
        if self._t.get(name) is None:
            return 65535
        return self._t.index.get(name, 65535)

    def get_anim_length(self, name):
        return self._t.length_ms(name)

    def get_anim_rate(self, name):
        # 动画自身的默认速率（配置 default_rate，还没进数据库），按 1.0
        return 1.0


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
