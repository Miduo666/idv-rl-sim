NAME={1000001:"yxz",1000002:"囚徒",1000003:"调香师",1000004:"邮差"}
def cg(o,nm):
    m=S(lambda: getattr(o,nm,None))
    if m is None: return "NA"
    return S(lambda: m()) if callable(m) else m
for u in (units_of(2) or []):
    d=S(lambda: idict(u),{}) or {}
    uid=d.get("uid"); mo=S(lambda: u.model)
    P("uid=%s %s | vif=%r model.visible=%r in_xray=%r is_show_xray=%r total_vis=%r const_vis=%r force_inv=%r occ_id=%r" % (
        uid, NAME.get(uid,"?"),
        cg(mo,"is_visible_in_this_frame"), cg(mo,"visible"),
        S(lambda: u.in_xray), cg(mo,"is_show_xray") if S(lambda: hasattr(mo,'is_show_xray')) else S(lambda: u.is_show_xray),
        S(lambda: u.total_visibility), S(lambda: u.const_visibility), S(lambda: u.force_invisible),
        cg(mo,"get_occlude_id")))
