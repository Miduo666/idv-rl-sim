# -*- coding: utf-8 -*-
"""NeoX game3d 的替代：最关键的是延迟回调调度（AsyncManager 依赖 delay_exec/frame_delay_exec）。
模拟器主循环调用 advance(dt_ms) 推进模拟时间并执行到期回调。其余接口返回合理常量，未知的回退成记录型桩。"""
import heapq, itertools, traceback

PLATFORM_WIN32, PLATFORM_ANDROID, PLATFORM_IOS = 1, 2, 3
ASYNC_HIGH, ASYNC_MID, ASYNC_LOW = 0, 1, 2

_now_ms = 0.0
_frame = 0
_seq = itertools.count(1)
_heap = []           # (到期 ms, seq, handle)
_tasks = {}          # handle -> [func, args, speed, cancelled, kind]
_frame_tasks = []    # (到期帧, seq, handle)
ERRORS = []


def now_ms():
    return _now_ms


def frame_id():
    return _frame


def delay_exec(ms, func, args=(), relative=True):
    h = next(_seq)
    _tasks[h] = [func, tuple(args or ()), 1.0, False, "t"]
    heapq.heappush(_heap, (_now_ms + max(0.0, float(ms)), h, h))
    return h


def frame_delay_exec(frames, func, args=()):
    h = next(_seq)
    _tasks[h] = [func, tuple(args or ()), 1.0, False, "f"]
    heapq.heappush(_frame_tasks, (_frame + max(1, int(frames)), h, h))
    return h


def cancel_delay_exec(h):
    t = _tasks.get(h)
    if t: t[3] = True
    return True


def set_delay_exec_speed(h, scale):
    t = _tasks.get(h)
    if t: t[2] = float(scale)


def _run(h):
    t = _tasks.pop(h, None)
    if not t or t[3]:
        return
    try:
        t[0](*t[1])
    except Exception:
        ERRORS.append(traceback.format_exc())


def advance(dt_ms):
    """推进 dt_ms 毫秒和 1 帧，执行所有到期回调（回调里新加的、已到期的也会在本次执行）。"""
    global _now_ms, _frame
    _now_ms += dt_ms
    _frame += 1
    while _frame_tasks and _frame_tasks[0][0] <= _frame:
        _, _, h = heapq.heappop(_frame_tasks); _run(h)
    n = 0
    while _heap and _heap[0][0] <= _now_ms and n < 100000:
        _, _, h = heapq.heappop(_heap); _run(h); n += 1


def pending():
    return sum(1 for t in _tasks.values() if not t[3])


# ---- 平台/设备 ----
def get_platform(): return PLATFORM_ANDROID
def is_pc(): return False
def get_window_dpi(): return (400.0, 400.0)
def get_frame_rate(): return 30
def get_neox_major_version(): return 3
def get_doc_dir(): return "."
def load_plugin(*a, **k): return True
def get_frame_time(): return 33.3
def get_time(): return _now_ms / 1000.0


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    import simenv
    simenv.ACCESS["game3d." + name] += 1
    return simenv.Stub("game3d." + name)
