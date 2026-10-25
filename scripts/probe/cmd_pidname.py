# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：找角色 pid -> 名字 的配表。列出名字像角色表的 DM 属性，打出 [66]/[1]/[3] 摘要。
dm = S(lambda: GK.DM)
names = S(lambda: [a for a in dir(dm) if not a.startswith("__")], []) or []
KW = ("role", "character", "hero", "char_", "player_data", "butcher_data", "civilian_data", "pid")
for a in names:
    if not any(w in a.lower() for w in KW): continue
    v = S(lambda a=a: getattr(dm, a))
    if not isinstance(v, dict) or not (30 <= len(v) <= 3000): continue
    ks = S(lambda: sorted([k for k in v.keys() if isinstance(k, int)])[:6], [])
    P("DM.%-36s n=%-5d keys=%s" % (a, len(v), ks))
    for k in (66, 1, 3):
        if k in v: P("    [%d] %s" % (k, R(v[k], 230)))
