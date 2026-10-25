# -*- coding: utf-8 -*-
# probe2 命令：准备界面快照(供前后差分用)。输出按名字排序、格式固定，方便两次 diff。
# 用法：改特质/天赋前跑一次，改完再跑一次，diff 出来变化的字段就是实时来源。
UI_CLS = ("Node", "Button", "Layout", "Sprite", "Label", "ScrollView", "Widget", "ImageView",
          "RichText", "CheckBox", "Slider", "EditBox", "ListView", "PageView", "RichTextEx55",
          "UIMatchState", "UIMatchCharName", "UIQuickChatSelect")
gk = GK
av = S(lambda: gk.g_avatar)

P("ROOM %s" % cname(S(lambda: gk.g_unit.room)))

# --- UIRoomWait 全部非 UI 属性 ---
ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
panel = None
for k, v in (S(lambda: list(ui.items()), []) or []):
    if "RoomWait" in str(k) or "RoomWait" in cname(v):
        panel = v; break
if panel is None:
    P("NOPANEL")
else:
    d = S(lambda: idict(panel), {}) or {}
    for a in sorted(d.keys()):
        if a.startswith("__"): continue
        v = S(lambda a=a: d.get(a))
        if v is None or callable(v): continue
        if cname(v) in UI_CLS: continue
        P("UI  %-34s %s" % (a, R(v, 150)))

# --- g_avatar：只取标量/小容器，避免噪声 ---
ad = S(lambda: idict(av), {}) or {}
for a in sorted(ad.keys()):
    if a.startswith("__"): continue
    v = S(lambda a=a: ad.get(a))
    if v is None or callable(v): continue
    cn = cname(v)
    if cn in ("int", "float", "bool", "str"):
        P("AV  %-34s %s" % (a, R(v, 80)))
    elif cn in ("list", "tuple", "dict", "set"):
        n = S(lambda: len(v), -1)
        if isinstance(n, int) and 0 <= n <= 12:
            P("AV  %-34s %s" % (a, R(v, 150)))

# --- 本机城市单位 ---
me = S(lambda: gk.g_unit)
md = S(lambda: idict(me), {}) or {}
for a in sorted(md.keys()):
    if a.startswith("__"): continue
    v = S(lambda a=a: md.get(a))
    if v is None or callable(v): continue
    if cname(v) in ("int", "float", "bool", "str"):
        P("ME  %-34s %s" % (a, R(v, 80)))
