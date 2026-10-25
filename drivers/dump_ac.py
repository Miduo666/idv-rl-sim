# -*- coding: utf-8 -*-
import sys, marshal, io
sys.setrecursionlimit(20000)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
def load(p):
    b=open(p,"rb").read()
    for x in (b[16:],b):
        try:
            c=marshal.loads(x)
            if hasattr(c,"co_filename"): return c
        except Exception: pass
    raise SystemExit("bad")
def walk(co,out,seen):
    if id(co) in seen: return
    seen.add(id(co))
    if "ANTI_CHEAT_TYPE" in co.co_names or any(k in co.co_names for k in("send_battle_event_safe","anti_mem_modify")):
        nums=[c for c in co.co_consts if isinstance(c,(int,float)) and not isinstance(c,bool)]
        strs=[c for c in co.co_consts if isinstance(c,str) and c.strip() and len(c)<70]
        out.append((getattr(co,"co_qualname",co.co_name),list(co.co_varnames)[:18],list(co.co_names),nums,strs))
    for c in co.co_consts:
        if hasattr(c,"co_code"): walk(c,out,seen)
for p in sys.argv[1:]:
    print("\n##################### %s" % p)
    out=[]
    try:
        walk(load(p),out,set())
    except Exception as e:
        print("  ERR", repr(e)); continue
    for qn,vs,nm,nums,strs in out:
        print(" FUNC %s  vars=%s" % (qn,vs))
        print("    names:",nm)
        print("    nums :",nums)
        print("    strs :",strs)
