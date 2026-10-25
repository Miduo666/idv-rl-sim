# -*- coding: utf-8 -*-
# probe2 林中童话：每个 [1601] 玩家的【全部】Python 属性 + combat_unit 深挖一层。
# 目的：看到"悬空框/空有框没有人"时单发一次，一份快照里同时含真人和空框，对比差异定位死亡/幽灵判据。
# 单次快照，不 sleep。用法：看到空框时  .\send_cmd.ps1 cmd_wf_full.py 空框
#
# probe2 在游戏进程内，能读到玩家单位全部 Python 属性(这就是"程序能读到的所有东西"的 Python 侧)。
# 场景侧内存(驱动读的那套 +0x240 等)CPython 无 ctypes 读不了，但 WaterFight 玩家 model_path=None、
# 差异几乎必在 Python 字段，所以全量 idict + combat_unit 足够。

def getd(o):
    return (S(lambda: idict(o), {}) or {}) if o is not None else {}

def shortval(v):
    # 数值/布尔/None/字符串直接印；容器印长度；对象印类名
    if v is None or isinstance(v, (int, float, bool)):
        return repr(v)
    if isinstance(v, str):
        return repr(v[:40])
    if isinstance(v, (list, tuple)):
        return "%s(len=%d)" % (type(v).__name__, len(v))
    if isinstance(v, dict):
        return "dict(len=%d)" % len(v)
    return "<%s>" % cname(v)

def dump_obj(o, tag, depth):
    pad = "  " * depth
    d = getd(o)
    if not d:
        P("%s%s = %s (无 idict)" % (pad, tag, cname(o) if o is not None else None)); return
    P("%s%s = %s  (%d 属性)" % (pad, tag, cname(o), len(d)))
    for k in sorted(d.keys()):
        if not isinstance(k, str): continue
        P("%s    %-26s %s" % (pad, k, shortval(d[k])))

us = units_of(1601) or []
P("========== [1601] 玩家 %d 个 — 全量 dump ==========" % len(us))
for idx, u in enumerate(us):
    d = getd(u)
    P("\n################ 玩家#%d uid=%s self=%s team=%s ident=%s is_leave=%s ################" % (
        idx, R(d.get("uid"),12), R(d.get("is_self"),6), R(d.get("water_fight_team"),4),
        R(d.get("water_fight_identity"),4), R(d.get("is_leave"),6)))
    # 全部顶层属性
    for k in sorted(d.keys()):
        if not isinstance(k, str): continue
        P("  %-28s %s" % (k, shortval(d[k])))
    # combat_unit 深挖一层：它本体 + 每个组件对象里的数值/布尔/字符串
    cu = d.get("combat_unit")
    if cu is not None:
        cud = getd(cu)
        P("  ---- combat_unit = %s (%d 属性) ----" % (cname(cu), len(cud)))
        for k in sorted(cud.keys()):
            if not isinstance(k, str): continue
            v = cud[k]
            P("    %-26s %s" % (k, shortval(v)))
            # 组件对象再钻一层，只印里面的数值/布尔/字符串(状态/血量最可能在这)
            if v is not None and not isinstance(v, (int, float, bool, str, list, tuple, dict)):
                sub = getd(v)
                prim = {kk: sub[kk] for kk in sub if isinstance(kk, str) and isinstance(sub.get(kk), (int, float, bool, str))}
                if prim:
                    P("        内含: %s" % {kk: (prim[kk] if not isinstance(prim[kk], str) else prim[kk][:20]) for kk in list(prim)[:24]})
P("\n[done]")
