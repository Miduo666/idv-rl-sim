# -*- coding: utf-8 -*-
# 卸掉 cmd_halllog.py 的切换日志 hook。
gk = GK
a  = S(lambda: gk.g_avatar)
AC = type(a) if a is not None else None
if AC is None:
    P("g_avatar 未就绪")
elif getattr(AC, "_halllog", 0):
    for nm, o in (getattr(AC, "_hl_orig", {}) or {}).items():
        setattr(AC, nm, o)
    b = getattr(AC, "_hl_csm_base", None)
    if b is not None:
        b.call_server_method = AC._hl_csm_orig
    for k in ("_halllog", "_hl_orig", "_hl_csm_base", "_hl_csm_orig"):
        try: delattr(AC, k)
        except Exception: pass
    P("切换日志 hook 已卸")
else:
    P("没装过")
