# -*- coding: utf-8 -*-
# probe5 管家持久链: 纯读。确定 1)housekeeper 表 id 全集 2)article_setting 里"当前装配管家"字段
#   3)当前装配 id 在不在拥有库(pp['67']/'203'/'105') —— 坐实"使用中 vs 未解锁"是不是两套独立状态。
import time
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)

# ---- 1. housekeeper 配表 ----
P("=== 1. dm.housekeeper 配表 ===")
hk = S(lambda: dm.housekeeper)
hkset = set()
if hk is not None and hasattr(hk, "keys"):
    ks = sorted(k for k in hk.keys() if isinstance(k, int))
    hkset = set(ks)
    P("数量:", len(ks))
    P("ids:", R(ks, 1500))
    if ks:
        s0 = S(lambda: hk[ks[0]])
        P("样本记录 id=%r = %s" % (ks[0], R(s0, 500)))
        flds = None
        if hasattr(s0, "__dict__"):
            flds = S(lambda: list(vars(s0).keys()))
        elif hasattr(s0, "keys"):
            flds = S(lambda: list(s0.keys()))
        P("记录字段:", R(flds, 400))
        # id=78 的完整记录(疑似花布侍女)
        if 78 in hkset:
            P("id=78 记录 =", R(S(lambda: hk[78]), 600))
else:
    P("housekeeper 读不到")

# ---- 2. article_setting 全字段(跳过超长的 role_* 等) ----
P("=== 2. a.article_setting 全标量字段(找当前装配管家) ===")
asv = S(lambda: a.article_setting)
SKIP = ("role_motion", "role_poster", "face_matching", "sharing_photos",
        "butcher_dishes", "civilian_dishes")
cur_candidates = []
if asv and hasattr(asv, "keys"):
    for k in sorted(asv.keys()):
        v = S(lambda k=k: asv.get(k))
        if k in SKIP:
            P("  %s: <跳过 len=%s>" % (k, len(v) if hasattr(v, "__len__") else "?"))
            continue
        P("  %s = %s" % (k, R(v, 160)))
        # 收集值落在 housekeeper id 集里的字段 => 当前装配管家
        try:
            if isinstance(v, int) and v in hkset:
                cur_candidates.append((k, v))
        except Exception:
            pass
P("  >>> 值命中 housekeeper id 的字段(疑似当前装配):", R(cur_candidates, 300))

# ---- 3. 拥有库 props_id 全集 + 跟 housekeeper 交叉 + 当前装配是否已拥有 ----
P("=== 3. 拥有库 ∩ housekeeper ===")
pp = S(lambda: a.props_package)
owned_by_lib = {}
for key in ("67", "203", "105", "14"):
    lib = S(lambda key=key: pp.get(key)) if pp else None
    if lib is None:
        continue
    ids = []
    for ok in (lib.keys() if hasattr(lib, "keys") else []):
        try:
            ids.append(int(ok))
        except Exception:
            pass
    ids = sorted(set(ids))
    owned_by_lib[key] = set(ids)
    inter = sorted(set(ids) & hkset)
    P("  pp[%r]: %d 条 ids=%s ; ∩housekeeper=%s" % (key, len(ids), R(ids, 240), R(inter, 200)))

# 结论: 当前装配 id 是否在任一拥有库
for k, v in cur_candidates:
    where = [lib for lib, s in owned_by_lib.items() if v in s]
    P("  装配字段 %s=%d : 拥有库命中=%s %s" % (k, v, where or "无(=未解锁却在用!)", ""))
P(">>> 若'当前装配管家 id'不在任何拥有库 => 装配(使用中)与拥有(未解锁)确为两套独立状态, 且该状态服务器持久。")
