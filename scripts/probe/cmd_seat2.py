# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：监管视角准备阶段 —— eid_2_player_info 的键与 uid2pos 的键是不是同一对象，
# 以及值 dict 里 role_type / final_genius 的类型。
ui = S(lambda: GK.g_ui_mgr.ui_dict, {}) or {}
panel = S(lambda: ui.get("UIRoomWait"))
d = S(lambda: idict(panel), {}) or {}
pos = d.get("uid2pos") or {}
info = d.get("eid_2_player_info") or {}
P("role=%r  info 类型=%s  n=%d" % (d.get("role"), type(info).__name__, len(info)))
for k, e in info.items():
    same = [pk for pk in pos.keys() if pk is k]
    P("  key=%s(%s,id=%s) 同一对象=%s 座位=%s  rt=%r(%s) fg=%r(%s) pid=%r" % (
        R(k, 40), type(k).__name__, hex(id(k)), bool(same), pos.get(k),
        e.get("role_type"), type(e.get("role_type")).__name__,
        e.get("final_genius"), type(e.get("final_genius")).__name__, e.get("pid")))
    if isinstance(e, dict): P("     值 dict 键: %s" % R(sorted(e.keys()), 300))
