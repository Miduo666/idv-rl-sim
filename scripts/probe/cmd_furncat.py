# -*- coding: utf-8 -*-
# 找家具全集：按内容扫 DM —— 哪张表的行里带 'image/furniture/' 图标路径就是家具目录。
# 另外把当前已拥有、以及 get_data_furniture_id 的含义一并打清楚。
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)
if a is None or dm is None:
    P("g_avatar/DM 未就绪")
else:
    owned = sorted(S(lambda: a.get_avaliable_furniture_ids()) or [])
    P("已拥有家具(%d): %s" % (len(owned), owned))

    # 内容扫：统计每张表里 "行内有 image/furniture/ 路径" 的行数
    hits = {}
    samples = {}
    for n in dir(dm):
        if n.startswith("__"):
            continue
        v = S(lambda n=n: getattr(dm, n))
        if not isinstance(v, dict) or not v:
            continue
        cnt = 0
        for k, row in list(v.items())[:3000]:
            vals = row.values() if hasattr(row, "values") else ([row] if isinstance(row, str) else [])
            for val in vals:
                if isinstance(val, str) and "image/furniture/" in val:
                    cnt += 1
                    if n not in samples:
                        samples[n] = (k, row)
                    break
        if cnt:
            hits[n] = cnt
    P("\n== 行内含 image/furniture/ 的表(行数) ==")
    for n in sorted(hits, key=lambda x: -hits[x]):
        P("  %-34s %d行/%d" % (n, hits[n], len(S(lambda n=n: getattr(dm, n)))))
        sk, sr = samples[n]
        P("       样本 key=%r %s" % (sk, R(sr, 240)))

    # 对最大的候选表，dump 全部 int 键 = 家具全集
    if hits:
        top = max(hits, key=lambda x: hits[x])
        tv = S(lambda: getattr(dm, top))
        ks = sorted([k for k in tv.keys() if isinstance(k, int)])
        P("\n== 最可能的家具目录 '%s' 全部 int 键(%d) ==" % (top, len(ks)))
        P("  %s" % R(ks, 1500))
