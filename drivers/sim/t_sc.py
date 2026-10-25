import sys, traceback
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
orig = simenv.StubModule.__setattr__
def logset(self, k, v):
    if self.__name__ == "servercommon" or k in ("Netease", "DM"):
        print("SETATTR %s.%s = %r" % (self.__name__, k, v))
        for fr in traceback.extract_stack()[-6:-1]: print("     ", fr.filename, fr.lineno, fr.name)
    orig(self, k, v)
simenv.StubModule.__setattr__ = logset
try:
    import common_cs.h55_utils.utils_attack
except Exception as e:
    print("ERR", e)
import servercommon
print("Netease =", servercommon.Netease, type(servercommon.Netease), [a for a in dir(servercommon.Netease) if not a.startswith("_")][:40])
