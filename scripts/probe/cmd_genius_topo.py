# -*- coding: utf-8 -*-
# probe2 命令：dump 监管天赋树的【完整拓扑】，给叠加层画径向树用。
#   目标三样：① 每个 id 的 pre_genius(父)、layer、node_seq、可选等级；
#            ② 一个节点 taggeddict 的全部键名(找有没有自带坐标/角度/分支/序号这类布局字段)；
#            ③ GK.DM 里可能的布局/分支表(*_genius_data / *_find_dict / branch_* / *_max_data)。
#   配表是账号级，天赋页/大厅/局内任意时刻都能跑。不能 sleep。

gk = GK
dm = S(lambda: gk.DM)

def row_min(gid):
    row = S(lambda: dm.butcher_genius[gid])
    if row is None:
        return None, None
    try:
        k = min(row.keys()); return row, row[k]
    except Exception:
        return row, None

# ---- ① 全 40 节点拓扑 ----
P("===== butcher_genius 40 节点拓扑 =====")
P("%-4s %-6s %-6s %-10s %s" % ("id", "layer", "nseq", "lv可选", "pre_genius(父)"))
for gid in range(1, 41):
    row, d = row_min(gid)
    if d is None:
        P("%-4d <取不到>" % gid); continue
    layer = S(lambda: d['layer'])
    nseq  = S(lambda: d['node_seq'])
    pre   = S(lambda: d['pre_genius'])
    lvs   = S(lambda: sorted(row.keys()))
    P("%-4d %-6s %-6s %-10s %s" % (gid, layer, nseq, R(lvs, 10), R(pre, 40)))

# ---- ② 一个节点的全部键名(找布局字段) ----
P("\n===== butcher_genius[1] taggeddict 全部键 =====")
_, d1 = row_min(1)
if d1 is not None:
    try:
        keys = list(d1.keys())
    except Exception as e:
        keys = "取键失败: %r" % (e,)
    P("键(%d): %s" % (len(keys) if isinstance(keys, list) else -1, R(keys, 400)))
    # 把每个键的值也打出来，一眼看有没有 pos/angle/x/y/index/branch
    if isinstance(keys, list):
        for k in keys:
            v = S(lambda k=k: d1[k])
            P("   %-24r = %s" % (k, R(v, 60)))

# ---- ③ DM 上可能的布局/分支表 ----
P("\n===== GK.DM 相关表探测 =====")
for name in ("butcher_genius_data", "butcher_genius_find_dict", "butcher_genius_max_data",
             "branch_passive_item_data", "recommend_genius", "pid_genius"):
    obj = S(lambda name=name: getattr(dm, name))
    if obj is None:
        P("  dm.%s = 取不到/None" % name); continue
    try:
        ks = list(obj.keys())
        P("  dm.%s : dict, 键数=%d, 样例键=%s" % (name, len(ks), R(ks[:8], 80)))
        if ks:
            P("     首项 %r -> %s" % (ks[0], R(obj[ks[0]], 100)))
    except Exception:
        P("  dm.%s : %s" % (name, R(obj, 80)))
