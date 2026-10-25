# -*- coding: utf-8 -*-
# probe2(2026-10-18)：映射 AnimDataComponent 内部,找驱动(非注入)能走到 POSE/骨骼的 Python 可见引用。
# 注入态只能调方法/读属性(无 ctypes 裸读)。所以:若 adc 持有 skeleton/pose/anim/model 这类对象引用,
# 驱动就能从 unit->anim_data_component(属性) 再->那个对象 走原生偏移;否则只能回 model+0x818 那条若辰链。
import time

cam = S(lambda: GK.g_cam_ctrl.unit)
adc = S(lambda: cam.anim_data_component)
mdl = S(lambda: cam.model)
P("now=%.1f cam=%s adc=%s id=0x%X  model id=0x%X" % (
    time.time(), cname(cam), cname(adc),
    id(adc) if adc else 0, id(mdl) if mdl else 0))

# unit 上 anim_data_component 的属性序号(驱动要靠 find_key 走到它)—— 打印它在 unit.__dict__ 里
dd = S(lambda: idict(cam), {}) or {}
P("unit has 'anim_data_component' key: %s ; '_anim_data_component': %s" % (
    'anim_data_component' in dd, '_anim_data_component' in dd))

def dump_obj(tag, o):
    if o is None:
        P("%s = None" % tag); return
    P("\n%s = %s  id=0x%X" % (tag, cname(o), id(o)))
    for a in sorted(attr_names(o)):
        v = S(lambda a=a: idict(o).get(a) if isinstance(idict(o), dict) else getattr(o, a))
        if v is None:
            v = S(lambda a=a: getattr(o, a))
        cn = cname(v)
        extra = ""
        if isinstance(v, (int, float, bool, str)):
            extra = R(v, 40)
        elif v is not None:
            extra = "id=0x%X" % id(v)
        la = a.lower()
        star = " *" if any(w in la for w in ("skelet", "pose", "anim", "bone", "model", "native", "ptr", "handler", "prs", "matrix", "data")) else ""
        P("  .%-34s %-22s %s%s" % (R(a, 34), R(cn, 22), extra, star))

dump_obj("adc", adc)
# model 也看一眼顶层(driver 另一条入口 model+0x20 native)
P("\n-- model attrs(前若干) --")
if mdl is not None:
    for a in sorted(attr_names(mdl))[:40]:
        v = S(lambda a=a: getattr(mdl, a))
        if not callable(v):
            P("  .%-30s %-18s %s" % (R(a, 30), cname(v), R(v, 30) if isinstance(v, (int, float, bool, str)) else ("id=0x%X" % id(v) if v is not None else "None")))
P("\nEND")
