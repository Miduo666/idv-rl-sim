# -*- coding: utf-8 -*-
# 只记录不拦截：包住 request_place_furniture(发出) + request_place_furniture_cb(服务器回包)，
# 各自 log 后调原函数。用来抓"摆家具确认"的真实请求/回包结构，之后才好写本地化 hook。
# 零风险：不改上行、不伪造，只是把真实数据写到 furnlog.txt。
import time
gk = GK
a  = S(lambda: gk.g_avatar)
AC = type(a) if a is not None else None
LOG = "/sdcard/Android/data/com.netease.dwrg/files/furnlog.txt"

def _log(tag, obj):
    try:
        f = open(LOG, "a"); f.write("[%.3f] %s %r\n" % (time.time(), tag, obj)); f.close()
    except Exception:
        pass

if AC is None:
    P("g_avatar 未就绪，进庄园再跑")
elif getattr(AC, "_furnlog", 0):
    P("日志 hook 已在，直接去摆家具")
else:
    _o1 = AC.request_place_furniture
    def _w1(self, furniture_info, *ar, **kw):
        _log("REQ request_place_furniture furniture_info=", furniture_info)
        return _o1(self, furniture_info, *ar, **kw)
    AC.request_place_furniture = _w1

    _o2 = AC.request_place_furniture_cb
    def _w2(self, info, *ar, **kw):
        _log("CB  request_place_furniture_cb info=", info)
        return _o2(self, info, *ar, **kw)
    AC.request_place_furniture_cb = _w2

    # 顺带抓 batch 版(如果摆放走批量)
    AC._fl_batch = {}
    for nm in ("request_place_furniture_batch", "request_place_furniture_batch_cb"):
        o = getattr(AC, nm, None)
        if o is not None:
            AC._fl_batch[nm] = o
            def mk(o, nm):
                def w(self, x, *ar, **kw):
                    _log(nm + " =", x); return o(self, x, *ar, **kw)
                return w
            setattr(AC, nm, mk(o, nm))

    AC._furnlog = 1
    AC._fl_o1 = _o1; AC._fl_o2 = _o2
    _log("=== furnlog installed ===", AC.__name__)
    P("日志 hook 装好了。现在去庄园装修，摆一件你【本来就拥有】的家具并确认，然后告诉我。")
