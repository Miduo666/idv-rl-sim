import sys, os, dis, marshal
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
want = sys.argv[3]
for rel in sys.argv[4:]:
    co = marshal.loads(open(os.path.join(simenv.ROOT, rel), "rb").read()[16:])
    def walk(c):
        ins = list(dis.get_instructions(c))
        for i, x in enumerate(ins):
            if x.argval == want and x.opname in ("LOAD_METHOD", "LOAD_ATTR"):
                seg = ins[max(0, i-4):i+10]
                print("--", rel, c.co_qualname)
                print("   " + " | ".join("%s %s" % (y.opname, y.argrepr) for y in seg))
        for k in c.co_consts:
            if hasattr(k, "co_code"): walk(k)
    walk(co)
