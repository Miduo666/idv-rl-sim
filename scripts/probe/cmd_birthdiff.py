# -*- coding: utf-8 -*-
# probe2: 出生/选区阶段 全量变化检测。进选区就发, 做出最终选择, 让它录到那次变化。
# 对 UIRoomWait + cur_world + g_avatar 的每个属性拍快照, 只记"跨帧变化"的(排噪声)。
# 选择数据无论存哪, 做选择的那一刻都会作为变化冒出来。写 birth_diff.txt(flush)。
import time
OUT = "/sdcard/Android/data/com.netease.dwrg/files/birth_diff.txt"
f = open(OUT, "w")

NOISE = ("time", "timer", "handler", "anim", "sfx", "tips", "_nodes", "_state_dict",
         "swallow", "tick", "frame", "left_time", "update", "cb_set", "logger", "ts",
         "_fade", "_hide", "registered_events", "area_times", "ping")

def sig(v):
    cn = cname(v)
    if cn == "dict":
        return "dict(%d)" % S(lambda: len(v), -1)
    if cn in ("list", "tuple", "set"):
        return "%s(%d)" % (cn, S(lambda: len(v), -1))
    if cn in ("int", "float", "bool", "str", "NoneType"):
        return "%s=%s" % (cn, R(v, 48))
    return cn  # 对象: 只记类名(避免 id 噪声)

def snapshot():
    out = {}
    for label, obj in (("RW", S(lambda: GK.g_ui_mgr.ui_dict.get("UIRoomWait"))),
                       ("CW", S(lambda: GK.g_world_mgr.cur_world)),
                       ("AV", S(lambda: GK.g_avatar))):
        if obj is None:
            continue
        for a in S(lambda obj=obj: list(idict(obj).keys()), []):
            if not isinstance(a, str) or a.startswith("__"):
                continue
            if any(w in a.lower() for w in NOISE):
                continue
            out["%s.%s" % (label, a)] = sig(S(lambda obj=obj, a=a: idict(obj)[a]))
    return out

prev = None
t0 = time.time()
nchg = 0
while time.time() - t0 < 55:
    cur = snapshot()
    if prev is not None:
        for k in sorted(set(prev) | set(cur)):
            a, b = prev.get(k, "<缺>"), cur.get(k, "<缺>")
            if a != b:
                nchg += 1
                f.write("t+%-4.0f %-40s %s  ->  %s\n" % (time.time() - t0, k, a, b)); f.flush()
    prev = cur
    time.sleep(1.0)
f.write("== done, %d 处变化 ==\n" % nchg); f.close()
P("STARTED birthdiff -> birth_diff.txt, %d 处变化" % nchg)
