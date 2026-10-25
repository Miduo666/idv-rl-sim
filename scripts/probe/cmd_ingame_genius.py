# -*- coding: utf-8 -*-
# probe2 命令：局内验证 —— g_avatar.final_genius_dict 还在不在？能不能用 unique_id 配到单位上？
# 目的：它若有效，就是比 genius_id_lv_lst(十几个嵌套 list 的冷页，间歇读不出)稳得多的大天赋来源。
gk = GK
av = S(lambda: gk.g_avatar)
P("room=%s  g_unit=%s" % (cname(S(lambda: gk.g_unit.room)), cname(S(lambda: gk.g_unit))))
ubt = S(lambda: gk.unit_mgr.units_by_type, {}) or {}
P("units_by_type 键 = %s" % sorted([k for k in S(lambda: list(ubt.keys()), [])]))

P("\n== g_avatar.final_genius_dict ==")
fg = S(lambda: av.final_genius_dict)
if isinstance(fg, dict):
    for k, v in fg.items():
        P("  %-28r -> %r" % (k, v))
else:
    P("  取不到: %r" % (fg,))

P("\n== UIRoomWait 还在吗 ==")
ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
keys = S(lambda: [str(k) for k in ui.keys()], []) or []
P("  ui_dict 里含 RoomWait 的键: %s" % [k for k in keys if "RoomWait" in k])
P("  ui_dict 键数 = %d" % len(keys))

P("\n== 各单位的身份与天赋 ==")
for t in (1, 2, 236):
    lst = S(lambda t=t: list(ubt.get(t, [])), []) or []
    if not lst:
        continue
    P("键 %d: %d 个" % (t, len(lst)))
    for u in lst:
        d = S(lambda u=u: idict(u), {}) or {}
        uid = S(lambda: d.get("uid"))
        uniq = S(lambda: d.get("unique_id"))
        gl = S(lambda: d.get("genius_id_lv_lst"))
        ss = S(lambda: d.get("support_skill_id"))
        nm = S(lambda: d.get("player_name"))
        bot = S(lambda: d.get("is_bot"))
        P("  %-22s uid=%-9s unique_id=%-26r name=%-14s bot=%-6s support=%s" % (
            cname(u), R(uid, 10), uniq, R(nm, 14), R(bot, 6), R(ss, 14)))
        P("      genius_id_lv_lst(%s条) = %s" % (
            len(gl) if isinstance(gl, list) else "?", R(gl, 150)))
        # 用 unique_id 去 final_genius_dict 里配
        if isinstance(fg, dict) and uniq is not None:
            for key in (uniq, str(uniq)):
                if key in fg:
                    P("      ★ final_genius_dict[%r] = %r" % (key, fg.get(key)))
                    break
            else:
                P("      × final_genius_dict 里没有这个 unique_id")
