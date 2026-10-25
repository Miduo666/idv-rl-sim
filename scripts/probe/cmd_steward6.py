# -*- coding: utf-8 -*-
# probe6 收口: 1)列 avatar 全字段名(眼找"当前管家"字段) 2)全5个housekeeper记录(用模型路径认花布侍女)
#   3)管家/新获得库完整记录(找 试用/到期 字段) 4)关键字段(keeper/guanjia/trial/expire/current...)
import time
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)

# ---- 1. avatar 全字段名 ----
P("=== 1. avatar 全字段名 ===")
d = S(lambda: vars(a)) or {}
P(R(sorted(d.keys()), 3000))

# ---- 2. 全 5 个 housekeeper 记录 ----
P("=== 2. dm.housekeeper 全 5 条 ===")
hk = S(lambda: dm.housekeeper)
if hk is not None and hasattr(hk, "keys"):
    for k in sorted(x for x in hk.keys() if isinstance(x, int)):
        rec = S(lambda k=k: hk[k])
        # 只挑能认名字的字段
        pick = {}
        src = vars(rec) if hasattr(rec, "__dict__") else (rec if hasattr(rec, "get") else {})
        for f in ("id", "but_keeper_name", "cil_keeper_name", "but_img_path", "cil_img_path",
                  "but_housekeeper", "cil_housekeeper", "hall_id", "name", "desc"):
            try:
                v = src.get(f) if hasattr(src, "get") else getattr(rec, f, None)
                if v is not None:
                    pick[f] = v
            except Exception:
                pass
        P("  id=%r: %s" % (k, R(pick, 400)))

# ---- 3. 管家/新获得库完整记录(找 试用/到期) ----
P("=== 3. pp['105'] / pp['67'] / pp['203'] 完整记录 ===")
pp = S(lambda: a.props_package)
for key in ("105", "67", "203"):
    lib = S(lambda key=key: pp.get(key)) if pp else None
    P("  pp[%r] = %s" % (key, R(lib, 700)))

# ---- 4. 关键字段扫描 ----
P("=== 4. avatar 字段名含 keeper/guanjia/trial/expire/current/experience/limit/temp/free ===")
KW = ["keeper", "guanjia", "trial", "expire", "end_time", "current", "cur_",
      "experience", "limit", "temp", "free", "preview", "试", "管家"]
cnt = 0
for fk in sorted(d.keys()):
    if any(x in str(fk).lower() for x in KW):
        P("  a.%s = %s" % (fk, R(d.get(fk), 300)))
        cnt += 1
if cnt == 0:
    P("  (无命中)")
P(">>> 目标: 认出花布侍女是哪个housekeeper id + 它在不在pp['105'] + '当前管家'存哪 + 有无到期字段")
