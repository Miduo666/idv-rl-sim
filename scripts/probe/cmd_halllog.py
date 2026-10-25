# -*- coding: utf-8 -*-
# 只记录不拦截：包住"切换/进入大厅"相关方法 + call_server_method(过滤 hall/custom/scene)，
# 各自 log 后调原函数。用来抓真实的"切换大厅"流程(请求+回包+本地应用序列)。零风险。
import time
gk = GK
a  = S(lambda: gk.g_avatar)
AC = type(a) if a is not None else None
LOG = "/sdcard/Android/data/com.netease.dwrg/files/halllog.txt"
_seq = [0]

def _log(tag, obj):
    try:
        _seq[0] += 1
        f = open(LOG, "a")
        f.write("[%03d %.3f] %s %r\n" % (_seq[0], time.time(), tag, obj))
        f.close()
    except Exception:
        pass

HALL_METHODS = ("reply_update_custom_hall", "alter_custom_hall_cb", "enter_custom_hall_cb",
                "change_to_common_hall", "update_custom_hall_info", "set_hall_info_no_save",
                "recover_self_hall_info", "notify_update_hall_info", "real_notify_update_hall_info",
                "update_saved_custom_hall_info", "enter_custom_hall", "reset_default_hall")

if AC is None:
    P("g_avatar 未就绪，进大厅再跑")
elif getattr(AC, "_halllog", 0):
    P("切换日志 hook 已在，直接去切大厅")
else:
    AC._hl_orig = {}
    for nm in HALL_METHODS:
        o = getattr(AC, nm, None)
        if o is None or not callable(o):
            continue
        AC._hl_orig[nm] = o
        def mk(o, nm):
            def w(self, *ar, **kw):
                _log(nm, {"args": [R(x, 300) for x in ar], "kw": {k: R(v, 200) for k, v in kw.items()}})
                return o(self, *ar, **kw)
            return w
        setattr(AC, nm, mk(o, nm))

    # call_server_method：定位定义类，log 带 hall/custom/scene 的调用
    base = None
    for klass in AC.__mro__:
        if "call_server_method" in klass.__dict__:
            base = klass; break
    if base is not None:
        _csm = base.call_server_method
        def _wcsm(self, method, *ar, **kw):
            try:
                ms = str(method)
            except Exception:
                ms = "?"
            if any(h in ms.lower() for h in ("hall", "custom", "scene", "servant")):
                _log("CSM:" + ms, {"args": [R(x, 300) for x in ar], "kw": {k: R(v, 200) for k, v in kw.items()}})
            return _csm(self, method, *ar, **kw)
        base.call_server_method = _wcsm
        AC._hl_csm_base = base; AC._hl_csm_orig = _csm

    AC._halllog = 1
    _log("=== halllog installed ===", AC.__name__)
    P("切换日志 hook 装好。现在:先切到【普通大厅/common】，再切回你自己的厅(15)，来回切 1~2 次。")
    P("包住的方法:", list(AC._hl_orig.keys()))
