# -*- coding: utf-8 -*-
# probe2: 地上有一根镇静剂(ItemInjector)时跑。确认掉地道具有没有 Python 引用。
KW = ("item", "drop", "ground", "fall", "scatter", "scene_item", "loot", "pick", "discard", "throw")

gk = GK
P("== game_kernel 全局里: 名字或类名带道具/掉落关键字、且是非空容器/管理器 ==")
for k in sorted(S(lambda: list(vars(gk).keys()), [])):
    if not isinstance(k, str) or k.startswith("__"):
        continue
    v = S(lambda k=k: getattr(gk, k))
    cn = cname(v)
    hit = any(w in k.lower() for w in KW) or any(w in cn.lower() for w in KW)
    if not hit:
        continue
    # 非空容器 / 管理器都打出来
    P("  %-28s %-26s %s" % (k, cn, R(v, 80)))

P("\n== unit_mgr 上带道具/掉落关键字的属性(非 None) ==")
for a in sorted(S(lambda: list(idict(mgr).keys()), [])):
    if not isinstance(a, str) or a.startswith("__"):
        continue
    if any(w in a.lower() for w in KW):
        v = S(lambda a=a: idict(mgr)[a])
        if v is not None:
            P("  %-30s %-22s %s" % (a, cname(v), R(v, 70)))

# 直接找 ItemInjector(镇静剂) 这个类的实例在不在 Python 对象图里(通过 all_units 够不着就是没实体)
P("\n== all_units 里有没有 ItemInjector/落单 Item* ==")
found = False
for key, u in all_units():
    cn = cname(u)
    if cn.startswith("Item") or "inject" in cn.lower():
        found = True
        P("  [%s] %s uid=%s" % (key, cn, R(S(lambda u=u: u.uid), 12)))
if not found:
    P("  (all_units 里没有任何 Item* 实体 -> 掉地道具不在 units_by_type)")

# 看消失的 uid=1000001 是不是变成别的 type(被淘汰/上椅) + 它的 item_lst 去哪了
P("\n== 找 uid=1000001(掉镇静剂的人)现在在哪个 type ==")
t = ubt()
for k in S(lambda: sorted([x for x in t.keys() if isinstance(x, int)]), []):
    for u in (units_of(k) or []):
        if S(lambda u=u: u.uid) == 1000001:
            P("  找到 1000001 在 type=%s cls=%s item_lst=%s" % (
                k, cname(u), R(S(lambda u=u: list(u.item_lst)), 40)))
