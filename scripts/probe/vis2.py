# 验证 is_visible_in_this_frame 是否反映遮挡 + 挖骨骼可达性
def call(o,nm):
    m=S(lambda o=o,nm=nm: getattr(o,nm,None))
    if m is None: return "_NA_"
    if callable(m): return S(lambda: m())
    return m
me_pos=S(lambda: me.position)
P("hunter pos=%s" % R(me_pos,40))
for u in (units_of(2) or []):
    d=S(lambda: idict(u),{}) or {}
    mo=S(lambda: u.model)
    ivf=call(mo,"is_visible_in_this_frame")
    P("uid=%s vif=%r model.visible=%r total_vis=%r in_xray=%r const_vis=%r force_inv=%r pos=%s" % (
        d.get("uid"), ivf, S(lambda: mo.visible), S(lambda: u.total_visibility),
        S(lambda: u.in_xray), S(lambda: u.const_visibility), S(lambda: u.force_invisible),
        R(S(lambda: u.position),36)))
# 骨骼可达性：动画组件
u0=(units_of(2) or [None])[0]
for cn in ("_anim_data_component","_anim_graph_component"):
    c=S(lambda cn=cn: getattr(u0,cn,None))
    if c is None: P("%s=None"%cn); continue
    ns=S(lambda: sorted(x for x in attr_names(c) if isinstance(x,str)),[]) or []
    bh=[a for a in ns if any(k in a.lower() for k in ("bone","joint","skelet","node","pose","socket","world","pos","transform","matrix","get_"))]
    P("%s type=%s n=%d cand=%s" % (cn, cname(c), len(ns), R(bh,500)))
