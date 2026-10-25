# -*- coding: utf-8 -*-
# probe2 命令：查 player_data_list 是不是过期快照。
# 现象：准备阶段特质已改成"移形"，叠加层仍显示上一局的"巡视者"。
# 猜测：player_data_list 是进局时写入的快照，准备阶段实时变化的是 UIRoomWait 那份。
gk = GK
av = S(lambda: gk.g_avatar)
P("room=%s  units_by_type键=%s" % (cname(S(lambda: gk.g_unit.room)),
    sorted([k for k in S(lambda: list(gk.unit_mgr.units_by_type.keys()), [])])))

def brief(lst, tag):
    P("\n== %s ==" % tag)
    if not isinstance(lst, (list, tuple)):
        P("  取不到/不是列表: %r" % (lst,)); return
    for i, e in enumerate(lst):
        if not isinstance(e, dict):
            P("  #%d %s" % (i, R(e, 100))); continue
        P("  #%d role=%s pid=%-4s name=%-14s final_genius=%-14s support=%-8s is_ready=%s eid=%s" % (
            i, R(e.get("role_type"), 3), R(e.get("pid"), 5), R(e.get("player_name"), 14),
            R(e.get("final_genius"), 14), R(e.get("support_skill_id"), 8),
            R(e.get("is_ready"), 6), R(e.get("eid"), 26)))

brief(S(lambda: av.player_data_list), "g_avatar.player_data_list")

ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
P("\n当前 ui_dict 键: %s" % R(S(lambda: [str(k) for k in ui.keys()]), 300))
panel = None
for k, v in (S(lambda: list(ui.items()), []) or []):
    if "RoomWait" in str(k) or "RoomWait" in cname(v):
        panel = v; break
if panel is not None:
    d = S(lambda: idict(panel), {}) or {}
    info = S(lambda: d.get("eid_2_player_info"))
    if isinstance(info, dict):
        brief(list(info.values()), "UIRoomWait.eid_2_player_info(界面实时)")
    brief(S(lambda: d.get("player_others")), "UIRoomWait.player_others")
else:
    P("\n没有 UIRoomWait 面板")

P("\n== final_genius_dict ==")
fg = S(lambda: av.final_genius_dict)
if isinstance(fg, dict):
    for k, v in fg.items():
        P("  %-28r -> %r" % (k, v))

# 自己现在选的特质：账号侧还有没有别的字段跟着变
P("\n== g_avatar 上可能存当前特质的字段 ==")
for a in sorted(S(lambda: list(idict(av).keys()), []) or []):
    low = a.lower()
    if any(w in low for w in ("support", "skill", "select", "cur_", "battle_position", "final")):
        v = S(lambda a=a: idict(av).get(a))
        if v is None or callable(v) or v in ({}, [], set(), "", False): continue
        P("  %-32s %-9s %s" % (a, cname(v), R(v, 120)))
