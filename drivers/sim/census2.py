# -*- coding: utf-8 -*-
"""启动 GK.DM 后，导入若干包下全部模块，统计成功率与失败原因。用法: census2.py 包1,包2 输出.json"""
import sys, os, json, collections, importlib, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot, simenv
simboot.boot()
ROOT = simenv.ROOT

mods = []
for pkg in sys.argv[1].split(","):
    for dp, _, fs in os.walk(os.path.join(ROOT, *pkg.split("."))):
        for fn in fs:
            if fn.endswith(".pyc"):
                m = os.path.relpath(os.path.join(dp, fn), ROOT)[:-4].replace(os.sep, ".")
                mods.append(m[:-9] if m.endswith(".__init__") else m)
mods.sort()
ok = collections.Counter()
tot = collections.Counter()
fails = collections.Counter()
ex = {}
for m in mods:
    top = m.split(".")[0]
    tot[top] += 1
    try:
        importlib.import_module(m)
        ok[top] += 1
    except BaseException as e:
        tb = traceback.extract_tb(e.__traceback__)
        where = "%s:%s" % (tb[-1].filename, tb[-1].lineno) if tb else "?"
        k = "%s: %s" % (type(e).__name__, str(e)[:90])
        fails[k] += 1
        ex.setdefault(k, (m, where))
for t in tot:
    print("%-12s %5d / %5d  (%.0f%%)" % (t, ok[t], tot[t], 100.0 * ok[t] / tot[t]))
print("stub modules:", len(simenv.STUBMODS))
print("fail kinds:", len(fails))
for k, n in fails.most_common(25):
    print("  %5d %s\n        e.g. %s @ %s" % (n, k, ex[k][0], ex[k][1]))
json.dump({"ok": dict(ok), "tot": dict(tot), "fails": [(k, n, ex[k]) for k, n in fails.most_common()],
           "stubs": sorted(simenv.STUBMODS), "access": simenv.ACCESS.most_common()},
          open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
