# 可见性(遮挡) + 骨骼/animator 可达性 探针
VKW=("visib","xray","invisi","render","occlu","transparent","cull","alpha","show","hide")
BKW=("bone","skelet","joint","pose","anim","node","matrix","transform")
VIS=("is_visible_in_this_frame","in_xray","is_show_xray","const_visibility",
     "force_invisible","total_visibility","visible","is_visible","render_visible")
def anames(o): return S(lambda: sorted(x for x in attr_names(o) if isinstance(x,str)), []) or []
def scan(o, tag):
    if o is None: P("%s = None" % tag); return
    ns=anames(o)
    vh=[a for a in ns if any(k in a.lower() for k in VKW)]
    bh=[a for a in ns if any(k in a.lower() for k in BKW)]
    P("%s type=%s" % (tag, cname(o)))
    if vh: P("   vis*: %s" % R(vh,300))
    if bh: P("   bone/anim*: %s" % R(bh,300))
    got=[]
    for nm in VIS:
        v=S(lambda o=o,nm=nm: getattr(o,nm,"_NA_"))
        if v!="_NA_": got.append("%s=%r"%(nm,v))
    if got: P("   VIS_VALUES: %s" % R(got,400))
u=(units_of(2) or [None])[0]
P("=== survivor uid=%s ===" % S(lambda: u.uid))
scan(u,"unit")
scan(S(lambda: u.model),"unit.model")
scan(S(lambda: u.combat_unit),"unit.combat_unit")
scan(S(lambda: u.animation_controller),"unit.animation_controller")
scan(S(lambda: u.animator),"unit.animator")
