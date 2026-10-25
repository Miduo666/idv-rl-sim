# -*- coding: utf-8 -*-
# probe2 命令：准备阶段找天赋来源 第二轮。
#   a) units_by_type 全部键下的单位逐个列出(类名 + 身份类属性)，看队友是不是也是"城市单位"
#   b) 从 game_kernel 做三层广度搜索，只沿"房间/队伍/界面"类的属性下钻，
#      打印任何名字含 genius/psv/talent 的属性
KW_G = ("genius", "psv", "talent", "passive")
KW_ID = ("pid", "cloth", "uid", "name", "seat", "index", "is_", "char")
FOLLOW = ("city", "room", "team", "member", "player", "seat", "ui", "view", "panel",
          "select", "prepare", "ready", "custom", "lobby", "match", "role", "hero", "data")

gk = GK
P("room = %s   g_unit = %s" % (cname(S(lambda: gk.g_unit.room)), cname(S(lambda: gk.g_unit))))

# ---- a) units_by_type 全量 ----
ubt = S(lambda: gk.unit_mgr.units_by_type, {}) or {}
P("\n== units_by_type 全量 ==")
for k in sorted(S(lambda: list(ubt.keys()), []) or []):
    lst = S(lambda k=k: list(ubt.get(k, [])), []) or []
    P("键 %-6s %d 个" % (k, len(lst)))
    for u in lst[:8]:
        P("   %s" % cname(u))
        names = S(lambda u=u: sorted(idict(u).keys()), []) or []
        shown = 0
        for a in names:
            low = a.lower()
            if any(w in low for w in KW_G):
                P("      ★ %s = %s" % (a, R(S(lambda a=a, u=u: idict(u).get(a)), 140)))
                shown += 1
            elif any(w in low for w in KW_ID) and shown < 14:
                v = S(lambda a=a, u=u: idict(u).get(a))
                if v is not None and not callable(v) and v not in ({}, [], set(), ""):
                    P("        %-26s %s" % (a, R(v, 60)))
                    shown += 1

# ---- b) 三层广度搜索 ----
P("\n== 广度搜索(沿房间/队伍/界面类属性下钻三层) ==")
seen = set()
queue = []
top = S(lambda: sorted(vars(gk).keys()), []) or []
for k in top:
    if not isinstance(k, str) or k.startswith("__"):
        continue
    v = S(lambda k=k: getattr(gk, k))
    if v is None or callable(v) or isinstance(v, (int, float, str, bool)):
        continue
    queue.append((v, "GK." + k, 0))

hits = 0
while queue and len(seen) < 6000:
    obj, path, depth = queue.pop(0)
    if id(obj) in seen:
        continue
    seen.add(id(obj))
    d = S(lambda: idict(obj))
    names = sorted(d.keys()) if isinstance(d, dict) else (S(lambda: sorted(attr_names(obj)), []) or [])
    for a in names:
        if not isinstance(a, str) or a.startswith("__"):
            continue
        low = a.lower()
        v = S(lambda a=a: d.get(a) if isinstance(d, dict) else getattr(obj, a))
        if v is None or callable(v):
            continue
        if any(w in low for w in KW_G):
            P("★ %s.%s = %s   (%s)" % (path, a, R(v, 160), cname(v)))
            hits += 1
        if depth < 2 and any(w in low for w in FOLLOW) and not isinstance(v, (int, float, str, bool)):
            if isinstance(v, dict):
                for kk, vv in list(v.items())[:8]:
                    if not isinstance(vv, (int, float, str, bool)) and vv is not None:
                        queue.append((vv, "%s.%s[%s]" % (path, a, kk), depth + 1))
            elif isinstance(v, (list, tuple, set)):
                for vv in list(v)[:8]:
                    if not isinstance(vv, (int, float, str, bool)) and vv is not None:
                        queue.append((vv, "%s.%s[]" % (path, a), depth + 1))
            else:
                queue.append((v, "%s.%s" % (path, a), depth + 1))

P("\n扫过对象 %d 个，天赋类命中 %d 条" % (len(seen), hits))
