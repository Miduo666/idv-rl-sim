# -*- coding: utf-8 -*-
# probe2 命令：看清 UIRoomWait.c_skill_data 的完整内容和字段含义，并和实时的 final_genius_dict 对照。
gk = GK
av = S(lambda: gk.g_avatar)
ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
panel = None
for k, v in (S(lambda: list(ui.items()), []) or []):
    if "RoomWait" in str(k) or "RoomWait" in cname(v):
        panel = v; break

P("== final_genius_dict(实时) ==")
fg = S(lambda: av.final_genius_dict)
if isinstance(fg, dict):
    for k, v in fg.items():
        P("  %-28r -> %r" % (k, v))

if panel is None:
    P("\n没有 UIRoomWait")
else:
    d = S(lambda: idict(panel), {}) or {}
    P("\n== c_skill_data 全量 ==")
    cs = S(lambda: d.get("c_skill_data"))
    if isinstance(cs, (list, tuple)):
        for i, row in enumerate(cs):
            P("  #%d %s" % (i, R(row, 200)))
    else:
        P("  取不到: %r" % (cs,))
    # 监管侧有没有对应的一份
    for a in sorted(d.keys()):
        if a.startswith("__"): continue
        low = a.lower()
        if ("skill_data" in low or "b_skill" in low or low.startswith("b_")) and a != "c_skill_data":
            P("  其它 %-24s %s" % (a, R(S(lambda a=a: d.get(a)), 200)))

P("\n== player_data_list 里的 final_genius / support(快照，用于对照) ==")
for e in (S(lambda: av.player_data_list, []) or []):
    if isinstance(e, dict):
        P("  role=%s eid=%-26s final_genius=%-12s support=%s" % (
            R(e.get("role_type"), 3), R(e.get("eid"), 26), R(e.get("final_genius"), 12),
            R(e.get("support_skill_id"), 10)))
