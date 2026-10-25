# -*- coding: utf-8 -*-
# probe2 命令：监管视角的准备阶段 —— 还能不能读到求生者天赋？自己的天赋和辅助特质在哪？
gk = GK
av = S(lambda: gk.g_avatar)
me = S(lambda: gk.g_unit)
P("g_unit=%s pid=%s cloth_id=%s uid=%s  room=%s" % (
    cname(me), R(S(lambda: me.pid), 10), R(S(lambda: me.cloth_id), 10),
    R(S(lambda: me.uid), 10), cname(S(lambda: me.room))))
ubt = S(lambda: gk.unit_mgr.units_by_type, {}) or {}
P("units_by_type 键 = %s" % sorted([k for k in S(lambda: list(ubt.keys()), [])]))

P("\n== final_genius_dict(监管视角) ==")
fg = S(lambda: av.final_genius_dict)
if isinstance(fg, dict):
    for k, v in fg.items():
        P("  %-28r -> %r" % (k, v))
else:
    P("  取不到: %r" % (fg,))

P("\n== 自己当前角色的天赋页 ==")
pid = S(lambda: me.pid)
p2g = S(lambda: av.pid_to_genius, {}) or {}
page_id = S(lambda: p2g.get(str(pid)))
P("  pid=%s -> 天赋页 id=%r" % (pid, page_id))
pages = S(lambda: av._pid_genius, {}) or {}
pg = S(lambda: pages.get(str(page_id))) if page_id is not None else None
if isinstance(pg, dict):
    for k in ("page_id", "page_type", "page_name", "genius_points", "genius_dict", "support_skill_id", "genius_data"):
        if k in pg:
            P("  %-18s %s" % (k, R(pg.get(k), 220)))
    for k in sorted(pg.keys()):
        if k not in ("page_id", "page_type", "page_name", "genius_points", "genius_dict", "genius_data"):
            P("  其它 %-14s %s" % (k, R(pg.get(k), 120)))
else:
    P("  页内容取不到: %r" % (pg,))

P("\n== 当前生效的监管/求生天赋页 ==")
P("  genius_data_b_active_page(监管) = %s" % R(S(lambda: av.genius_data_b_active_page), 300))
P("  genius_data_c_active_page(求生) = %s" % R(S(lambda: av.genius_data_c_active_page), 300))

P("\n== g_avatar 上名字含 support/skill/leader/trait 的属性 ==")
for a in sorted(S(lambda: list(idict(av).keys()), []) or []):
    low = a.lower()
    if not any(w in low for w in ("support", "skill", "leader", "trait", "final")):
        continue
    v = S(lambda a=a: idict(av).get(a))
    if callable(v):
        continue
    P("  %-34s %-9s %s" % (a, cname(v), R(v, 150)))
