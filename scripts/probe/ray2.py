gcc=S(lambda: GK.g_cam_ctrl)
pd=S(lambda: gcc.get_pos_dir())
P("cam get_pos_dir=%s" % R(pd,120))
campos=S(lambda: pd[0]) if isinstance(pd,tuple) else None
for u in (units_of(2) or []):
    d=S(lambda: idict(u),{}) or {}
    mo=S(lambda: u.model)
    vif=S(lambda: mo.is_visible_in_this_frame())
    tgt=S(lambda: u.position)
    hit=None
    if campos is not None and tgt is not None:
        dirv=S(lambda: tgt - campos)
        hit=S(lambda: mo.hit_by_ray(campos, dirv))
    # 自体命中测试：从头顶上方往下射，必中自己
    selfhit=None
    if tgt is not None:
        try:
            import math3d
            up=S(lambda: math3d.vector(tgt.x, tgt.y+5, tgt.z))
            dn=S(lambda: math3d.vector(0,-1,0))
            selfhit=S(lambda: mo.hit_by_ray(up,dn))
        except Exception as e: selfhit="ERR %s"%R(e,40)
    P("uid=%s model=%s vif=%r cam2tgt_hit=%s selfhit=%s" % (
        d.get("uid"), R(S(lambda: mo.get_res_name()),40), vif, R(hit,60), R(selfhit,60)))
