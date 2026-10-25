# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24 第二轮)：combat_unit 上的状态/动作、全部道具的数值字段、治疗字段快照。
# 不 sleep：要时间序列就由 PC 侧重复投递。
gk = GK
t0 = time.time()

def scalars(o, kw=None, n=60):
    d = S(lambda: idict(o), {}) or {}
    out = []
    for a in sorted(d.keys()):
        if not isinstance(a, str) or a.startswith("__"): continue
        v = d[a]
        if isinstance(v, bool) or isinstance(v, (int, float)) or (isinstance(v, (list, tuple)) and len(v) <= 6):
            if kw and not any(w in a.lower() for w in kw): continue
            out.append("%s=%s" % (a, R(v, 40)))
    return out

P("now=%s" % R(S(lambda: units_of(1)[0].now), 20))

# ---------- 一、combat_unit ----------
P("== 一、combat_unit ==")
KW = ("state", "action", "anim", "dir", "forward", "move", "stage")
for ut in (1, 2):
    for u in units_of(ut)[:2]:
        cu = S(lambda: idict(u).get("combat_unit"), "<无此属性>")
        P("  [%d] %s uid=%s combat_unit=%s" % (ut, cname(u), S(lambda: u.uid), cname(cu) if cu != "<无此属性>" else cu))
        if cu in (None, "<无此属性>"): continue
        cd = S(lambda: idict(cu), {}) or {}
        P("     共 %d 条属性" % len(cd))
        P("     关键字命中: %s" % R(scalars(cu, KW), 900))
        for nm in ("state", "_state", "status", "state_id", "action", "action_id", "direction", "dir", "forward",
                   "position", "visual_position", "logic_position", "pos", "world_position"):
            if nm in cd: P("     .%-16s %s" % (nm, R(cd[nm], 80)))

# 单位本体上名字带 state/action/anim 的标量(combat_unit 不存在时的备选)
P("\n== 二、单位本体上 state/action/anim 类标量 ==")
for ut in (1, 2):
    u = (units_of(ut) or [None])[0]
    if u is None: continue
    P("  [%d] %s: %s" % (ut, cname(u), R(scalars(u, ("state", "action", "anim")), 1500)))

# ---------- 三、全部道具 ----------
P("\n== 三、全部 item_lst ==")
for ut in (2, 1):
    for u in units_of(ut):
        for i, it in enumerate(S(lambda: list(u.item_lst), []) or []):
            P("  [%d] uid=%s item[%d] %s: %s" % (ut, S(lambda: u.uid), i, cname(it), R(scalars(it), 700)))

# ---------- 四、治疗字段快照 ----------
P("\n== 四、治疗字段 ==")
for u in units_of(2):
    d = S(lambda: idict(u), {}) or {}
    P("  uid=%s hp=%s cured_process_client=%r cured_speed_client=%r cured_uid=%r debug=%r self_cure=%s" % (
        d.get("uid"), R(d.get("hp", d.get("_hp")), 12), d.get("cured_process_client"), d.get("cured_speed_client"),
        d.get("cured_uid"), d.get("debug_record_cured_info"),
        R([(a, d[a]) for a in d if isinstance(a, str) and "self_cure" in a and isinstance(d[a], (int, float, bool))], 200)))

P("\n# 用时 %.1f ms" % ((time.time() - t0) * 1000))
