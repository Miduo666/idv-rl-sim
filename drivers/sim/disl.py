import sys, io, dis
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
import marshal, os
def load(rel):
    return marshal.loads(open(os.path.join(simenv.ROOT, rel), "rb").read()[16:])
def find(c, qn):
    if c.co_qualname == qn: return c
    for k in c.co_consts:
        if hasattr(k, "co_code"):
            r = find(k, qn)
            if r: return r
co = load(sys.argv[2])
f = find(co, sys.argv[3]) if len(sys.argv) > 3 else co
lo, hi = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (0, 10**9)
for ins in dis.get_instructions(f):
    if ins.positions.lineno and lo <= ins.positions.lineno <= hi:
        print("%4s %-24s %s" % (ins.positions.lineno, ins.opname, ins.argrepr))
