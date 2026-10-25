# -*- coding: utf-8 -*-
# probe2 命令：准备阶段找天赋来源。
# 前提推理：客户端界面上能看到队友带什么天赋，那数据就一定在客户端内存里；
# 只是准备阶段 units_by_type 里没有玩家单位(实测)，所以不可能挂在 unit 上 —— 要换个地方找。
# 做法：不猜字段名，从 game_kernel 顶层往下两层，把属性名里含 genius/psv/talent 的东西全打出来，
# 同时把"看着像玩家列表"的结构(含 pid/cloth/uid/name 的容器)一并列出。
KW_G = ("genius", "psv", "talent", "passive")
KW_P = ("pid", "cloth", "uid", "player", "member", "team", "seat", "role", "hero", "char")

gk = GK
P("== 阶段 ==")
P("g_unit=%s  room=%s" % (cname(S(lambda: gk.g_unit)), cname(S(lambda: gk.g_unit.room))))
ubt = S(lambda: gk.unit_mgr.units_by_type, {}) or {}
P("units_by_type 键 = %s" % sorted([k for k in S(lambda: list(ubt.keys()), [])]))

def short(v, n=90):
    return R(v, n)

def scan(obj, path, depth, seen):
    """打印 obj 上名字命中关键字的属性；depth>0 时对容器/实例继续下钻一层"""
    if obj is None or id(obj) in seen or len(seen) > 4000:
        return
    seen.add(id(obj))
    names = S(lambda: list(idict(obj).keys()), None)
    if names is None:
        names = S(lambda: [a for a in attr_names(obj)], []) or []
    for k in sorted(names):
        if not isinstance(k, str) or k.startswith("__"):
            continue
        low = k.lower()
        hit_g = any(w in low for w in KW_G)
        hit_p = any(w in low for w in KW_P)
        if not (hit_g or hit_p) and depth <= 0:
            continue
        v = S(lambda k=k: idict(obj).get(k) if idict(obj) else getattr(obj, k))
        if v is None or callable(v):
            continue
        if hit_g:
            P("★天赋? %s.%s = %s   (%s)" % (path, k, short(v, 160), cname(v)))
        elif hit_p:
            P("  玩家? %s.%s = %s" % (path, k, short(v, 70)))
        if depth > 0 and (hit_g or hit_p):
            # 容器就把元素也扫一层
            items = S(lambda: list(v.values())[:6] if isinstance(v, dict) else (list(v)[:6] if isinstance(v, (list, tuple)) else [v]), [])
            for it in (items or []):
                if it is None or isinstance(it, (int, float, str, bool)):
                    continue
                scan(it, "%s.%s[]" % (path, k), depth - 1, seen)

seen = set()
P("\n== game_kernel 顶层(名字含关键字的属性) ==")
top = S(lambda: sorted(vars(gk).keys()), []) or []
P("顶层属性 %d 个" % len(top))
for k in top:
    if not isinstance(k, str) or k.startswith("__"):
        continue
    low = k.lower()
    v = S(lambda k=k: getattr(gk, k))
    if v is None or callable(v):
        continue
    cn = cname(v)
    if any(w in low for w in KW_G):
        P("★ GK.%-28s %-30s %s" % (k, cn, short(v, 120)))
    # 管理器类一律下钻一层
    if any(w in low for w in KW_P) or any(w in cn.lower() for w in ("mgr", "manager", "room", "team", "match", "city")):
        P("[下钻] GK.%-24s %s" % (k, cn))
        scan(v, "GK." + k, 1, seen)

P("\n== 本机单位与 room ==")
me_u = S(lambda: gk.g_unit)
if me_u is not None:
    scan(me_u, "g_unit", 1, seen)
    room = S(lambda: me_u.room)
    if room is not None:
        scan(room, "room", 1, seen)
