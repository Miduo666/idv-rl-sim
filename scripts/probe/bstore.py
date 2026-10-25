u=None
for x in (units_of(2) or []):
    if S(lambda x=x: x.uid)==1000002: u=x; break
u=u or (units_of(2) or [None])[0]
mo=S(lambda: u.model)
P("uid=%s model type=%s id=0x%x" % (S(lambda: u.uid), cname(mo), S(lambda: id(mo)) or 0))
# model 的存储属性(__dict__)——外部裸读只能读这些
md=S(lambda: idict(mo))
P("model.__dict__ type=%s keys=%s" % (type(md).__name__, R(S(lambda: sorted(md.keys()) if hasattr(md,'keys') else md),400)))
BK=("bone","skelet","joint","pose","transform","matrix","anim","node","socket")
if hasattr(md,'keys'):
    P("model.__dict__ 里骨骼相关: %s" % R([k for k in md.keys() if isinstance(k,str) and any(b in k.lower() for b in BK)],300))
# unit __dict__ 里 anim/bone 相关的存储字段 + 它们的值(看是不是 None)
ud=S(lambda: idict(u),{}) or {}
anim=[(k, R(ud[k],40)) for k in sorted(ud.keys()) if isinstance(k,str) and any(b in k.lower() for b in BK)]
P("unit.__dict__ anim/bone 字段: %s" % R(anim,600))
# get_bone_by_name 返回对象是不是带存储字段
hb=S(lambda: mo.get_bone_by_name("biped head"))
P("bone obj type=%s id=0x%x dict=%s" % (cname(hb), S(lambda: id(hb)) or 0, R(S(lambda: idict(hb)),200)))
if hb is not None:
    P("bone obj dir: %s" % R([a for a in (S(lambda: dir(hb),[]) or []) if not a.startswith('__')],400))
