# -*- coding: utf-8 -*-
# probe2: 出生点(birth)/区域选择 —— 在 UIRoomWait 内。不靠关键字, 按"形状"找选择容器。
# 时机: 出生点倒计时中、求生者已开始选格子时发。
ud = S(lambda: GK.g_ui_mgr.ui_dict)
rw = S(lambda: ud["UIRoomWait"])
if rw is None:
    P("UIRoomWait 不在 ui_dict; keys=%s me=%s" % (R(S(lambda: list(ud.keys())), 120), cname(me)))
else:
    P("== UIRoomWait 所有非空 dict/list 属性(按形状找选择容器) ==")
    for a in sorted(S(lambda: list(idict(rw).keys()), [])):
        if not isinstance(a, str) or a.startswith("__"):
            continue
        v = S(lambda a=a: idict(rw)[a])
        cn = cname(v)
        if cn in ("dict", "list"):
            n = S(lambda v=v: len(v), 0)
            if n:
                P("  %-34s %s(%d) %s" % (a, cn, n, R(v, 160)))

    P("\n== 重点字段全量 ==")
    for key in ("pre_select_hero_info", "c_choice_data", "c_skill_data", "dk_pick_state",
                "dk_pick_state_hint", "eid_2_player_info", "uid2pos", "uid2pid", "uid_2_eid",
                "has_select", "ex_data_dict", "state_node_dict", "nightmare_info",
                "node_choose_dish", "role", "status"):
        v = S(lambda key=key: idict(rw)[key])
        P("  -- %-24s = %s" % (key, R(v, 700)))

    P("\n== birth_* / dish / pick / choose 全部 ==")
    for a in sorted(S(lambda: list(idict(rw).keys()), [])):
        if isinstance(a, str) and any(w in a.lower() for w in ("birth", "dish", "pick", "choose", "choice", "born")):
            P("  %-32s %-16s %s" % (a, cname(S(lambda a=a: idict(rw)[a])), R(S(lambda a=a: idict(rw)[a]), 140)))

P("\n== 现状 == me=%s units_by_type=%s" % (
    cname(me), R(S(lambda: {k: len(units_of(k) or []) for k in sorted([x for x in ubt().keys() if isinstance(x, int)])}), 160)))
