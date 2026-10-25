# -*- coding: utf-8 -*-
# probe2 命令：把 GK.g_avatar 上的天赋来源看清楚。
# 2026-09-23 发现：准备阶段 final_genius_dict {unique_id: [终端天赋id...]} 与界面显示一致。
# 要搞清：键到底是什么、值是不是只有终端天赋、空值代表什么、怎么和场上/房里的人配对。
gk = GK
av = S(lambda: gk.g_avatar)
P("g_avatar = %s" % cname(av))

fg = S(lambda: av.final_genius_dict)
P("\n== final_genius_dict 全量 ==")
if isinstance(fg, dict):
    for k, v in fg.items():
        P("  %-28r -> %r" % (k, v))
else:
    P("  取不到: %r" % (fg,))

# 同族属性，挑名字里带 genius 的全部列出(截断)
P("\n== g_avatar 上其它 genius 属性 ==")
for a in sorted(S(lambda: list(idict(av).keys()), []) or []):
    if "genius" not in a.lower() or a == "final_genius_dict":
        continue
    P("  %-34s %-8s %s" % (a, cname(S(lambda a=a: idict(av).get(a))), R(S(lambda a=a: idict(av).get(a)), 110)))

# 房间里的人：找带 unique_id / uid 的容器，看能不能和 final_genius_dict 的键对上
P("\n== 找 unique_id 的出处 ==")
def dump_ids(obj, path, depth=0):
    d = S(lambda: idict(obj))
    if not isinstance(d, dict):
        return
    for a in sorted(d.keys()):
        if not isinstance(a, str) or a.startswith("__"):
            continue
        v = S(lambda a=a: d.get(a))
        if v is None or callable(v):
            continue
        low = a.lower()
        if "unique" in low or low in ("uid", "player_name", "pid", "cloth_id", "seat_id", "is_bot"):
            P("   %s.%-24s %s" % (path, a, R(v, 60)))
        if depth < 1 and any(w in low for w in ("member", "player", "seat", "team", "user")) \
           and isinstance(v, (list, tuple, dict)):
            items = list(v.values())[:6] if isinstance(v, dict) else list(v)[:6]
            for i, it in enumerate(items):
                if it is not None and not isinstance(it, (int, float, str, bool)):
                    P("  [%s.%s#%d %s]" % (path, a, i, cname(it)))
                    dump_ids(it, "%s.%s#%d" % (path, a, i), depth + 1)

me_u = S(lambda: gk.g_unit)
dump_ids(me_u, "g_unit")
room = S(lambda: me_u.room)
if room is not None:
    dump_ids(room, "room")
ubt = S(lambda: gk.unit_mgr.units_by_type, {}) or {}
for k in sorted(S(lambda: list(ubt.keys()), []) or []):
    for i, u in enumerate((S(lambda k=k: list(ubt.get(k, [])), []) or [])[:6]):
        cn = cname(u)
        if "Hall" in cn:      # 大厅家具，跳过
            continue
        P("  [键%s#%d %s]" % (k, i, cn))
        dump_ids(u, "ubt%s#%d" % (k, i))
