import sys, os, dis, marshal, collections
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
cnt = collections.Counter(); ex = {}
for dp, _, fs in os.walk(os.path.join(simenv.ROOT, "common_cs")):
    for fn in fs:
        if not fn.endswith(".pyc"): continue
        p = os.path.join(dp, fn)
        co = marshal.loads(open(p, "rb").read()[16:])
        def walk(c):
            ins = list(dis.get_instructions(c))
            for i, x in enumerate(ins[:-1]):
                if x.opname in ("LOAD_ATTR",) and x.argval in ("_scene_col", "scene_col") and ins[i+1].opname in ("LOAD_METHOD", "LOAD_ATTR"):
                    m = ins[i+1].argval; cnt[m] += 1; ex.setdefault(m, os.path.relpath(p, simenv.ROOT) + ":" + c.co_qualname)
            for k in c.co_consts:
                if hasattr(k, "co_code"): walk(k)
        walk(co)
for m, n in cnt.most_common(40): print("%5d %-28s %s" % (n, m, ex[m]))
