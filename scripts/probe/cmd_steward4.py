# -*- coding: utf-8 -*-
# probe4 管家(steward)系统发现: 纯读, 零上行。
# 目标: 定位"花布侍女"(管家)的 配表id / article_type / 拥有存储 / "当前使用"字段,
#       解释"未解锁 + 使用中"同屏, 以及它为何能脱离拥有真持久(退游戏重进仍在)。
import time
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)
SUBS = ["花布侍女", "侍女", "花布"]
KW   = ["steward", "butler", "housekeep", "manager", "servant", "maid", "管家", "侍女", "花布"]

def hit_kw(s):
    try:
        s = str(s).lower()
    except Exception:
        return False
    return any(k in s for k in KW)

if a is None:
    P("g_avatar 未就绪，进庄园再跑")
else:
    # ---- 1. article_setting 全量 (当前使用的管家 id 多半在这) ----
    P("=== 1. a.article_setting 全量 ===")
    P(R(S(lambda: a.article_setting), 2000))

    # ---- 2. props_package 每个库的规模 + 样本 (认出哪个是管家库) ----
    P("=== 2. a.props_package 各库 (key=article_type) ===")
    pp = S(lambda: a.props_package)
    if pp and hasattr(pp, "items"):
        for k, v in list(pp.items()):
            n = len(v) if hasattr(v, "__len__") else "?"
            sk = None; sv = None
            try:
                sk = list(v.keys())[0]; sv = v[sk]
            except Exception:
                pass
            P("  pp[%r]: %s 条; 样本 %r = %s" % (k, n, sk, R(sv, 160)))

    # ---- 3. article_unlock 全量 ----
    P("=== 3. a.article_unlock 全量 ===")
    P(R(S(lambda: a.article_unlock), 1500))

    # ---- 4. avatar.__dict__ 里 名字/值 命中 管家关键字的字段 ----
    P("=== 4. avatar 字段命中 管家关键字 ===")
    d = S(lambda: vars(a)) or {}
    cnt = 0
    for fk in sorted(d.keys()):
        try:
            fv = d[fk]
            rv = R(fv, 400)
            if hit_kw(fk) or any(s in rv for s in SUBS):
                P("  a.%s = %s" % (fk, rv))
                cnt += 1
                if cnt >= 30:
                    break
        except Exception:
            pass
    if cnt == 0:
        P("  (无字段名/值直接命中; 管家可能以纯数字 id 存, 靠第1/2节的样本反推)")

    # ---- 5. dm 配表: 按名字找"花布侍女", 按表名找 steward 表 ----
    P("=== 5. dm 配表命中 ===")
    name_hits = []; table_hits = []
    for tn in dir(dm):
        if tn.startswith("__"):
            continue
        t = S(lambda tn=tn: getattr(dm, tn))
        if t is None:
            continue
        if hit_kw(tn):
            table_hits.append(tn)
        if not (hasattr(t, "keys") and hasattr(t, "__getitem__")):
            continue
        try:
            keys = list(t.keys())
        except Exception:
            continue
        scanned = 0
        for k in keys:
            if scanned >= 6000:
                break
            scanned += 1
            v = S(lambda t=t, k=k: t[k])
            if v is None:
                continue
            try:
                rv = R(v, 240)
            except Exception:
                continue
            if any(s in rv for s in SUBS):
                name_hits.append((tn, k, rv))
                if len(name_hits) >= 25:
                    break
        if len(name_hits) >= 25:
            break
    P("  表名含管家关键字:", R(table_hits, 400))
    P("  值里含'花布/侍女' (%d):" % len(name_hits))
    for tn, k, rv in name_hits[:25]:
        P("    dm.%s[%r] = %s" % (tn, k, rv))

    P(">>> 拿到: 花布侍女的 id + 它在哪张表 + 当前使用字段 + 它在不在拥有库里 → 下一步针对性抓它的持久链。")
