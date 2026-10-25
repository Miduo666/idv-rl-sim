# -*- coding: utf-8 -*-
# 趁监管正【牵气球】，dump 监管本体 + 求生者单位上 carry/balloon/catch/struggle 等相关字段的活值，
# 找出「正在牵气球」的状态字段，以及「牵的是谁(uid)」。被扛的求生者侧也一并 dump。
KW = ("carry", "balloon", "ballon", "catch", "struggle", "struggl", "captiv",
      "hostage", "hang", "rescue", "body_state", "is_down", "knock", "dying",
      "picked", "pick_up", "on_chair", "struggle_process")

def dump(obj, label):
    P("== %s : %s  uid=%s ==" % (label, cname(obj), R(S(lambda: obj.uid), 10)))
    d = S(lambda: idict(obj))
    names = sorted(d.keys()) if isinstance(d, dict) else (S(lambda: sorted(attr_names(obj)), []) or [])
    n = 0
    for a in names:
        if not isinstance(a, str) or a.startswith("__"):
            continue
        low = a.lower()
        if not any(w in low for w in KW):
            continue
        v = S(lambda a=a: d.get(a) if isinstance(d, dict) else getattr(obj, a))
        if callable(v):
            continue
        P("   %-36s = %s   (%s)" % (a, R(v, 100), cname(v)))
        n += 1
    if n == 0:
        P("   (无匹配字段)")

gk = GK
me = S(lambda: gk.g_unit)
cam = S(lambda: gk.g_cam_ctrl.unit)
P("g_unit=%s   g_cam_ctrl.unit=%s" % (cname(me), cname(cam)))
if me is not None:
    dump(me, "g_unit(主角色)")
if cam is not None and id(cam) != id(me):
    dump(cam, "cam.unit(当前操控)")

um = S(lambda: gk.unit_mgr)
ubt = S(lambda: um.units_by_type, {}) or {}
P("\nunits_by_type 键 = %s" % R(S(lambda: sorted(ubt.keys())), 200))

P("\n---- 监管 units_by_type[1] ----")
for u in (S(lambda: list(ubt.get(1, [])), []) or []):
    dump(u, "监管[1]")

P("\n---- 求生者 units_by_type[2] ----")
for u in (S(lambda: list(ubt.get(2, [])), []) or []):
    dump(u, "求生者[2]")
