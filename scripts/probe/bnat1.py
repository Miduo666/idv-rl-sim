u=None
for x in (units_of(2) or []):
    if S(lambda x=x: x.uid)==1000002: u=x; break   # 囚徒(相对稳定)
u=u or (units_of(2) or [None])[0]
mo=S(lambda: u.model)
P("uid=%s model_id=0x%x world_pos=%s bone_count=%r" % (
   S(lambda: u.uid), S(lambda: id(mo)) or 0, R(S(lambda: mo.world_position),40), S(lambda: mo.get_bone_count())))
# 可能的子对象指针
for nm in ("get_animator","get_anim_ctrl","get_animation_component","get_constraint_component"):
    o=S(lambda nm=nm: getattr(mo,nm)())
    if o is not None: P("  %s -> type=%s id=0x%x" % (nm, cname(o), S(lambda o=o: id(o)) or 0))
# get_bone_by_name 返回什么
hb=S(lambda: mo.get_bone_by_name("biped head"))
P("get_bone_by_name('biped head') -> type=%s val=%s id=0x%x" % (cname(hb), R(hb,80), S(lambda: id(hb)) or 0))
# 真值：bone 0 / 17 的矩阵与prs（全精度）
for i in (0,17):
    P("bone[%d] name=%r matrix=%r" % (i, S(lambda i=i: mo.get_bone_name(i)), S(lambda i=i: mo.get_bone_matrix(i))))
    P("bone[%d] prs=%r" % (i, S(lambda i=i: mo.get_bone_prs(i))))
