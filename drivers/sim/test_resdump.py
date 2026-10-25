# -*- coding: utf-8 -*-
"""本地干跑 cmd_resdump_built.py：真实配表 + 假 C_file，验证各阶段逻辑与产物格式。"""
import sys, os, types, json, zipfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot
GK = simboot.boot(False)
OUT = sys.argv[2]
shutil.rmtree(OUT, ignore_errors=True)

calls = []


def fake_get_res_file(p, _):
    calls.append(p)
    n = p.replace("\\", "/")
    if n.endswith(".nav"):
        return b"TESM" + b"\x07\x00\x00\x00" + b"\x00" * 40 + b"\x0c\x00\x00\x006_-15_0.tile\x0c\x00\x00\x007_-15_0.tile"
    if n.endswith(".tile"):
        d = n.rsplit("/", 2)
        return b"TILE" if "/nav/" in n and n.count("/") >= 2 and not n.endswith("_tile/6_-15_0.tile") and "/".join(n.split("/")[:-1]).endswith("nav") else None
    if n.endswith(".scn"):
        return b'<SceneConfig><x path="scene\\scene_battle\\fake\\nav\\fake.nav" m="a\\b.gim"/></SceneConfig>'
    if n.endswith((".scn_col", ".col_mesh")):
        return b"COLDATA" if "_dev" not in n else None
    return b"X"


C = types.ModuleType("C_file"); C.get_res_file = fake_get_res_file
sys.modules["C_file"] = C


def S(f, d=None):
    try:
        return f()
    except Exception:
        return d


g = {"GK": GK, "P": print, "S": S, "RESDUMP_OUT": OUT, "RESDUMP_SYNC": True, "__name__": "probe_cmd"}
src = open(sys.argv[1], encoding="utf-8").read()
exec(compile(src, "cmd_resdump_built.py", "exec"), g)

print("progress:", open(OUT + "/progress.json").read())
print("log tail:\n" + "".join(open(OUT + "/log.txt", encoding="utf-8").readlines()[-12:]))
z = zipfile.ZipFile(OUT + "/res.zip")
names = z.namelist()
print("zip entries:", len(names), names[:5])
man = [json.loads(l) for l in open(OUT + "/manifest.jsonl", encoding="utf-8")]
print("manifest:", len(man), man[0])
print("miss:", sum(1 for _ in open(OUT + "/miss.jsonl", encoding="utf-8")))
print("nav_report sample:", list(json.load(open(OUT + "/nav_report.json", encoding="utf-8")).items())[:2])
print("files:", sorted(os.listdir(OUT)))
print("get_res_file calls:", len(calls))
