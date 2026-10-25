import sys, os, dis, marshal, collections
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
found = collections.Counter()
for dp, _, fs in os.walk(simenv.ROOT):
    for fn in fs:
        if not fn.endswith(".pyc"): continue
        try: co = marshal.loads(open(os.path.join(dp, fn), "rb").read()[16:])
        except Exception: continue
        def walk(c):
            ins = list(dis.get_instructions(c))
            for i, x in enumerate(ins):
                if x.opname in ("LOAD_GLOBAL", "LOAD_NAME") and x.argval == "isinstance":
                    for y in ins[i+1:i+12]:
                        if y.opname in ("LOAD_GLOBAL", "LOAD_NAME", "LOAD_FAST") and y.argval in ("world", "render", "collision", "game3d"):
                            j = ins.index(y)
                            if j + 1 < len(ins) and ins[j+1].opname == "LOAD_ATTR":
                                found["%s.%s" % (y.argval, ins[j+1].argval)] += 1
                        if y.opname in ("PRECALL", "CALL"): break
            for k in c.co_consts:
                if hasattr(k, "co_code"): walk(k)
        walk(co)
print(found.most_common())
