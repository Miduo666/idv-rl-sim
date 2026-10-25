# -*- coding: utf-8 -*-
import sys, marshal, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
path = sys.argv[1]; subs = [s.lower() for s in sys.argv[2:]]
co = marshal.loads(open(path, "rb").read())
def walk(c, depth=0):
    nm = getattr(c, "co_qualname", c.co_name)
    if any(s in nm.lower() for s in subs):
        print("\n#### %s (args=%d) vars=%s" % (nm, c.co_argcount, list(c.co_varnames)[:12]))
        print("   names:", list(c.co_names))
        strs=[x for x in c.co_consts if isinstance(x,str) and x.strip()]
        print("   strs:", strs[:30])
        print("   nums:", [x for x in c.co_consts if isinstance(x,(int,float)) and not isinstance(x,bool)][:30])
    for x in c.co_consts:
        if hasattr(x,"co_code"): walk(x, depth+1)
walk(co)
