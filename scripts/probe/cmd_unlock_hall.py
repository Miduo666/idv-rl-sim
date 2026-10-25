# -*- coding: utf-8 -*-
# 大厅本地解锁：遍历 custom_hall 真实主题(排除 TEST)，reply_unlock_custom_hall(id,{}) 本地解锁 + 刷 UI。
# reply_unlock_custom_hall 已静态坐实 LOCAL(无 call_server_method)，纯本地、安全。
# ‼ 只是"显示拥有"。别去【切换/使用】假大厅——切换走 reply_update_custom_hall 会上行(还没 hook)。
import time
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)
if a is None or dm is None:
    P("g_avatar/DM 未就绪，进大厅再跑")
else:
    tbl = S(lambda: dm.custom_hall) or {}
    hl = a.article_unlock["hall_list"]
    before = sorted(hl)
    def is_test(k):
        row = tbl[k]
        g = str(row.get("g_name", "")) if hasattr(row, "get") else ""
        return "TEST" in g.upper()
    targets = [k for k in sorted(tbl.keys()) if not is_test(k)]
    P("custom_hall 真实主题(排除TEST):", targets)

    did_reply = []; errs = {}
    for k in targets:
        try:
            a.reply_unlock_custom_hall(k, {})      # 内部会 append hall_list + obtain_new_custom_hall + 刷UI
            did_reply.append(k)
        except Exception as e:
            errs[k] = repr(e)
            # 兜底：直接塞进拥有列表
            try:
                if k not in hl: hl.append(k)
            except Exception as e2:
                errs["append_%s" % k] = repr(e2)
    try:
        a.update_hall_ui()
    except Exception as e:
        errs["update_hall_ui"] = repr(e)

    P("reply_unlock 成功:", did_reply)
    P("hall_list 解锁前:", before)
    P("hall_list 解锁后:", sorted(a.article_unlock["hall_list"]))
    P("errs:", errs)
