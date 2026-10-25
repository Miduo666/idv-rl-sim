# -*- coding: utf-8 -*-
# probe2 命令：找"当前实时选中的辅助特质"。
# 现象：用户已把特质改成移形(8)，但 player_data_list / eid_2_player_info 里仍是 [4](巡视者)。
# 说明那份记录是进房时同步的，不跟随界面选择。真正实时的值在别处。
# 做法：a) 把 UIRoomWait 上所有非 UI 节点的属性全列出来(小值优先)
#       b) 全图宽搜，找值等于 8 或 [8] 且名字与技能/特质沾边的属性
#       c) 顺便看 article_setting 里的每角色配置
gk = GK
av = S(lambda: gk.g_avatar)
ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
panel = None
for k, v in (S(lambda: list(ui.items()), []) or []):
    if "RoomWait" in str(k) or "RoomWait" in cname(v):
        panel = v; break

UI_CLS = ("Node", "Button", "Layout", "Sprite", "Label", "ScrollView", "Widget", "ImageView",
          "RichText", "CheckBox", "Slider", "EditBox", "ListView", "PageView", "RichTextEx55",
          "UIMatchState", "UIMatchCharName", "UIQuickChatSelect")

if panel is None:
    P("没有 UIRoomWait")
else:
    d = S(lambda: idict(panel), {}) or {}
    P("== UIRoomWait 全部非 UI 属性 ==")
    for a in sorted(d.keys()):
        if a.startswith("__"): continue
        v = S(lambda a=a: d.get(a))
        if v is None or callable(v): continue
        cn = cname(v)
        if cn in UI_CLS: continue
        P("  %-34s %-10s %s" % (a, cn, R(v, 110)))

P("\n== 全图宽搜：值是 8 / [8] / (8,) 且名字沾技能的属性 ==")
seen = set(); queue = []
for k in (S(lambda: sorted(vars(gk).keys()), []) or []):
    if not isinstance(k, str) or k.startswith("__"): continue
    v = S(lambda k=k: getattr(gk, k))
    if v is None or callable(v) or isinstance(v, (int, float, str, bool)): continue
    queue.append((v, "GK." + k, 0))
hits = 0
while queue and len(seen) < 4000:
    obj, path, depth = queue.pop(0)
    if id(obj) in seen: continue
    seen.add(id(obj))
    if cname(obj) in UI_CLS: continue
    d2 = S(lambda: idict(obj))
    if not isinstance(d2, dict): continue
    for a in sorted(d2.keys()):
        if not isinstance(a, str) or a.startswith("__"): continue
        v = S(lambda a=a: d2.get(a))
        if v is None or callable(v): continue
        low = a.lower()
        is8 = (v == 8) or (isinstance(v, (list, tuple)) and len(v) == 1 and v[0] == 8)
        if is8 and any(w in low for w in ("skill", "support", "assist", "trait", "select", "cur", "id")):
            P("★ %s.%s = %r" % (path, a, v)); hits += 1
        if depth < 1 and not isinstance(v, (int, float, str, bool, bytes)):
            if isinstance(v, dict):
                for vv in (S(lambda: list(v.values())[:4], []) or []):
                    if vv is not None and not isinstance(vv, (int, float, str, bool)):
                        queue.append((vv, "%s.%s[]" % (path, a), depth + 1))
            elif isinstance(v, (list, tuple, set)):
                for vv in (S(lambda: list(v)[:4], []) or []):
                    if vv is not None and not isinstance(vv, (int, float, str, bool)):
                        queue.append((vv, "%s.%s[]" % (path, a), depth + 1))
            else:
                queue.append((v, "%s.%s" % (path, a), depth + 1))
P("扫过 %d 个对象，命中 %d 条" % (len(seen), hits))

P("\n== article_setting 里带 skill/support 的键 ==")
art = S(lambda: idict(av).get("article_setting"), {}) or {}
if isinstance(art, dict):
    for k in sorted(art.keys()):
        if any(w in str(k).lower() for w in ("skill", "support", "assist", "trait")):
            P("  %-28s %s" % (k, R(art.get(k), 150)))
