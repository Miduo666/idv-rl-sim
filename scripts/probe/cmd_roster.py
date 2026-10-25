# -*- coding: utf-8 -*-
# probe2 命令：准备界面的完整花名册 eid_2_player_info（含 final_genius），逐条全字段打印。
gk = GK
ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
panel = None
for k, v in (S(lambda: list(ui.items()), []) or []):
    if "RoomWait" in str(k) or "RoomWait" in cname(v):
        panel = v; break
if panel is None:
    P("没找到 UIRoomWait")
else:
    d = S(lambda: idict(panel), {}) or {}
    for name in ("eid_2_player_info",):
        info = S(lambda name=name: d.get(name))
        P("== %s ==" % name)
        if isinstance(info, dict):
            for k, v in info.items():
                P("  eid %r:" % (k,))
                if isinstance(v, dict):
                    for kk in sorted(v.keys()):
                        P("      %-24s %s" % (kk, R(v.get(kk), 150)))
                else:
                    P("      %s" % R(v, 250))
        else:
            P("  取不到: %r" % (info,))
    # 自己(监管)那条在不在 player_others 里？它是列表
    others = S(lambda: d.get("player_others"))
    P("\n== player_others 条数 = %s ==" % (len(others) if isinstance(others, list) else "?"))
    if isinstance(others, list):
        for i, v in enumerate(others):
            if isinstance(v, dict):
                P("  #%d eid=%s name=%s pid=%s bot=%s role_type=%s final_genius=%s" % (
                    i, R(v.get("eid"), 20), R(v.get("player_name"), 20), R(v.get("pid"), 8),
                    R(v.get("bot"), 8), R(v.get("role_type"), 4), R(v.get("final_genius"), 40)))
    # b_ 开头(监管侧)的映射
    P("\n== 监管侧映射 ==")
    for a in sorted(d.keys()):
        if a.startswith("b_") or a in ("uid2pid", "uid2pos", "uid_2_eid", "role", "copycat_camp_id"):
            P("  %-20s %s" % (a, R(S(lambda a=a: d.get(a)), 140)))
