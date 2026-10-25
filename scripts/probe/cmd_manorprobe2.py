# -*- coding: utf-8 -*-
# probe2 第二轮：精确定位家具主表 + Avatar 的 hall/furniture 解锁方法 + 大厅全键名。
# 2026-10-18。第一轮已知：大厅总表=custom_hall(28)，拥有=article_unlock['hall_list'],当前=article_setting['hall_id'];
#   家具 furniture_id≈332~350+(见 custom_hall_info / new_furniture_info)，但主表没被 hint 命中。这一轮找它。
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)
P("avatar=%s dm=%s" % (a is not None, dm is not None))
if a is not None and dm is not None:
    # 1. custom_hall 全部键 + 名字(认迷雾山庄/林泉池馆/魅影古堡/沉默宫殿)
    ch = S(lambda: getattr(dm, 'custom_hall'))
    if isinstance(ch, dict):
        P("\n== custom_hall keys(%d) == %s" % (len(ch), sorted(ch.keys())))
        for k in sorted(ch.keys()):
            row = ch[k]
            g = row.get('g_name') if hasattr(row, 'get') else None
            ic = row.get('big_icon') if hasattr(row, 'get') else None
            P("  hall %-3s g_name=%-40r icon=%r" % (k, g, ic))

    # 2. 扫所有 DM dict 表，找含整数键 334 的 = 家具主表
    P("\n== 含 key=334 的 DM 表(家具主表) ==")
    for n in dir(dm):
        if n.startswith('__'):
            continue
        v = S(lambda n=n: getattr(dm, n))
        if isinstance(v, dict) and 334 in v:
            row = v[334]
            flds = sorted(row.keys()) if hasattr(row, 'keys') else cname(row)
            P("  %-32s size=%-5d fields=%s" % (n, len(v), R(flds, 220)))
            P("       row[334]=%s" % R(row, 300))

    # 3. 更宽：含 key 330/334/340/350 的表(家具 id 范围)
    P("\n== 含 key∈{330,334,340,350,360} 的 DM 表 ==")
    for n in dir(dm):
        if n.startswith('__'):
            continue
        v = S(lambda n=n: getattr(dm, n))
        if isinstance(v, dict):
            hit = [kk for kk in (330, 334, 340, 350, 360) if kk in v]
            if hit:
                P("  %-32s size=%-5d hit=%s" % (n, len(v), hit))

    # 4. Avatar 类方法：hall/furniture/component 相关 + reply_*/unlock_*
    AC = type(a)
    P("\n== Avatar 方法(hall/furniture/component) ==")
    for nm in sorted(dir(AC)):
        low = nm.lower()
        if any(h in low for h in ('hall', 'furniture', 'component')) and callable(S(lambda nm=nm: getattr(AC, nm, None))):
            P("  " + nm)
    P("\n== Avatar reply_* / *unlock* 方法 ==")
    for nm in sorted(dir(AC)):
        if (nm.startswith('reply_') or 'unlock' in nm.lower()) and callable(S(lambda nm=nm: getattr(AC, nm, None))):
            P("  " + nm)

    # 5. 家具拥有容器 + 结构
    au = S(lambda: a.article_unlock)
    P("\n== hall_component_list == %s" % (R(au.get('hall_component_list'), 300) if hasattr(au, 'get') else '?'))
    P("== new_furniture_info == %s" % R(S(lambda: a.new_furniture_info), 500))
    chi = S(lambda: a.custom_hall_info)
    if isinstance(chi, dict):
        for hk in list(chi.keys())[:1]:
            fi = S(lambda hk=hk: chi[hk].get('furniture_info'))
            P("== custom_hall_info[%s].furniture_info keys == %s" % (hk, R(S(lambda: list(fi.keys())), 200)))
            P("     %s" % R(fi, 400))
