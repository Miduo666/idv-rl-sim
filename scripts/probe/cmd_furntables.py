# -*- coding: utf-8 -*-
# 定位装修UI的家具目录：dump 所有名字带 furniture 的 DM 表(大小/前若干键/样本)，并查 dm.furniture。
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)
if a is None or dm is None:
    P("未就绪")
else:
    names = [n for n in dir(dm) if "furniture" in n.lower() and not n.startswith("__")]
    P("DM 里带 furniture 的属性:", names)
    for n in names:
        v = S(lambda n=n: getattr(dm, n))
        if isinstance(v, dict):
            ks = sorted([k for k in v.keys() if isinstance(k, int)])
            P("\n-- %s size=%d --" % (n, len(v)))
            P("   keys前40: %s" % R(ks[:40], 300))
            k0 = next(iter(v.keys()))
            P("   样本[%r]=%s" % (k0, R(v[k0], 260)))
        else:
            P("\n-- %s = %s (%s)" % (n, R(v, 120), cname(v)))
    # 直接查 dm.furniture
    fv = S(lambda: getattr(dm, "furniture", None))
    P("\ndm.furniture =", cname(fv), "size=", S(lambda: len(fv), "-"))
    # get_avaliable_furniture_ids 现值
    P("owned now:", R(S(lambda: sorted(a.get_avaliable_furniture_ids())), 300))
