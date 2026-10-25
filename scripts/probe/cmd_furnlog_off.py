# -*- coding: utf-8 -*-
# 卸掉 cmd_furnlog.py 装的日志 hook，恢复原函数。
gk = GK
a  = S(lambda: gk.g_avatar)
AC = type(a) if a is not None else None
if AC is None:
    P("g_avatar 未就绪")
elif getattr(AC, "_furnlog", 0):
    AC.request_place_furniture = AC._fl_o1
    AC.request_place_furniture_cb = AC._fl_o2
    for nm, o in (getattr(AC, "_fl_batch", {}) or {}).items():
        setattr(AC, nm, o)
    for k in ("_furnlog", "_fl_o1", "_fl_o2", "_fl_batch"):
        try: delattr(AC, k)
        except Exception: pass
    P("日志 hook 已卸")
else:
    P("没装过")
