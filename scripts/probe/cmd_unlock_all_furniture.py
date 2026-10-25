# -*- coding: utf-8 -*-
# 本地解锁全部家具：枚举 dm.furniture(OptDict, 889) 的全部 id，reply_obtain_furniture(fid,1) 本地授予。
# reply_obtain_furniture 已坐实 LOCAL(无 call_server_method)。授完对比 get_avaliable_furniture_ids 验证。
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)
if a is None or dm is None:
    P("未就绪")
else:
    fur = S(lambda: dm.furniture)
    # 取 OptDict 全部键
    ids = None
    for getter in (lambda: list(fur.keys()), lambda: [k for k in fur], lambda: list(fur)):
        ids = S(getter)
        if ids:
            break
    ids = [k for k in (ids or []) if isinstance(k, int)]
    P("家具目录 dm.furniture 键数:", len(ids), " 示例:", R(sorted(ids)[:20], 150))

    before = set(S(lambda: a.get_avaliable_furniture_ids()) or [])
    ok = 0; errs = {}
    for fid in ids:
        try:
            a.reply_obtain_furniture(fid, 1)
            ok += 1
        except Exception as e:
            if len(errs) < 8:
                errs[fid] = repr(e)
    after = set(S(lambda: a.get_avaliable_furniture_ids()) or [])

    P("reply_obtain_furniture 调用成功:", ok, " 报错:", len(ids) - ok)
    P("owned 前:", len(before), " 后:", len(after), " 新增:", len(after - before))
    P("after 示例:", R(sorted(after)[:40], 300))
    P("errs 示例:", errs)
