# -*- coding: utf-8 -*-
# dump props_package['14'](家具)的条目格式：key 是不是 furniture_id、value 长啥样。
gk = GK
a  = S(lambda: gk.g_avatar)
pp = S(lambda: a.props_package)
fur = S(lambda: pp.get("14"))
P("pp['14']:", cname(fur), " len=", S(lambda: len(fur), -1))
ks = S(lambda: list(fur.keys()), [])
P("key 类型:", R(S(lambda: sorted(set(type(k).__name__ for k in ks))), 60))
P("全部 key:", R(sorted(ks, key=str), 500))
P("样本条目:")
for k in ks[:8]:
    P("  %r = %r  (%s)" % (k, S(lambda k=k: fur[k]), cname(S(lambda k=k: fur[k]))))
# 对照：get_avaliable_furniture_ids 和 pp['14'] 的键是否一致
owned = S(lambda: sorted(a.get_avaliable_furniture_ids()), [])
P("get_avaliable_furniture_ids:", R(owned, 300))
