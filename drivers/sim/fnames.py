import sys, os, marshal
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
want = sys.argv[3].split(",")
co = marshal.loads(open(os.path.join(simenv.ROOT, sys.argv[2]), "rb").read()[16:])
def walk(c):
    if c.co_qualname.split(".")[-1] in want:
        print("def %s(%s)\n   names: %s" % (c.co_qualname, ",".join(c.co_varnames[:c.co_argcount]), " ".join(c.co_names)))
        s = [k for k in c.co_consts if isinstance(k, str) and k.strip()]
        if s: print("   strs:", s[:25])
    for k in c.co_consts:
        if hasattr(k, "co_code"): walk(k)
walk(co)
