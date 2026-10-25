import sys
sys.path.insert(0, sys.argv[1])
import simboot; GK = simboot.boot(False)
from common_cs import ComuKeys
cid = ComuKeys.UNDERTAKER_CONST_COLLECTION.COFFIN_CREATE_ID
d = GK.DM.skill_creature_data
print("type", type(d), "len", len(d), "cid", cid, "in", cid in d)
print("entry:", d.get(cid))
import pydata.skill_creature_data as m
print("module attrs:", [a for a in dir(m) if not a.startswith("__")])
ks = list(d.keys())[:5]; print("sample keys", ks, d[ks[0]] if ks else None)
