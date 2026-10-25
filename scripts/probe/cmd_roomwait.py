# -*- coding: utf-8 -*-
# probe2 命令：把准备界面 UIRoomWait 看清楚 —— 成员表、各人选了什么、辅助特质在不在这里。
gk = GK
ui = S(lambda: gk.g_ui_mgr.ui_dict)
panel = None
if isinstance(ui, dict):
    for k, v in ui.items():
        if "RoomWait" in str(k) or "RoomWait" in cname(v):
            panel = v; P("面板 = %s (键 %r)" % (cname(v), k)); break
if panel is None:
    P("没找到 UIRoomWait；当前 ui_dict 键 = %s" % R(S(lambda: list(ui.keys())), 300))
else:
    d = S(lambda: idict(panel), {}) or {}
    P("\n== pre_select_hero_info 全量 ==")
    info = S(lambda: d.get("pre_select_hero_info"))
    if isinstance(info, dict):
        for k, v in info.items():
            P("  %r ->" % (k,))
            if isinstance(v, dict):
                for kk in sorted(v.keys()):
                    P("      %-22s %s" % (kk, R(v.get(kk), 120)))
            else:
                P("      %s" % R(v, 200))
    else:
        P("  取不到: %r" % (info,))

    P("\n== 面板上其它可能有用的属性(非 UI 节点、有值) ==")
    for a in sorted(d.keys()):
        if a.startswith("__"): continue
        v = S(lambda a=a: d.get(a))
        if v is None or callable(v): continue
        cn = cname(v)
        if cn in ("Node", "Button", "Layout", "Sprite", "Label", "ScrollView", "Widget", "ImageView",
                  "RichText", "CheckBox", "Slider", "EditBox", "ListView", "PageView"):
            continue
        if v in ({}, [], set(), "", False): continue
        low = a.lower()
        if any(w in low for w in ("hero", "info", "seat", "member", "player", "camp", "role",
                                  "skill", "genius", "talent", "select", "eid", "uid", "ready")):
            P("  %-36s %-10s %s" % (a, cn, R(v, 130)))

P("\n== 顺带：g_avatar 上和当前局相关的选择 ==")
av = S(lambda: gk.g_avatar)
for a in sorted(S(lambda: list(idict(av).keys()), []) or []):
    low = a.lower()
    if any(w in low for w in ("final", "pre_select", "preselect", "cur_", "battle")):
        v = S(lambda a=a: idict(av).get(a))
        if v is None or callable(v) or v in ({}, [], set(), "", False, 0): continue
        P("  %-34s %-9s %s" % (a, cname(v), R(v, 130)))
