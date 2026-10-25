# -*- coding: utf-8 -*-
# probe2 命令：勘探「归宿大厅(庄园主题)」+「家具」的拥有/解锁字段。
# 2026-10-18 建。字段未知，目标是把以下三件事看清楚，之后才好写 beautify 的解锁逻辑：
#   (1) g_avatar 上哪个容器存"已拥有的大厅/家具"(类比 article_unlock['decoration_list'])
#   (2) GK.DM 里哪张配表是全部大厅、哪张是全部家具(大厅只有迷雾山庄/林泉池馆/魅影古堡/沉默宫殿 ~4+ 个，是小表好认)
#   (3) ARTICLE_TYPE 里有没有 FURNITURE/HOUSE/MANOR 这类枚举(有的话解锁走和换皮同一套机制)
# 在大厅/庄园界面跑(g_avatar 要就绪)。输出较长，cat idv_cmd_out.txt 看。
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)
P("avatar_ready=%s dm_ready=%s" % (a is not None, dm is not None))
if a is None or dm is None:
    P("!! g_avatar / DM 未就绪 —— 进大厅/庄园界面再跑")
else:
    HINT = ("manor", "homeland", "home", "house", "furniture", "hall", "theme",
            "garden", "decorate", "yard", "room", "scene", "villa", "castle",
            "palace", "building", "estate", "guixu", "zhuangyuan", "jiaju",
            "datang", "jiayuan", "backyard", "furnish")

    # ---------- 1. g_avatar 的拥有/设置容器 ----------
    au = S(lambda: a.article_unlock)
    P("\n== article_unlock ==  cls=%s" % cname(au))
    if hasattr(au, "keys"):
        for k in sorted(au.keys(), key=lambda x: str(x)):
            v = au.get(k)
            P("  [%s] %-10s len=%-5s %s" % (k, cname(v), S(lambda v=v: len(v), "-"), R(v, 140)))

    aset = S(lambda: a.article_setting)
    P("\n== article_setting keys ==  cls=%s" % cname(aset))
    if hasattr(aset, "keys"):
        for k in sorted(aset.keys(), key=lambda x: str(x)):
            v = aset.get(k)
            P("  [%s] %-10s %s" % (k, cname(v), R(v, 110)))

    # ---------- 2. g_avatar 实例属性里带 hint 的(可能是大厅/家具的专用容器) ----------
    an = attr_names(a)
    P("\n== g_avatar 全部实例属性数=%d ==" % len(an))
    hit = [n for n in an if any(h in n.lower() for h in HINT)]
    P("-- 命中 hint 的属性 --")
    for n in hit:
        v = S(lambda n=n: idict(a).get(n))
        P("  %-34s %-10s len=%-5s %s" % (n, cname(v), S(lambda v=v: len(v), "-"), R(v, 130)))

    # ---------- 3. ARTICLE_TYPE 枚举全量(找 FURNITURE/HOUSE/MANOR) ----------
    P("\n== ComuKeys.ARTICLE_TYPE 全量 ==")
    try:
        from common_cs import ComuKeys
        AT = ComuKeys.ARTICLE_TYPE
        for nm in sorted(dir(AT)):
            if nm.startswith("__"):
                continue
            P("  ARTICLE_TYPE.%-22s = %r" % (nm, S(lambda nm=nm: getattr(AT, nm))))
    except Exception as e:
        P("  取 ARTICLE_TYPE 失败: %r" % e)

    # ---------- 4. GK.DM 全部 dict 配表(名字,大小)，小表和 hint 表重点标出 ----------
    tbls = []
    for n in dir(dm):
        if n.startswith("__"):
            continue
        v = S(lambda n=n: getattr(dm, n))
        if isinstance(v, dict) and len(v) > 0:
            tbls.append((n, len(v)))
    tbls.sort()
    P("\n== GK.DM dict 配表 共%d 张 ==" % len(tbls))
    for n, sz in tbls:
        mark = ""
        if any(h in n.lower() for h in HINT):
            mark += " <HINT>"
        if sz <= 40:
            mark += " <SMALL>"   # 大厅只有 4+ 个，必在小表里
        P("  %-40s %6d%s" % (n, sz, mark))

    # ---------- 5. dump 候选表样本(hint 命中 或 小表)，看 id 范围和字段名 ----------
    cand = [n for n, sz in tbls if any(h in n.lower() for h in HINT) or sz <= 40]
    P("\n== 候选表样本(每表前 4 行) ==  候选 %d 张" % len(cand))
    for n in cand:
        v = S(lambda n=n: getattr(dm, n))
        if not isinstance(v, dict) or not v:
            continue
        ks = list(v.keys())[:4]
        P("---- %s (size=%d) keys样本=%s ----" % (n, len(v), R([type(x).__name__ for x in ks], 60)))
        for kk in ks:
            row = v[kk]
            # 配表行通常是 dict，打出字段名有助于认"这是不是大厅/家具"
            if isinstance(row, dict):
                P("   key=%r fields=%s" % (kk, R(sorted(row.keys()), 200)))
                P("        %s" % R(row, 240))
            else:
                P("   key=%r %s=%s" % (kk, cname(row), R(row, 200)))
