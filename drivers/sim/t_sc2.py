import sys, traceback
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
try:
    import common_cs.ai.AIButcher
except Exception as e:
    print("ERR", e)
sc = sys.modules.get("servercommon")
print("servercommon:", sc, type(sc), getattr(sc, "__file__", None))
N = sc.Netease
print("Netease:", N, type(N), getattr(N, "__module__", None), getattr(N, "__file__", None))
print([a for a in dir(N) if not a.startswith("__")][:60])
