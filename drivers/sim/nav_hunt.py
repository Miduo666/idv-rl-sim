# -*- coding: utf-8 -*-
"""从设备场景包(idx+wpk)里按内容找导航资源：导出包缺的 .nav(MSET) 与 .tilecache(TEST)。
用法: nav_hunt.py <scene.idx> <nav_entries.json> <输出目录>
nav_entries.json 由 data/scene_classify.tsv 按魔数筛出（见 SKILL §9.10）。"""
import sys, os, json, struct, types, logging
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "tools", "NeoXtractor-IDXWPK")))
logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile
import navmesh

idx, entries, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
os.makedirs(out, exist_ok=True)
f = IDXWPKFile(idx)
rows = []
for tag in ("TESM导航总表", "TEST tilecache总表"):
    for i, md5, size, known in entries.get(tag, []):
        d = f.read_entry(i).data
        open(os.path.join(out, "%s_%d.%s" % (md5, i, "nav" if tag.startswith("TESM") else "tilecache")), "wb").write(d)
        if tag.startswith("TESM"):
            magic, ver, ntiles = struct.unpack_from("<4sii", d, 0)
            orig = struct.unpack_from("<3f", d, 12); tw, th = struct.unpack_from("<2f", d, 24); mt, mp = struct.unpack_from("<2i", d, 32)
            names = navmesh.tile_names(d)
            rows.append(dict(kind="nav", idx=i, md5=md5, known=known, size=size, ver=ver, ntiles=ntiles, orig=[round(v, 1) for v in orig],
                             tile=[tw, th], max_tiles=mt, max_polys=mp, names=len(names), name0=names[:2]))
        else:
            rows.append(dict(kind="tilecache", idx=i, md5=md5, known=known, size=size, head=d[:96].hex()))
json.dump(rows, open(os.path.join(out, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("写出 %d 个 -> %s" % (len(rows), out))
