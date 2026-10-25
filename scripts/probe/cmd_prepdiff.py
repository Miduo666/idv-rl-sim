# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：准备阶段单次快照，给 prepdiff60.ps1 反复投递、PC 侧做差分。
# 目的：我是监管时，对面求生者换天赋，看哪个数据源跟着变(找实时源)。
# 输出两部分：
#   KEY 行：已知候选源里每个求生者的终端天赋(人读)
#   ATTR 行：UIRoomWait / g_avatar 上每个非 UI 属性的 repr 哈希 + 预览 —— 用来发现"不在候选里"的实时源
# 不 sleep(命令在游戏线程里 exec)，时间序列由 PC 侧连续投递。
gk = GK
t0 = time.time()
P("TIME\t%.3f" % t0)

ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
panel = S(lambda: ui.get("UIRoomWait"))
pd = S(lambda: idict(panel), {}) or {} if panel is not None else {}
av = S(lambda: gk.g_avatar)
ad = S(lambda: idict(av), {}) or {}
P("PANEL\t%s\trole=%r" % (panel is not None, pd.get("role")))

def terms(v):
    if not isinstance(v, (list, tuple)): return repr(v)
    return repr([x for x in v if x in (8, 16, 24, 26, 32)] if all(isinstance(x, int) for x in v) else v)

pos = pd.get("uid2pos") or {}
# 1) eid_2_player_info(当前代码用的源)
for k, e in (pd.get("eid_2_player_info") or {}).items():
    if isinstance(e, dict) and e.get("role_type") == 2:
        P("KEY\te2pi\tseat=%s\teid=%s\t%s" % (pos.get(k), R(k, 30), terms(e.get("final_genius"))))
# 2) c_skill_data(求生者视角的实时源，监管视角应为空)
for r in (pd.get("c_skill_data") or []):
    P("KEY\tcskill\tseat=%s\teid=%s\t%s" % (pos.get(r[0]), R(r[0], 30), terms(r[4] if len(r) > 4 else None)))
# 3) g_avatar.final_genius_dict(键是 str(eid))
fg = ad.get("final_genius_dict") or {}
for k, v in fg.items():
    P("KEY\tfgdict\teid=%s\t%s" % (R(k, 30), terms(v)))
# 4) g_avatar.player_data_list
for e in (ad.get("player_data_list") or []):
    if isinstance(e, dict) and e.get("role_type") == 2:
        P("KEY\tpdl\tseat=%s\teid=%s\t%s" % (pos.get(e.get("eid")), R(e.get("eid"), 30), terms(e.get("final_genius"))))

# ATTR 行：两个对象上所有非 UI、非 callable 的属性
UI_CLS = ("Node", "Button", "Layout", "Sprite", "Label", "ScrollView", "Widget", "ImageView", "RichText",
          "CheckBox", "Slider", "EditBox", "ListView", "PageView", "RichTextEx55", "UIMatchState",
          "UIMatchCharName", "UIQuickChatSelect", "TextField", "Text", "LoadingBar")
for tag, d in (("ui", pd), ("av", ad)):
    for a in sorted(d.keys()):
        if not isinstance(a, str) or a.startswith("__"): continue
        v = d[a]
        if callable(v) and not isinstance(v, (dict, list, tuple, set)): continue
        if cname(v) in UI_CLS: continue
        r = S(lambda v=v: repr(v), "<repr失败>")
        if len(r) > 20000: r = r[:20000]
        P("ATTR\t%s.%s\t%x\t%s" % (tag, a, hash(r) & 0xffffffff, r[:160].replace("\t", " ").replace("\n", " ")))
P("END\t%.1fms" % ((time.time() - t0) * 1000))
