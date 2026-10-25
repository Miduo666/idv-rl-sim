import sys
sys.path.insert(0, sys.argv[1])
import simboot; GK = simboot.boot(False)
sc = GK.DM.scene_config
print("scene_config entries:", len(sc))
k0 = sorted(sc)[:3]
for k in sorted(sc):
    v = sc[k]
    nm = v.get("name") or v.get("scene_name") or v.get("scene_path") or ""
    if "generator_pos_id" in v or "generator_model_path" in v:
        print(k, repr(nm)[:60], "| gen:", repr(v.get("generator_pos_id"))[:40], "| keys", len(v))
print("--- sample keys of one entry:", sorted(sc[k0[0]].keys())[:80])
pc = GK.DM.pos_config
print("pos_config entries:", len(pc), "sample", list(pc.items())[:2])
