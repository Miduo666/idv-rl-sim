# -*- coding: utf-8 -*-
import sys, marshal, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
def walk(co,out,seen,depth):
    if id(co) in seen or depth>60: return
    seen.add(id(co))
    nm=co.co_names
    if "ANTI_CHEAT_TYPE" in nm or "anti_mem_modify" in nm or "send_battle_event_safe" in nm:
        nums=[c for c in co.co_consts if isinstance(c,(int,float)) and not isinstance(c,bool)]
        strs=[c for c in co.co_consts if isinstance(c,str) and c.strip() and len(c)<70]
        out.append((getattr(co,"co_qualname",co.co_name),list(nm),nums,strs))
    for c in co.co_consts:
        if hasattr(c,"co_code"): walk(c,out,seen,depth+1)
for p in sys.argv[1:]:
    print("\n##### %s"%p)
    try:
        co=marshal.loads(open(p,"rb").read())   # 无头 .marshal, 直接 loads
        out=[]; walk(co,out,set(),0)
    except Exception as e:
        print("  ERR",repr(e)); continue
    for qn,nm,nums,strs in out:
        print(" FUNC",qn); print("   names:",nm); print("   nums:",nums); print("   strs:",strs)
