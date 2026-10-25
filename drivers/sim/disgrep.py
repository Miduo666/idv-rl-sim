import sys, dis, marshal, os, re
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
pat = re.compile(sys.argv[3])
co = marshal.loads(open(os.path.join(simenv.ROOT, sys.argv[2]), "rb").read()[16:])
def walk(c):
    if any(pat.search(n) for n in c.co_names):
        print("\n#### def", c.co_qualname)
        for ins in dis.get_instructions(c):
            print("%5s %-26s %s" % (ins.positions.lineno or "", ins.opname, ins.argrepr))
    for k in c.co_consts:
        if hasattr(k, "co_code"): walk(k)
walk(co)
