# -*- coding: utf-8 -*-
# probe2: 红夫人镜面来源调研 —— MaryMirrorUnit(246).position/direction 的类型/值/时机，
# 对照 本体 + MaryMirrorImageUnit(247) 的垂直平分线。用于把镜线来源迁到 Python 权威值。
# 不 sleep；主线程 exec。用户在局内反复「准备放镜→放下」，PC 侧连续采样抓切换瞬间。
import time
t0 = time.time()


def vec(v):
    if v is None:
        return "None"
    tn = S(lambda: type(v).__name__, "?")
    for combo in (("x", "y", "z"), ("X", "Y", "Z")):
        t = S(lambda c=combo: tuple(float(getattr(v, a)) for a in c))
        if t is not None:
            return "%s .%s=(%.3f,%.3f,%.3f)" % (tn, "/".join(combo), t[0], t[1], t[2])
    t = S(lambda: (float(v[0]), float(v[1]), float(v[2])))
    if t is not None:
        return "%s [0/1/2]=(%.3f,%.3f,%.3f)" % (tn, t[0], t[1], t[2])
    return "%s repr=%s" % (tn, R(v, 80))


def dump(u, tag):
    d = S(lambda: idict(u), {}) or {}
    pos = d.get("position")
    dirv = S(lambda: getattr(u, "direction"))
    vis = S(lambda: u.model.visible)
    mdl = S(lambda: u.model.filename)
    same = S(lambda: type(u.position) is type(u.direction))
    dn = None
    if dirv is not None:
        dn = S(lambda: (float(dirv.x) ** 2 + float(dirv.y) ** 2 + float(dirv.z) ** 2) ** 0.5)
    P("  %s id=%x vis=%s mdl=%s" % (tag, id(u), vis, R(mdl, 50)))
    P("    position = %s" % vec(pos))
    P("    direction= %s  |dir|=%s same_type=%s" % (vec(dirv), ("%.3f" % dn if dn else dn), same))


P("UI\t%s" % R(S(lambda: list(GK.g_ui_mgr.ui_dict.keys()), []), 200))
me = S(lambda: GK.g_cam_ctrl.unit)
P("SELF\t%s" % cname(me))
if me is not None:
    dm = S(lambda: idict(me), {}) or {}
    P("  self.position = %s" % vec(dm.get("position")))
    sk = S(lambda: me.skill_mgr.cur_skill)
    if sk is None:
        sk = S(lambda: me.cur_skill)
    P("  cur_skill=%s" % cname(sk))

for k in (246, 247):
    us = S(lambda k=k: units_of(k), []) or []
    P("[%d] %s x%d" % (k, cname(us[0]) if us else "?", len(us)))
    for u in us[:4]:
        dump(u, "u")

P("END\t%.1fms" % ((time.time() - t0) * 1000))
