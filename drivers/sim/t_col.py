import sys
sys.path.insert(0, sys.argv[1])
import simboot; GK = simboot.boot(False)
from common_tools import utils
for sid in (6, 1, 18):
    try:
        print(sid, "col path:", repr(utils.get_scene_col_path(sid)))
    except Exception as e:
        print(sid, "ERR", e)
v = GK.DM.scene_config[6]
for k in sorted(v):
    if any(s in k for s in ("path", "col", "nav", "scene", "surface", "voxel", "sdf")):
        print("   ", k, "=", repr(v[k])[:120])
