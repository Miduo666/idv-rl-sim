# -*- coding: utf-8 -*-
# probe2 命令：求生者视角的准备阶段 —— 能不能看到**监管**的天赋 / 辅助特质？
# 背景：监管视角实测能看到四个求生者的 final_genius；求生者视角那次 final_genius_dict 里
#       监管位是空列表，怀疑这份数据是单向的(游戏不让求生者提前知道监管配装)。
# 这个脚本把"监管那条记录"的**全部字段**打出来，逐条判定，最后给结论。
gk = GK
av = S(lambda: gk.g_avatar)
me = S(lambda: gk.g_unit)

P("== 当前身份 ==")
P("  g_unit=%s  room=%s" % (cname(me), cname(S(lambda: me.room))))
ubt = S(lambda: gk.unit_mgr.units_by_type, {}) or {}
P("  units_by_type 键 = %s   (没有键1/2 = 局外)" % sorted([k for k in S(lambda: list(ubt.keys()), [])]))
P("  本机 uid=%s unique_id=%s" % (R(S(lambda: idict(me).get("uid")), 12),
                                  R(S(lambda: idict(me).get("unique_id")), 20)))

P("\n== g_avatar.final_genius_dict ==")
fg = S(lambda: av.final_genius_dict)
if isinstance(fg, dict):
    for k, v in fg.items():
        P("  %-28r -> %r" % (k, v))
else:
    P("  取不到: %r" % (fg,))

def dump_roster(lst, tag):
    P("\n== %s ==" % tag)
    if not isinstance(lst, (list, tuple)):
        P("  取不到: %r" % (lst,)); return None
    hunter = None
    for i, e in enumerate(lst):
        if not isinstance(e, dict):
            P("  #%d %s" % (i, R(e, 120))); continue
        rt = e.get("role_type")
        P("  #%d role_type=%s eid=%s name=%s pid=%s bot=%s final_genius=%s support_skill_id=%s" % (
            i, R(rt, 4), R(e.get("eid"), 30), R(e.get("player_name"), 16), R(e.get("pid"), 6),
            R(e.get("bot"), 6), R(e.get("final_genius"), 30), R(e.get("support_skill_id"), 16)))
        if rt == 1:
            hunter = e
    return hunter

hunter = dump_roster(S(lambda: av.player_data_list), "g_avatar.player_data_list")

# 准备界面 UI 上那份(进局会销毁，局外才有)
ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
panel = None
for k, v in (S(lambda: list(ui.items()), []) or []):
    if "RoomWait" in str(k) or "RoomWait" in cname(v):
        panel = v; break
if panel is not None:
    d = S(lambda: idict(panel), {}) or {}
    info = S(lambda: d.get("eid_2_player_info"))
    if isinstance(info, dict):
        h2 = dump_roster(list(info.values()), "UIRoomWait.eid_2_player_info")
        hunter = hunter or h2
    P("\n  UIRoomWait 其它可能带监管信息的字段:")
    for a in sorted(d.keys()):
        low = a.lower()
        if any(w in low for w in ("butcher", "b_", "hunter", "camp", "role", "nightmare", "assistive")):
            v = S(lambda a=a: d.get(a))
            if v is None or callable(v) or v in ({}, [], set(), "", False): continue
            P("    %-28s %s" % (a, R(v, 130)))
else:
    P("\n(没有 UIRoomWait —— 不在准备界面?)")

P("\n== 监管那条记录的全部字段 ==")
if hunter is None:
    P("  ★ 花名册里**没有** role_type==1 的记录 —— 求生者视角下监管根本不在名单里")
else:
    for k in sorted(hunter.keys()):
        P("  %-24s %s" % (k, R(hunter.get(k), 150)))
    fgv = hunter.get("final_genius")
    ssv = hunter.get("support_skill_id")
    P("\n  ★ 结论: 监管 final_genius = %r ; support_skill_id = %r" % (fgv, ssv))
    if not fgv and not ssv:
        P("  ★ 都是空 -> 求生者视角看不到监管配装，这个功能做不了")
    else:
        P("  ★ 有值 -> 可以做！")
