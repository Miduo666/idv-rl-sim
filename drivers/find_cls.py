# -*- coding: utf-8 -*-
import sys, marshal, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
path = sys.argv[1]; targets = set(sys.argv[2:])
co = marshal.loads(open(path, "rb").read())
def walk(c):
    if c.co_name in targets:
        print("\n######## class/func: %s ########" % c.co_name)
        members = [x for x in c.co_consts if isinstance(x, str)]
        nums = [x for x in c.co_consts if isinstance(x,(int,float)) and not isinstance(x,bool)]
        print("  names:", list(c.co_names))
        print("  str_consts:", members)
        print("  num_consts:", nums)
    for x in c.co_consts:
        if hasattr(x, "co_code"):
            walk(x)
walk(co)
