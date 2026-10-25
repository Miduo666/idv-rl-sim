u=(units_of(2) or [None])[0]
mo=S(lambda: u.model)
P("unit.position=%s" % R(S(lambda: u.position),50))
# 找 head 索引
hi=None; n=S(lambda: mo.get_bone_count()) or 0
for i in range(n):
    if S(lambda i=i: mo.get_bone_name(i))=="biped head": hi=i; break
P("head idx=%r" % hi)
for tag,fn in (("accum", lambda k: mo.get_accum_matrix(k)),
               ("bonemtx", lambda k: mo.get_bone_matrix(k)),
               ("prs", lambda k: mo.get_bone_prs(k))):
    for k in (hi, "biped head"):
        if k is None: continue
        v=S(lambda k=k,fn=fn: fn(k))
        if v is not None: P("%s(%r)=%s" % (tag,k,R(v,200)))
