import sys, io
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
import marshal, os
co = marshal.loads(open(os.path.join(simenv.ROOT, sys.argv[2]), "rb").read()[16:])
def walk(c, depth=0):
    strs = [k for k in c.co_consts if isinstance(k, str) and k.strip()][:12]
    print("  " * depth + "def %s(%s)" % (c.co_qualname, ",".join(c.co_varnames[:c.co_argcount])))
    if depth >= 1:
        print("  " * depth + "   names: " + " ".join(c.co_names)[:400])
        if strs: print("  " * depth + "   strs: %r" % strs)
    for k in c.co_consts:
        if hasattr(k, "co_code") and depth < 2: walk(k, depth + 1)
walk(co)
