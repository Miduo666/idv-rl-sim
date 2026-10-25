import math
def call(o,nm,*a):
    m=S(lambda: getattr(o,nm,None))
    if m is None: return "_NA_"
    return S(lambda: m(*a)) if callable(m) else m
hp=S(lambda: me.position)
def dist(p):
    try: return math.hypot(p[0]-hp[0], p[2]-hp[2])
    except: return -1
for u in (units_of(2) or []):
    d=S(lambda: idict(u),{}) or {}
    mo=S(lambda: u.model)
    mp=S(lambda: mo.get_res_name()) or S(lambda: getattr(mo,'model_path',None)) or S(lambda: d.get('model_path'))
    p=S(lambda: u.position)
    P("uid=%s iid=%s vif=%r pos=%s dist=%.0f model=%s" % (
        d.get("uid"), d.get("identity_id"), call(mo,"is_visible_in_this_frame"),
        R(p,30), dist(p) if p else -1, R(mp,60)))
# 扫 model 方法里 occlusion/raycast/depth/query 相关
mo=S(lambda: (units_of(2) or [None])[0].model)
ns=S(lambda: sorted(set(dir(mo))),[]) or []
KW=("occlu","ray","depth","query","cull","obstruct","block","los","line_of","behind","cover","hidden","trace","hit")
P("occ/ray methods: %s" % R([a for a in ns if any(k in a.lower() for k in KW)],500))
