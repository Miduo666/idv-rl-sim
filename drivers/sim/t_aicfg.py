# -*- coding: utf-8 -*-
"""人机 AI 配置：QAAIFactory.CONTROLLER_MAP；配表里引用 qaai_* 行为树的位置；scene_config[1] 的开门条件。"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot
GK = simboot.boot(False)
from common_cs import ComuKeys
from common_cs.ai.qaai_butcher.QAAIFactory import QAAIFactory
H = ComuKeys.HERO_ID_MAP
hero = {getattr(H, k): k for k in dir(H) if not k.startswith("_") and isinstance(getattr(H, k), int)}
print("CONTROLLER_MAP:", {(p, hero.get(p)): c for p, c in QAAIFactory.CONTROLLER_MAP.items()})
DM = GK.DM
hits = collections.defaultdict(list)


def scan(v, path, depth=0):
    if depth > 4: return
    if isinstance(v, str):
        if v.startswith("qaai_"): hits[path.split("[")[0]].append((path, v))
    elif isinstance(v, dict):
        for k, x in list(v.items())[:5000]: scan(x, "%s[%r]" % (path, k), depth + 1)
    elif isinstance(v, (list, tuple)):
        for i, x in enumerate(v[:200]): scan(x, "%s[%d]" % (path, i), depth + 1)


for name in list(DM.global_data):
    try:
        scan(getattr(DM, name), name)
    except Exception:
        pass
for t, rows in hits.items():
    print("== %s: %d 处，例 %s" % (t, len(rows), rows[:4]))
sc = DM.scene_config[1]
print("scene1 open_door_condition=%r game_type=%r player_id=%r" % (sc.get("open_door_condition"), sc.get("game_type"), sc.get("player_id")))
