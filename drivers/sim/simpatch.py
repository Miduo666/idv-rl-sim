# -*- coding: utf-8 -*-
"""模拟器的表现层补丁：纯视觉/音效/UI 的函数替换成返回默认值的空实现。
原则：只动"表现"，不碰逻辑（状态机、技能逻辑 LSkill*、碰撞、移动、判定）。每条注明理由。"""
import importlib

# (模块, 类名 或 None, 函数名, 返回值, 理由)
NOOP = [
    ("ClientUnits.BattlePlayerUnit", "BattlePlayerUnit", "should_socket_play_fx", False, "挂点特效是否播放（视觉）"),
    ("ClientUnits.BattlePlayerUnit", "BattlePlayerUnit", "check_exposure_fx_should_go_invisible", False, "曝光特效隐藏（视觉）"),
    ("core.ResAsyncLoadMgr", "ResAsyncLoadMgr", "check_loading_sync_res", True, "异步资源(模型)加载完成判定；不加载模型，直接完成"),
    ("worlds.WorldBase", "WorldBase", "update_script_tick", None, "脚本帧率统计（用真实时间差做除数）"),
    ("worlds.WorldBase", "WorldBase", "tick_graph_FPS", None, "画面帧率统计"),
    ("worlds.WorldBase", "WorldBase", "tick_log_FPS", None, "帧率日志"),
]


# ---- 模拟时钟：游戏逻辑的 time.time() / g_world_mgr.now 全部改由模拟时间驱动 ----
SIM_EPOCH = 1790000000.0


def install_clock():
    import time as _t, game3d
    _t._real_time = getattr(_t, "_real_time", _t.time)
    _t.time = lambda: SIM_EPOCH + game3d.now_ms() / 1000.0
    return _t._real_time

# ---- 被游戏吞掉的异常：utils.custom_traceback_handler -> TracebackManager().on_traceback ----
import collections, traceback
SWALLOWED = collections.Counter()


def install_traceback_capture(echo=True):
    from common_tools import TracebackManager as TM

    def on_traceback(self, t, v, tb, **kw):
        key = "".join(traceback.format_exception_only(t, v)).strip()
        if not SWALLOWED[key] and echo:
            print("[被吞异常] " + "".join(traceback.format_exception(t, v, tb, limit=-6))[-1500:])
        SWALLOWED[key] += 1
    TM.TracebackManager.on_traceback = on_traceback

CALLED = collections.Counter()


def count_calls(targets):
    """诊断用：给 (模块, 类名, 函数名) 挂计数器，看调用链断在哪一环。"""
    for mod, cls, fn in targets:
        owner = getattr(importlib.import_module(mod), cls)
        orig = owner.__dict__[fn] if fn in owner.__dict__ else getattr(owner, fn)
        key = "%s.%s" % (cls, fn)

        def wrap(*a, _o=orig, _k=key, **k):
            CALLED[_k] += 1
            return _o(*a, **k)
        setattr(owner, fn, wrap)

APPLIED = []


def apply():
    for mod, cls, fn, ret, why in NOOP:
        try:
            m = importlib.import_module(mod)
            owner = getattr(m, cls) if cls else m
            if not hasattr(owner, fn):
                APPLIED.append((mod, cls, fn, "缺失")); continue
            setattr(owner, fn, (lambda r: (lambda *a, **k: r))(ret))
            APPLIED.append((mod, cls, fn, "ok"))
        except Exception as e:
            APPLIED.append((mod, cls, fn, "ERR %r" % e))
    return APPLIED
