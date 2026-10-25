# -*- coding: utf-8 -*-
# probe2: 区域选择阶段(3x3/3x4 格子, 求生者先选/监管后选)一次性全量抓取。
# 目标: 找"监管端能不能看到求生者选了哪格"的字段(dict/list)。60s 窗口, 一发抓全。
KW = ("area", "region", "select", "choose", "chosen", "pick", "grid", "born", "birth",
      "zone", "block", "map_", "vote", "site", "spawn", "location", "sel_", "_sel", "point", "cell")

def dump_kw(obj, label, show_all_names=False):
    names = sorted(S(lambda: list(idict(obj).keys()), []))
    if show_all_names:
        line = ""
        for a in names:
            if isinstance(a, str) and not a.startswith("__"):
                line += a + " "
                if len(line) > 110:
                    P("      | " + line); line = ""
        if line:
            P("      | " + line)
    for a in names:
        if not isinstance(a, str) or a.startswith("__"):
            continue
        if any(w in a.lower() for w in KW):
            v = S(lambda o=obj, a=a: idict(o)[a])
            P("    %-32s %-18s %s" % (a, cname(v), R(v, 120)))

# 1) ui_dict: 每个打开的 UI 对象 -> 类名 + 全属性名清单 + 选区关键字属性值
P("== ui_dict 里每个 UI 对象 ==")
uim = S(lambda: GK.g_ui_mgr)
ud = S(lambda: uim.ui_dict)
keys = S(lambda: list(ud.keys()), [])
P("  ui_dict keys = %s" % R(keys, 160))
for name in keys:
    uiobj = S(lambda name=name: ud[name])
    P("  [UI] %s = %s" % (name, cname(uiobj)))
    dump_kw(uiobj, name, show_all_names=True)

# 2) g_avatar(账号级, 求生者选择可能挂这, 像 final_genius_dict 那样)
P("\n== g_avatar 选区相关 ==")
dump_kw(S(lambda: GK.g_avatar), "g_avatar")

# 3) game_kernel 全局选区相关
P("\n== game_kernel 全局选区相关 ==")
gk = GK
for k in sorted(S(lambda: list(vars(gk).keys()), [])):
    if not isinstance(k, str) or k.startswith("__"):
        continue
    if any(w in k.lower() for w in KW):
        v = S(lambda k=k: getattr(gk, k))
        if callable(v) and not hasattr(v, "__dict__"):
            continue
        P("  %-30s %-24s %s" % (k, cname(v), R(v, 90)))

# 4) 现状(阶段确认)
P("\n== 现状 ==")
P("  me = %s" % cname(me))
t = ubt()
P("  units_by_type = %s" % R(S(lambda: {k: len(units_of(k) or []) for k in sorted([x for x in t.keys() if isinstance(x, int)])}), 200))
