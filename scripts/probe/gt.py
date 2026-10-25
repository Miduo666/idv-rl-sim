u=None
for x in (units_of(2) or []):
    if S(lambda x=x: x.uid)==1000002: u=x; break
u=u or (units_of(2) or [None])[0]
mo=S(lambda: u.model)
P("MODEL_ID 0x%x" % (S(lambda: id(mo)) or 0))
P("WORLDPOS %r" % (S(lambda: mo.world_position),))
P("UNITPOS %r" % (S(lambda: u.position),))
P("BONECOUNT %r" % (S(lambda: mo.get_bone_count()),))
for i in (0,1,17):
    P("BM%d %r" % (i, S(lambda i=i: mo.get_bone_matrix(i))))
    P("PRS%d %r" % (i, S(lambda i=i: mo.get_bone_prs(i))))
