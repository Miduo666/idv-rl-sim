# -*- coding: utf-8 -*-
# probe2 命令：准备阶段找"辅助特质"的存放位置(局内是 unit.support_skill_id，局外 unit 不存在)。
# 顺带把天赋页结构 _pid_genius 的键看清楚。
KW = ("support_skill", "leader_skill", "assist", "trait", "special_skill", "skill_id", "cur_skill")
FOLLOW = ("avatar", "city", "room", "team", "select", "prepare", "ready", "custom", "battle",
          "loadout", "equip", "data", "info", "setting", "config", "player", "role", "hero")

gk = GK
av = S(lambda: gk.g_avatar)
me = S(lambda: gk.g_unit)

P("== 天赋页结构 ==")
pages = S(lambda: av._pid_genius, {}) or {}
P("_pid_genius 键 = %s" % R(S(lambda: sorted(pages.keys())), 200))
p2g = S(lambda: av.pid_to_genius, {}) or {}
P("pid_to_genius[str(%s)] = %r" % (R(S(lambda: me.pid), 8), S(lambda: p2g.get(str(S(lambda: me.pid))))))
for k in (S(lambda: sorted(pages.keys()), []) or [])[:3]:
    pg = S(lambda k=k: pages.get(k))
    if isinstance(pg, dict):
        P("  页 %-8s 键 = %s" % (k, R(sorted(pg.keys()), 200)))

P("\n== 广度搜索：名字含 support_skill/leader/trait/assist 的属性 ==")
seen = set(); queue = []
for k in (S(lambda: sorted(vars(gk).keys()), []) or []):
    if not isinstance(k, str) or k.startswith("__"): continue
    v = S(lambda k=k: getattr(gk, k))
    if v is None or callable(v) or isinstance(v, (int, float, str, bool)): continue
    queue.append((v, "GK." + k, 0))
hits = 0
while queue and len(seen) < 8000:
    obj, path, depth = queue.pop(0)
    if id(obj) in seen: continue
    seen.add(id(obj))
    d = S(lambda: idict(obj))
    names = sorted(d.keys()) if isinstance(d, dict) else (S(lambda: sorted(attr_names(obj)), []) or [])
    for a in names:
        if not isinstance(a, str) or a.startswith("__"): continue
        low = a.lower()
        v = S(lambda a=a: d.get(a) if isinstance(d, dict) else getattr(obj, a))
        if v is None or callable(v): continue
        if any(w in low for w in KW):
            if v in ({}, [], set(), "", 0, False, None):   # 空值太多，只看有内容的
                continue
            P("★ %s.%s = %s   (%s)" % (path, a, R(v, 130), cname(v)))
            hits += 1
        if depth < 2 and any(w in low for w in FOLLOW) and not isinstance(v, (int, float, str, bool)):
            if isinstance(v, dict):
                for kk, vv in list(v.items())[:6]:
                    if vv is not None and not isinstance(vv, (int, float, str, bool)):
                        queue.append((vv, "%s.%s[%s]" % (path, a, kk), depth + 1))
            elif isinstance(v, (list, tuple, set)):
                for vv in list(v)[:6]:
                    if vv is not None and not isinstance(vv, (int, float, str, bool)):
                        queue.append((vv, "%s.%s[]" % (path, a), depth + 1))
            else:
                queue.append((v, "%s.%s" % (path, a), depth + 1))
P("\n扫过 %d 个对象，命中 %d 条" % (len(seen), hits))
