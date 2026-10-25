# -*- coding: utf-8 -*-
"""npc_data 里带 ai 的条目，按 class 分组；以及 UNIT_TYPE_CONF 名字。"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot
GK = simboot.boot(False)
from common_cs import ComuKeys
U = ComuKeys.UNIT_TYPE_CONF
names = {getattr(U, k): k for k in dir(U) if not k.startswith("_") and isinstance(getattr(U, k), int)}
nd = GK.DM.npc_data
by = collections.defaultdict(list)
for pid, row in nd.items():
    if row.get("ai"):
        by[row.get("class")].append((pid, row.get("ai"), row.get("real_name_tid"), row.get("model_path", "")[-40:]))
print("npc_data 共 %d 条，带 ai %d 条" % (len(nd), sum(map(len, by.values()))))
for c, rows in sorted(by.items(), key=lambda x: -len(x[1])):
    print("class=%s(%s) %d 条  例: %s" % (c, names.get(c), len(rows), rows[:3]))
ai = collections.Counter(r[1] for rows in by.values() for r in rows)
print("ai 取值 top:", ai.most_common(25))
print("keys 例:", sorted(next(iter(nd.values())).keys()))
