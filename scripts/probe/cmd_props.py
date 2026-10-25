# -*- coding: utf-8 -*-
# 看 props_package 结构 —— get_avaliable_furniture_ids 从这里按 FURNITURE(14) 过滤。
# 目标：搞清家具在背包里怎么 keyed，好正确写入授予拥有。
gk = GK
a  = S(lambda: gk.g_avatar)
pp = S(lambda: a.props_package)
P("props_package:", cname(pp), " len=", S(lambda: len(pp), "-"))
from common_cs import ComuKeys
FUR = ComuKeys.ARTICLE_TYPE.FURNITURE
P("FURNITURE type =", FUR)

# 取键看结构(可能是 '14_332' 这种 type_id，或嵌套 {type:{id:...}})
ks = S(lambda: list(pp.keys()), [])
P("键数:", len(ks), " 前30键:", R(ks[:30], 300))
P("键类型分布:", R(S(lambda: sorted(set(type(k).__name__ for k in ks))), 80))

# 已拥有家具(25)在背包里的真实条目
owned = S(lambda: a.get_avaliable_furniture_ids()) or []
P("\n已拥有家具 id:", R(sorted(owned), 200))
# 猜几种 key 形式找它们
import_ok = True
for fid in list(owned)[:6]:
    found = []
    for cand in (fid, str(fid), "%d_%d" % (FUR, fid), "%d_%d" % (fid, FUR), (FUR, fid)):
        try:
            if cand in pp:
                found.append((cand, R(pp[cand], 100)))
        except Exception:
            pass
    P("  furniture %s 在背包的键: %s" % (fid, found if found else "<未按这些形式命中>"))

# 直接把背包里所有 '含 FURNITURE' 的键打出来(前40)
hits = []
for k in ks:
    sk = str(k)
    if sk.startswith("%d_" % FUR) or sk.endswith("_%d" % FUR):
        hits.append((k, R(pp[k], 80)))
P("\n背包里形如 FURNITURE 的键(前40):", R(hits[:40], 1200))
