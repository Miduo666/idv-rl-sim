# -*- coding: utf-8 -*-
# 本地授予全部家具：把 dm.furniture(889) 全部 id 写进 props_package['14'](家具拥有背包)，
# 用现有家具条目做模板。授完报告 get_avaliable_furniture_ids 前后数量验证是否真授上。
# 依据：get_avaliable_furniture_ids 读 props_package 按 FURNITURE(14) 过滤；reply_obtain_furniture 只打红点不授予。
import copy
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)
pp = S(lambda: a.props_package)
fur = S(lambda: pp.get("14"))
if fur is None:
    P("pp['14'] 不存在。先进一次庄园装修/确保拥有过家具再跑。")
else:
    ks = list(fur.keys())
    key_str = isinstance(ks[0], str) if ks else True
    tkey = ks[0] if ks else None
    tval = fur[tkey] if tkey is not None else 1
    P("模板: pp['14'] 现有 %d 条, key类型=%s" % (len(ks), sorted(set(type(k).__name__ for k in ks))))
    P("模板条目: %r = %r (%s)" % (tkey, R(tval, 160), cname(tval)))

    fids = [k for k in list(dm.furniture.keys()) if isinstance(k, int)]
    P("furniture 全集:", len(fids))
    before = len(S(lambda: a.get_avaliable_furniture_ids()) or [])
    added = 0
    for fid in fids:
        k = str(fid) if key_str else fid
        if k in fur:
            continue
        if isinstance(tval, bool):
            nv = True
        elif isinstance(tval, (int, float)):
            nv = tval if tval else 1
        elif isinstance(tval, dict):
            nv = copy.deepcopy(tval)
            for idf in ("id", "article_id", "props_id"):
                if idf in nv:
                    nv[idf] = fid
        else:
            nv = 1
        fur[k] = nv
        added += 1
    after = sorted(S(lambda: a.get_avaliable_furniture_ids()) or [])
    P("写入 pp['14'] 新增:", added, " 现 len:", len(fur))
    P("get_avaliable_furniture_ids: %d -> %d" % (before, len(after)))
    P("owned 示例:", R(after[:60], 400))
    P(">>> 若 after 接近 889 = 授予成功；装修界面应能看到全部家具，摆放+保存即持久化。")
