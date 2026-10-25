# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：单次采样 —— 治疗字段 + 受伤类字段 + 监管当前动画。PC 侧重复投递成时间序列。
KW = ("hp", "life", "blood", "hurt", "injur", "fall", "down", "cure", "heal", "self_")
h = (units_of(1) or [None])[0]
hd = S(lambda: idict(h), {}) or {}
ap = hd.get("animation_parameter")
P("t=%.2f 监管动画=%s cast=%s" % (S(lambda: h.now, 0) or 0, R(ap[0] if isinstance(ap, tuple) and ap else ap, 30),
                                  R(S(lambda: h.skill_mgr.last_cast_skill_id), 10)))
for u in units_of(2):
    d = S(lambda: idict(u), {}) or {}
    ap = d.get("animation_parameter")
    sc = []
    for a in sorted(d.keys()):
        if not isinstance(a, str): continue
        v = d[a]
        if isinstance(v, bool) or not isinstance(v, (int, float)): continue
        if v == 0: continue
        if any(w in a.lower() for w in KW): sc.append("%s=%s" % (a, R(v, 12)))
    P("  uid=%s 动画=%s cpc=%r csc=%r cured_uid=%r dbg=%s | %s" % (
        d.get("uid"), R(ap[0] if isinstance(ap, tuple) and ap else ap, 20), d.get("cured_process_client"),
        d.get("cured_speed_client"), d.get("cured_uid"), R(d.get("debug_record_cured_info"), 80), R(sc, 400)))
