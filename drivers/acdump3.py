# -*- coding: utf-8 -*-
import sys, marshal, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
KW=[k.lower() for k in sys.argv[1].split(",")]
def hit(co):
    pool=[s.lower() for s in co.co_names]+[c.lower() for c in co.co_consts if isinstance(c,str)]
    return any(any(k in s for s in pool) for k in KW)
def walk(co,out,seen,d):
    if id(co) in seen or d>60: return
    seen.add(id(co))
    if hit(co):
        nums=[c for c in co.co_consts if isinstance(c,(int,float)) and not isinstance(c,bool)]
        strs=[c for c in co.co_consts if isinstance(c,str) and c.strip() and len(c)<80]
        out.append((getattr(co,"co_qualname",co.co_name),list(co.co_names),nums,strs))
    for c in co.co_consts:
        if hasattr(c,"co_code"): walk(c,out,seen,d+1)
for p in sys.argv[2:]:
    print("\n##### %s"%p.split("/")[-1])
    try:
        co=marshal.loads(open(p,"rb").read()); out=[]; walk(co,out,set(),0)
    except Exception as e:
        print("  ERR",repr(e)); continue
    for qn,nm,nums,strs in out:
        print(" FUNC",qn); print("   names:",nm); print("   nums:",nums); print("   strs:",strs)
