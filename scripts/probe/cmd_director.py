# -*- coding: utf-8 -*-
# probe2 命令(2026-10-18)：导演局/模仿者局定向快照。
# 目的：修 draw_Gui.cpp copycat extra 块的两个 bug——
#   (1) 导演傀儡(1211)其实是本机自身、被无条件画出来   -> 要知道哪个单位是 self、1211 跟 self 的关系
#   (2) 导演局里其他人全被盖成固定标签"导演"            -> 要知道 1210/1211 身上到底有没有 identity_id/copycat_index/position
# 不 sleep；在游戏主线程 exec，有时间上限。
import time
t0 = time.time()


def one(v, n=140):
    return R(v, n).replace("\t", " ").replace("\n", " ")


def num3(v):
    # 尝试把 Vector3 之类拆成 (x,y,z)；拿不到就 repr
    for combo in (("x", "y", "z"), ("X", "Y", "Z")):
        t = S(lambda: tuple(getattr(v, a) for a in combo))
        if t is not None:
            return "(%s)" % ",".join("%.2f" % c if isinstance(c, float) else str(c) for c in t)
    return one(v, 60)


def unit_line(u):
    d = S(lambda: idict(u), {}) or {}
    uid = d.get("uid")
    uq = d.get("unique_id")
    ident = d.get("identity_id")
    idx = d.get("copycat_index")
    isself = d.get("is_self")
    pos = d.get("position")
    # 模型文件名
    mdl = S(lambda: u.model.filename) or S(lambda: getattr(u.model, "model_path", None))
    vis = S(lambda: u.model.visible)
    # 冗余身份来源：combat_unit.components[*].identity_id
    comp_id = None
    comps = S(lambda: u.combat_unit.components, None)
    if isinstance(comps, dict):
        for ck, cv in list(comps.items())[:40]:
            ci = S(lambda cv=cv: getattr(cv, "identity_id", None))
            if ci is not None:
                comp_id = (ck, ci)
                break
    P("  uid=%s unique=%s ident=%s idx=%s self=%s vis=%s" % (uid, uq, ident, idx, isself, vis))
    P("    pos=%s model=%s comp_id=%s" % (num3(pos) if pos is not None else None, one(mdl, 70), comp_id))


gk = GK
# 1) 模式判定
cw = S(lambda: gk.g_world_mgr.cur_world)
P("WORLD\tcur_world=%s wt=%s" % (cname(cw), S(lambda: cw.world_type)))
P("UI\t%s" % one(S(lambda: list(gk.g_ui_mgr.ui_dict.keys()), []), 300))

# 2) 自身：g_cam_ctrl.unit
me = S(lambda: gk.g_cam_ctrl.unit)
P("SELF\t%s  (g_cam_ctrl.unit)" % cname(me))
if me is not None:
    unit_line(me)
me_id = id(me) if me is not None else 0

# 3) 所有 units_by_type 键：类名 + 数量
keys = sorted([x for x in (S(lambda: list(ubt().keys()), []) or []) if isinstance(x, int)])
P("KEYS")
for k in keys:
    us = S(lambda k=k: units_of(k), []) or []
    cn = cname(us[0]) if us else "?"
    P("  [%d] %s  x%d" % (k, cn, len(us)))

# 4) 重点键逐单位 dump：1088 号码簿 + 1210/1211 导演 + 1203 食人鬼 + 1089 鬼魂
for k in (1088, 1210, 1211, 1203, 1089):
    if time.time() - t0 > 1.4:
        P("TRUNC\tat key %d" % k)
        break
    us = S(lambda k=k: units_of(k), []) or []
    if not us:
        continue
    P("DUMP[%d] %s x%d" % (k, cname(us[0]), len(us)))
    for u in us[:14]:
        mark = "  <== SELF" if id(u) == me_id else ""
        if mark:
            P(mark)
        unit_line(u)

P("END\t%.1fms" % ((time.time() - t0) * 1000))
