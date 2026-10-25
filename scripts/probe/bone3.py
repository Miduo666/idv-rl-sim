u=(units_of(2) or [None])[0]
mo=S(lambda: u.model)
n=S(lambda: mo.get_bone_count())
P("bone_count=%r" % n)
names=[]
if isinstance(n,int) and n>0:
    for i in range(min(n,60)):
        nm=S(lambda i=i: mo.get_bone_name(i))
        names.append(nm)
    P("bone_names[:60]=%s" % R(names,900))
# 取几个关键骨骼的矩阵/prs
for key in ("Bip001", "Bip001 Head", "head", "Head", "Bip001 Spine", "Bip001 Pelvis", 0, 1):
    mtx=S(lambda key=key: mo.get_bone_matrix(key))
    prs=S(lambda key=key: mo.get_bone_prs(key))
    ti =S(lambda key=key: mo.get_bone_trans_info(key))
    if mtx is not None or prs is not None or ti is not None:
        P("key=%r | matrix=%s | prs=%s | trans_info=%s" % (key, R(mtx,120), R(prs,120), R(ti,120)))
bb=S(lambda: mo.bones_bounding_box)
P("bones_bounding_box=%s (callable=%s)" % (R(bb,80), callable(bb) if bb is not None else "NA"))
