# world.model 原生对象的方法：找骨骼/关节/socket 入口
u=(units_of(2) or [None])[0]
mo=S(lambda: u.model)
P("model type=%s id=0x%x" % (cname(mo), S(lambda: id(mo)) or 0))
ns=S(lambda: sorted(set(dir(mo))),[]) or []
KW=("bone","joint","skelet","socket","node","pose","world","pos","transform","matrix","attach","get_","visible","mesh")
cand=[a for a in ns if isinstance(a,str) and any(k in a.lower() for k in KW)]
P("model methods/attrs (%d total), 候选: %s" % (len(ns), R(cand,900)))
# 尝试常见取骨骼方法(不带参先试)
for nm in ("get_bone_world_position","get_bone_position","get_socket_position","get_joint_position",
           "get_bone_matrix","get_world_transform","get_position","world_position","get_bone_count","get_bone_names"):
    m=S(lambda nm=nm: getattr(mo,nm,None))
    if m is not None: P("  HAS %s callable=%s" % (nm, callable(m)))
