# -*- coding: utf-8 -*-
"""1v4 需要的配置：角色 pid、人机行为树名、地图出生点。"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot
GK = simboot.boot(False)
from common_cs import ComuKeys
U = ComuKeys.UNIT_TYPE_CONF
DM = GK.DM
cnt = collections.Counter(r.get("class") for r in DM.player.values())
print("player 按 class:", cnt, " CIVILIAN=%s BUTCHER=%s" % (U.CIVILIAN, U.BUTCHER))
H = ComuKeys.HERO_ID_MAP
hero = {getattr(H, k): k for k in dir(H) if not k.startswith("_") and isinstance(getattr(H, k), int)}
for c in (U.CIVILIAN, U.BUTCHER):
    rows = sorted(p for p, r in DM.player.items() if r.get("class") == c)
    print("class %s: %d 个, 前 12:" % (c, len(rows)), [(p, hero.get(p)) for p in rows[:12]])
bt = sorted(f[:-4] for f in os.listdir(os.path.join(simboot.simenv.ROOT, "common_cs", "ai", "bt_code")) if f.startswith("qaai"))
print("qaai 行为树 %d 个:" % len(bt), bt[:60])
sc = DM.scene_config[1]
for k in ("civilian_pos_id", "butcher_pos_id", "generator_pos_id", "server_col", "server_nav", "name"):
    print("scene1.%s = %r" % (k, sc.get(k)))
print("ai_terror_data 键例:", list(DM.ai_terror_data)[:10] if hasattr(DM, "ai_terror_data") else None)
