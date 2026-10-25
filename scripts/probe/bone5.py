import traceback
u=(units_of(2) or [None])[0]
mo=S(lambda: u.model)
P("unit.position=%s" % R(S(lambda: u.position),50))
# 直接调用并捕获异常，探明 get_accum_matrix 的签名/返回
for expr in ("mo.get_accum_matrix(17)","mo.get_accum_matrix('biped head')",
             "mo.get_accum_matrix(17,1)","mo.get_bone_trans_info(17)",
             "mo.get_world_matrix()","mo.get_transform()","mo.get_position()",
             "mo.world_position","mo.get_bone_prs(17)","mo.get_bone_matrix(0)"):
    try:
        r=eval(expr)
        P("OK %s = %s" % (expr, R(r,160)))
    except Exception as e:
        P("ERR %s : %s" % (expr, R(e,80)))
