# -*- coding: utf-8 -*-
# probe2 第三轮：定位家具主表(keys⊇new_furniture_info 的 id) + 解锁相关方法签名。
# 已知解锁入口候选：reply_unlock_custom_hall / reply_unlock_hall_component / reply_obtain_furniture。
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)
import inspect

# 1. 家具主表：取 new_furniture_info 里真实的一组 furniture_id 做 superset 判定 + 字段过滤
nfi = S(lambda: a.new_furniture_info) or {}
sample_ids = set()
for v in (nfi.values() if hasattr(nfi, "values") else []):
    for x in (v if isinstance(v, (list, tuple)) else []):
        try: sample_ids.add(int(x))
        except Exception: pass
sample_ids = set(list(sorted(sample_ids))[:8])
P("== new_furniture_info 取样 id = %s ==" % sorted(sample_ids))
P("== keys 含上述全部样本 且字段像家具 的 DM 表 ==")
FURN_FLD = ("furniture", "quality", "g_name", "model", "class", "cost", "icon")
for n in dir(dm):
    if n.startswith("__"):
        continue
    v = S(lambda n=n: getattr(dm, n))
    if isinstance(v, dict) and sample_ids and sample_ids.issubset(set(k for k in v.keys() if isinstance(k, int))):
        anyk = next(iter(sample_ids))
        row = v.get(anyk) if hasattr(v, "get") else None
        flds = set(row.keys()) if hasattr(row, "keys") else set()
        score = sum(1 for f in flds for h in FURN_FLD if h in str(f).lower())
        P("  %-34s size=%-5d score=%d fields=%s" % (n, len(v), score, R(sorted(flds), 200)))
        if score >= 2:
            P("       row[%s]=%s" % (anyk, R(row, 320)))

# 2. 解锁/应用方法签名(不调用，只看参数)
AC = type(a)
P("\n== 解锁相关方法签名 ==")
for nm in ("reply_unlock_custom_hall", "handle_unlock_custom_hall", "reply_update_custom_hall",
           "reply_unlock_hall_component", "reply_update_hall_component", "reply_obtain_furniture",
           "obtain_new_furniture", "operate_new_furniture", "operate_new_furniture_batch",
           "check_add_new_furniture", "get_avaliable_furniture_ids", "get_data_furniture_id",
           "is_hall_unlocked", "update_unlock_cloth_type_info"):
    f = S(lambda nm=nm: getattr(AC, nm, None))
    if f is None:
        P("  %-34s <无此方法>" % nm); continue
    try:
        sig = str(inspect.signature(f))
    except Exception as e:
        co = S(lambda: f.__code__)
        sig = "(%s)" % ", ".join(co.co_varnames[:co.co_argcount]) if co else "?%r" % e
    P("  %s%s" % (nm, sig))

# 3. 零参 getter 安全调用：拿全部可用家具 id 的全集
f = S(lambda: getattr(AC, "get_avaliable_furniture_ids", None))
co = S(lambda: f.__code__) if f else None
if co and co.co_argcount == 1:   # 只有 self
    r = S(lambda: a.get_avaliable_furniture_ids())
    P("\n== get_avaliable_furniture_ids() == cls=%s len=%s %s" % (cname(r), S(lambda: len(r), "-"), R(r, 300)))
else:
    P("\n== get_avaliable_furniture_ids 需要参数 argcount=%s varnames=%s ==" % (
        S(lambda: co.co_argcount), R(S(lambda: co.co_varnames[:6]), 120)))
