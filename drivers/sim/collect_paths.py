# -*- coding: utf-8 -*-
"""离线收集要从游戏里取的资源路径：扫全部 pydata 配表里出现的资源路径字符串，按扩展名分类。
输出 JSON: {ext: [path...]}，以及 scene_config 每张图的关键字段。"""
import sys, os, re, json, collections, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot, simenv
GK = simboot.boot(False)

PAT = re.compile(r"^[A-Za-z0-9_./\\\-]+\.([A-Za-z0-9_]{1,12})$")
found = collections.defaultdict(set)
where = collections.defaultdict(set)


def scan(v, src, depth=0):
    if depth > 8: return
    if isinstance(v, str):
        for part in v.split(","):
            s = part.strip()
            if ("/" in s or "\\" in s) and PAT.match(s):
                ext = PAT.match(s).group(1).lower()
                p = s.replace("\\", "/")
                found[ext].add(p); where[p].add(src)
    elif isinstance(v, dict):
        for k, x in v.items():
            scan(k, src, depth + 1); scan(x, src, depth + 1)
    elif isinstance(v, (list, tuple, set, frozenset)):
        for x in v: scan(x, src, depth + 1)


root = os.path.join(simenv.ROOT, "pydata")
bad = 0
for dp, _, fs in os.walk(root):
    for fn in fs:
        if not fn.endswith(".pyc"): continue
        mod = os.path.relpath(os.path.join(dp, fn), simenv.ROOT)[:-4].replace(os.sep, ".")
        if "tid_data" in mod or mod.endswith("__init__"): continue
        try:
            m = importlib.import_module(mod)
        except BaseException:
            bad += 1; continue
        scan(getattr(m, "data", None), mod)
print("modules failed:", bad)
cnt = {e: len(v) for e, v in found.items()}
for e, n in sorted(cnt.items(), key=lambda x: -x[1])[:40]:
    print("%-12s %6d  e.g. %s" % (e, n, sorted(found[e])[0]))
json.dump({e: sorted(v) for e, v in found.items()}, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump({p: sorted(s) for p, s in where.items()}, open(sys.argv[1] + ".where.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
