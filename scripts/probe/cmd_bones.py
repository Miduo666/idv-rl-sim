# -*- coding: utf-8 -*-
# probe2 命令(2026-10-18)：骨骼真值 dump(native-bones.md 待办步骤1)。注入态、可调方法。
# 要拿到：
#  ① anim_data_component(无下划线) 活不活 vs _anim_data_component(复盘分叉①)
#  ② get_bone_count + 每根 get_bone_name(i) + get_bone_position(name) 世界真值
#  ③ unit.position；④ id(anim_data_component)/id(model)(给 PC 侧 devread 裸读)
import time


def vec(v):
    if v is None:
        return None
    for c in (("x", "y", "z"), ("X", "Y", "Z")):
        t = S(lambda: tuple(round(float(getattr(v, a)), 2) for a in c))
        if t is not None:
            return t
    return R(v, 50)


def hid(o):
    return ("0x%X" % id(o)) if o is not None else "None"


def dump(u, full):
    P("\n== %s uid=%s is_self=%s ==" % (cname(u), R(S(lambda: u.uid), 20), R(S(lambda: u.is_self), 6)))
    P("  unit.position = %s" % R(vec(S(lambda: u.position)), 60))
    adc = S(lambda: u.anim_data_component)        # 无下划线(007 用的,期望活)
    adc_ = S(lambda: u._anim_data_component)      # 有下划线(我们以前读到的 None)
    mdl = S(lambda: u.model)
    P("  anim_data_component  = %s  id=%s" % (cname(adc), hid(adc)))
    P("  _anim_data_component = %s  id=%s" % (cname(adc_), hid(adc_)))
    P("  model                = %s  id=%s  file=%s" % (cname(mdl), hid(mdl), R(S(lambda: mdl.filename), 60)))
    # 骨骼数：优先 model.get_bone_count，再 adc.get_bone_count
    bc = S(lambda: mdl.get_bone_count())
    bc2 = S(lambda: adc.get_bone_count()) if adc is not None else None
    P("  model.get_bone_count=%s  adc.get_bone_count=%s" % (R(bc, 8), R(bc2, 8)))
    if not full:
        return
    n = bc if (isinstance(bc, int) and 0 < bc < 256) else 0
    P("  --- 逐根(idx | name | get_bone_position(name)世界 | get_bone_matrix(i)平移) ---")
    for i in range(n):
        nm = S(lambda i=i: mdl.get_bone_name(i))
        # 世界真值：先 adc.get_bone_position(name)，再 model.get_bone_pos(name)
        bp = None
        if adc is not None and nm is not None:
            bp = S(lambda nm=nm: adc.get_bone_position(nm))
        if bp is None and nm is not None:
            bp = S(lambda nm=nm: mdl.get_bone_pos(nm))
        # get_bone_matrix(i) 的平移(第4行)——看表示是世界还是父相对(分叉②)
        m = S(lambda i=i: mdl.get_bone_matrix(i))
        mt = None
        if m is not None:
            mt = S(lambda: tuple(round(float(x), 2) for x in (m[12], m[13], m[14]))) \
                or S(lambda: tuple(round(float(m[3][k]), 2) for k in range(3)))
        P("   [%2d] %-22s world=%s  mtx_t=%s" % (i, R(nm, 22), R(vec(bp) if not isinstance(bp, tuple) else bp, 40), R(mt, 40)))


cam = S(lambda: GK.g_cam_ctrl.unit)
P("now=%.1f  cam.unit=%s" % (time.time(), cname(cam)))
# 自身：全量 dump(建名字表 + 世界真值标尺)
if cam is not None:
    dump(cam, True)
# 另外两类玩家各列一个(只看 bone_count / id,确认别的单位同样走得通)
seen = set([id(cam)])
cnt = 0
for t in (2, 1):
    for u in (S(lambda t=t: units_of(t), []) or []):
        if id(u) in seen or cnt >= 3:
            continue
        seen.add(id(u))
        cnt += 1
        dump(u, False)
P("\nEND")
