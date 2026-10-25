# -*- coding: utf-8 -*-
# probe2: 定位出生点选择数据挂在哪(不在 UIRoomWait)。线索: 事件 ON_ORDER_INFO_LST_CHANGED。
# 搜 g_avatar / game_kernel 全局 / cur_world, 找 order_info/birth/area/select/region/spawn/pick/map 相关属性。
KW = ("order_info", "order_lst", "birth", "area", "select", "region", "spawn", "pick",
      "choose", "choice", "map_select", "born", "grid", "zone", "preselect", "pre_select",
      "camp_pos", "start_pos", "point")

def scan(obj, label):
    P("== %s ==" % label)
    names = sorted(S(lambda: list(idict(obj).keys()), []))
    if not names:
        P("  (无属性或读不到)"); return
    for a in names:
        if not isinstance(a, str) or a.startswith("__"):
            continue
        if any(w in a.lower() for w in KW):
            v = S(lambda o=obj, a=a: idict(o)[a])
            P("  %-32s %-18s %s" % (a, cname(v), R(v, 110)))

scan(S(lambda: GK.g_avatar), "g_avatar")

# game_kernel 全局
P("\n== game_kernel 全局(名字含关键字) ==")
gk = GK
for k in sorted(S(lambda: list(vars(gk).keys()), [])):
    if not isinstance(k, str) or k.startswith("__"):
        continue
    if any(w in k.lower() for w in KW):
        v = S(lambda k=k: getattr(gk, k))
        if callable(v) and not hasattr(v, "__dict__"):
            continue
        P("  %-30s %-24s %s" % (k, cname(v), R(v, 90)))

# cur_world
cw = S(lambda: GK.g_world_mgr.cur_world)
scan(cw, "g_world_mgr.cur_world = %s" % cname(cw))

# 全局里所有 mgr 对象, 看类名带 birth/match/select/order 的
P("\n== game_kernel 全局里类名含 birth/match/order/select 的管理器 ==")
for k in sorted(S(lambda: list(vars(gk).keys()), [])):
    if not isinstance(k, str) or k.startswith("__"):
        continue
    v = S(lambda k=k: getattr(gk, k))
    cn = cname(v)
    if any(w in cn.lower() for w in ("birth", "match", "order", "select", "area", "region", "spawn")):
        P("  %-28s %s" % (k, cn))

P("\n== 现状 == me=%s ui=%s" % (cname(me), R(S(lambda: list(GK.g_ui_mgr.ui_dict.keys())), 100)))
