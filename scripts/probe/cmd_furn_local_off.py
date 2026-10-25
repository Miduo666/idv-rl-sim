# -*- coding: utf-8 -*-
# 关闭本地装修模式，恢复所有被 hook/阻断的上行写。
gk = GK
a  = S(lambda: gk.g_avatar)
AC = type(a) if a is not None else None
if AC is None:
    P("g_avatar 未就绪")
elif getattr(AC, "_furnlocal", 0):
    AC.request_place_furniture = AC._fl_place_o
    for nm, o in (getattr(AC, "_furn_blocked", {}) or {}).items():
        setattr(AC, nm, o)
    for k in ("_furnlocal", "_fl_place_o", "_furn_blocked"):
        try: delattr(AC, k)
        except Exception: pass
    P("本地装修模式已关，上行写已恢复")
else:
    P("没开过")
