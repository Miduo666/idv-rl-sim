# -*- coding: utf-8 -*-
# probe7: 定位 hall_servant(管家)系统的 "当前使用" 字段 + 设置API。纯读。
#   花布侍女 = housekeeper id 5 (未拥有, pp['105']只有2). 找它"使用中"状态存哪 + 怎么被设上的。
import time
gk = GK
a  = S(lambda: gk.g_avatar)
AC = type(a) if a is not None else None
KW = ["servant", "housekeeper", "keeper", "guanjia"]

def hit(s):
    try:
        return any(x in str(s).lower() for x in KW)
    except Exception:
        return False

if a is None:
    P("g_avatar 未就绪")
else:
    # 1. avatar 字段名命中 (这次含 servant)
    P("=== 1. avatar 字段: servant/housekeeper/keeper/guanjia ===")
    d = S(lambda: vars(a)) or {}
    for fk in sorted(d.keys()):
        if hit(fk):
            P("  a.%s = %s" % (fk, R(d.get(fk), 300)))

    # 2. article_shared_setting 全量 (当前管家可能在这)
    P("=== 2. a.article_shared_setting 全量 ===")
    P(R(S(lambda: a.article_shared_setting), 2000))

    # 3. 任意字段值 == 5 且像管家 id 的
    P("=== 3. 值==5 的 servant/keeper/housekeeper 字段 ===")
    f3 = 0
    for fk in sorted(d.keys()):
        try:
            if d.get(fk) == 5 and hit(fk):
                P("  a.%s = 5" % fk); f3 += 1
        except Exception:
            pass
    if f3 == 0:
        P("  (无; 当前管家可能在 article_shared_setting 或 custom_hall_info 里)")

    # 4. custom_hall_info 各厅的非 furniture 键
    P("=== 4. custom_hall_info 各厅结构键 ===")
    chi = S(lambda: a.custom_hall_info)
    if chi and hasattr(chi, "items"):
        for hkey, hv in list(chi.items()):
            ks = list(hv.keys()) if hasattr(hv, "keys") else []
            P("  hall %r keys: %s" % (hkey, R(ks, 300)))
            for kk in ks:
                if hit(kk):
                    P("    %r = %s" % (kk, R(hv.get(kk), 160)))

    # 5. Avatar 方法: servant/housekeeper/keeper (候选 setter)
    P("=== 5. Avatar 方法名命中 (候选设置/上行API) ===")
    if AC:
        for nm in sorted(dir(AC)):
            if hit(nm):
                try:
                    o = getattr(AC, nm, None)
                    P("  %s%s" % (nm, "()" if callable(o) else " = %s" % R(o, 80)))
                except Exception:
                    pass
    P(">>> 目标: 当前管家存哪个字段(=持久的那个) + 设置它的API叫啥 + 走不走上行")
