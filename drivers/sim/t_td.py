import sys, os, dis, marshal
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
co = marshal.loads(open(os.path.join(simenv.ROOT, "pydata", sys.argv[2]), "rb").read()[16:])
ins = list(dis.get_instructions(co))
n = 0
for i, x in enumerate(ins):
    if x.opname == "LOAD_NAME" and x.argval == "TD":
        nx = ins[i + 1]
        r = repr(nx.argval)
        print(x.positions.lineno, nx.opname, type(nx.argval).__name__, r[:150], "| next:", ins[i+2].opname, repr(ins[i+2].argval)[:60])
        n += 1
        if n > 14: break
