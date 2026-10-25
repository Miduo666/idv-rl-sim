# -*- coding: utf-8 -*-
"""核对导出覆盖率：每个 scene_config 的 server_col / col_mesh / server_nav(+块) 是否齐。用法: dump_coverage.py <res_recovered.zip>"""
import sys, os, re, zipfile, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot
GK = simboot.boot(False)
z = zipfile.ZipFile(sys.argv[1])
have = set(z.namelist())
ext = collections.Counter(n.rsplit(".", 1)[-1] for n in have)
print("by ext:", ext.most_common())


def tiles_of(nav):
    b = z.read(nav)
    names = []
    for m in re.finditer(rb"\.tile", b):
        e = m.end()
        for L in range(6, 240):
            s0 = e - L
            if s0 < 4: break
            if int.from_bytes(b[s0 - 4:s0], "little") == L and all(32 < c < 127 for c in b[s0:e]):
                names.append(b[s0:e].decode()); break
    d = nav.rsplit("/", 1)[0]; stem = nav.rsplit("/", 1)[1][:-4]
    for c in (d, d + "/" + stem):
        got = sum(1 for n in names if c + "/" + n in have)
        if got:
            return len(names), got
    return len(names), 0


rows = []
seen = set()
for sid, cfg in sorted(GK.DM.scene_config.items()):
    col = (cfg.get("server_col") or "").replace("\\", "/")
    nav = (cfg.get("server_nav") or "").replace("\\", "/")
    if not col and not nav: continue
    key = (col, nav)
    if key in seen: continue
    seen.add(key)
    name = cfg.get("scene_name", "")
    r = {"sid": sid, "name": name, "col": col in have, "col_mesh": col.replace(".scn_col", ".col_mesh") in have,
         "nav": nav in have}
    r["tiles"] = "%d/%d" % tuple(reversed(tiles_of(nav))) if nav in have else "-"
    for pre in ("ai_", "moveable_"):
        pn = nav.rsplit("/", 1)[0] + "/" + pre + nav.rsplit("/", 1)[1] if nav else ""
        r[pre] = ("%d/%d" % tuple(reversed(tiles_of(pn)))) if pn in have else "-"
    rows.append(r)
ok_all = sum(1 for r in rows if r["col"] and r["nav"] and r["tiles"] != "-" and r["tiles"].split("/")[0] == r["tiles"].split("/")[1])
print("distinct (server_col, server_nav) maps:", len(rows), " fully ok:", ok_all)
for r in rows:
    flag = "" if (r["col"] and r["nav"] and r["tiles"] != "-" and r["tiles"].split("/")[0] == r["tiles"].split("/")[1]) else "  <<<"
    print("%4s %-36s col=%d mesh=%d nav=%d tiles=%-9s ai=%-9s mov=%-9s%s" % (
        r["sid"], r["name"][:36], r["col"], r["col_mesh"], r["nav"], r["tiles"], r["ai_"], r["moveable_"], flag))
