# -*- coding: utf-8 -*-
# probe2 命令: 找"箱子开出掉地上的道具"的实体/字段。在游戏进程内 exec。
# 在身上的道具(item_lst)已知, 这里重点找掉地上的那种 + 关键字全局/管理器。
KW = ("item", "box", "chest", "treasure", "drop", "ground", "cellar", "pick",
      "supply", "prop", "loot", "chest", "spawn", "fall")

P("== units_by_type 全表 (key / 类名 / 数量) ==")
t = ubt()
for k in S(lambda: sorted([x for x in t.keys() if isinstance(x, int)]), []):
    us = units_of(k); c = {}
    for u in us:
        c[cname(u)] = c.get(cname(u), 0) + 1
    P("  [%s] n=%d %s" % (k, len(us), c))

P("\n== game_kernel 顶层含道具/箱子关键字的全局 ==")
gk = GK
for k in sorted(S(lambda: list(vars(gk).keys()), [])):
    if not isinstance(k, str) or k.startswith("__"):
        continue
    if any(w in k.lower() for w in KW):
        v = S(lambda k=k: getattr(gk, k))
        if callable(v) and not hasattr(v, "__dict__"):
            continue
        P("  %-30s %-24s %s" % (k, cname(v), R(v, 90)))

P("\n== 求生者 item_lst (在身上, 已知, 确认字段) ==")
for u in (units_of(2) or []):
    uid = S(lambda: u.uid)
    items = S(lambda: list(u.item_lst), []) or []
    P("  civ uid=%s item_lst n=%d" % (R(uid, 12), len(items)))
    for i, it in enumerate(items):
        P("     [%d] %s id=%s name=%s remain=%s/%s inuse=%s" % (
            i, cname(it), R(S(lambda it=it: it.item_id), 8), R(S(lambda it=it: it.item_name), 18),
            R(S(lambda it=it: it._remain_use_times), 6), R(S(lambda it=it: it._init_use_times), 6),
            R(S(lambda it=it: it._b_in_use), 6)))

# 顺带: 场上所有单位里, 类名/属性名带道具关键字的(抓掉地上道具可能挂的单位)
P("\n== 所有单位中类名含道具关键字的 ==")
for k, u in all_units():
    cn = cname(u)
    if any(w in cn.lower() for w in KW):
        P("  [%s] %s uid=%s pos=%s" % (k, cn, R(S(lambda u=u: u.uid), 12), R(S(lambda u=u: u.position), 40)))
