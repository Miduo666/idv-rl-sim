# -*- coding: utf-8 -*-
# probe2 第四轮：家具主表(靠 get_data_furniture_id 映射 + 按"行里有 furniture 字段/JIAJU 名"扫表)
#   + custom_hall_component_data 全貌 + unlock_info/update_info 结构样本。
gk = GK
a  = S(lambda: gk.g_avatar)
dm = S(lambda: gk.DM)

# 1. furniture_id -> data id 映射(看间接层)
avail = S(lambda: a.get_avaliable_furniture_ids()) or []
P("== get_data_furniture_id 映射 ==")
for fid in list(avail)[:8]:
    P("  furniture_id %s -> data %s" % (fid, R(S(lambda fid=fid: a.get_data_furniture_id(fid)), 120)))

# 2. 按"行字段里带 furniture / 行 g_name 带 JIAJU/FURNITURE"扫所有 DM 表 = 家具目录
P("\n== 行内容像家具的 DM 表(字段含 furniture 或 g_name 含 JIAJU) ==")
for n in dir(dm):
    if n.startswith("__"):
        continue
    v = S(lambda n=n: getattr(dm, n))
    if not isinstance(v, dict) or not v:
        continue
    k0 = next(iter(v.keys()))
    row = v.get(k0) if hasattr(v, "get") else None
    flds = set(str(x) for x in row.keys()) if hasattr(row, "keys") else set()
    gname = str(row.get("g_name", "")) if hasattr(row, "get") else ""
    has_fur_fld = any("furniture" in f.lower() for f in flds)
    has_jiaju = "JIAJU" in gname.upper() or "FURNITURE" in gname.upper()
    if has_fur_fld or has_jiaju:
        P("  %-34s size=%-5d fields=%s" % (n, len(v), R(sorted(flds), 180)))

# 3. custom_hall_component_data 全键 + 带 g_name 的样本(是不是家具目录)
chc = S(lambda: getattr(dm, "custom_hall_component_data"))
if isinstance(chc, dict):
    ks = sorted([k for k in chc.keys() if isinstance(k, int)])
    P("\n== custom_hall_component_data keys(%d) = %s" % (len(chc), R(ks, 300)))
    shown = 0
    for k in ks:
        row = chc[k]
        if hasattr(row, "get") and row.get("g_name"):
            P("   [%s] %s" % (k, R(row, 200))); shown += 1
            if shown >= 5:
                break
    if shown == 0:
        P("   (无 g_name 字段，前3行:)")
        for k in ks[:3]:
            P("   [%s] %s" % (k, R(chc[k], 200)))

# 4. hall_component_data 全量(3 条)
hcd = S(lambda: getattr(dm, "hall_component_data"))
if isinstance(hcd, dict):
    P("\n== hall_component_data 全量 ==")
    for k in sorted(hcd.keys()):
        P("   [%s] %s" % (k, R(hcd[k], 240)))

# 5. unlock_info / update_info 结构：从已有的 custom_hall_info / saved 里反推
P("\n== custom_hall_info 结构(unlock/update_info 参考) ==")
chi = S(lambda: a.custom_hall_info)
if isinstance(chi, dict):
    for hk in list(chi.keys())[:1]:
        P("   hall %s = %s" % (hk, R(chi[hk], 500)))
P("== saved_custom_hall_info == %s" % R(S(lambda: a.saved_custom_hall_info), 300))
P("== custom_hall_other_info == %s" % R(S(lambda: a.custom_hall_other_info), 400))

# 6. 大厅拥有/解锁判定：hall_list 与 is_hall_unlocked 对几个 hall 的结果
P("\n== hall_list == %s" % R(S(lambda: a.article_unlock.get('hall_list')), 120))
for hid in (1, 9, 15, 23, 4):
    P("   is_hall_unlocked(%s)=%s" % (hid, R(S(lambda hid=hid: a.is_hall_unlocked(hid)), 40)))
