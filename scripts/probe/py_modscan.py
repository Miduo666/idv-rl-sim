# -*- coding: utf-8 -*-
r"""列出 sys.modules 里名字匹配关键字的模块，并查它们有没有指定属性。

    python py_modscan.py GK                 # 名字含 GK 的模块
    python py_modscan.py --attr g_unit      # 直接找带 g_unit 属性的模块
"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from idv_probe import discover
from pyw import Py, MASK

SYS_MODULES_OFF = 0xA7029E8
KWS = [a for a in sys.argv[1:] if not a.startswith("--")]
ATTR = sys.argv[sys.argv.index("--attr") + 1] if "--attr" in sys.argv else None

pid, libbase, bss, maps = discover()
p = Py(pid, libbase)
SM = p.qf(libbase + SYS_MODULES_OFF)
print("libbase=0x%X  sys.modules=0x%X" % (libbase, SM))

mods = p.dict_names(SM)
print("读出模块名 %d 个\n" % len(mods))

if KWS:
    hit = [(i, nm, v) for i, nm, v in mods if any(k.lower() in nm.lower() for k in KWS)]
    print("=== 名字含 %s 的模块 %d 个 ===" % (KWS, len(hit)))
    for i, nm, v in hit[:60]:
        md = p.qf(v + 0x10)
        n = 0
        if md:
            r = p.dict_raw(md)
            n = r[2] if r else 0
        print("   #%-5d %-60s module=0x%X md_dict=0x%X 属性%d" % (i, nm, v, md or 0, n))

if ATTR:
    print("\n=== 带属性 '%s' 的模块 ===" % ATTR)
    p.fetch([v for _, _, v in mods], 0x20)
    found = 0
    for i, nm, v in mods:
        md = p.q(v + 0x10)
        if not md:
            continue
        j, val = p.dget(md, ATTR)
        if val:
            tp = p.qf(val + 8)
            print("   #%-5d %-52s %s=0x%X (entry#%d) type=0x%X" % (i, nm, ATTR, val, j, tp or 0))
            found += 1
            if found >= 10:
                break
    if not found:
        print("   没找到")
