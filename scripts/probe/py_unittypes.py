# -*- coding: utf-8 -*-
r"""列出 units_by_type 的全部键: 每个 unit_type 对应的类名、数量，以及该类有没有进度类属性。"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from idv_probe import discover
from pyw import Py, MASK

SYS_MODULES_OFF = 0xA7029E8
PROBE = ("fix_process", "hack_process", "be_fixed_flag", "state", "uid", "position")

pid, libbase, bss, maps = discover()
p = Py(pid, libbase)


def tpname(tp):
    n = p.qf(tp + 0x18)
    if not n:
        return "?"
    p.fetch([n], 0x60)
    s = p.get(n, 64)
    return s.split(b"\0")[0].decode("utf-8", "replace") if s else "?"


SM = p.qf(libbase + SYS_MODULES_OFF)
UM = None
for i, nm, v in p.dict_names(SM):
    md = p.qf(v + 0x10)
    if not md:
        continue
    r = p.dict_raw(md)
    if not r or not (100 <= r[2] <= 200):
        continue
    j, um = p.dget(md, "unit_mgr")
    if um:
        UM = um
        print("模块 '%s'  unit_mgr=0x%X (entry#%d)" % (nm, um, j))
        break
if not UM:
    sys.exit("没找到 unit_mgr")

ud = p.inst_dict(UM)
bi, UBT = p.dget(ud, "units_by_type")
print("units_by_type = 0x%X (entry#%d)\n" % (UBT, bi))

print("%-6s %-8s %-26s %s" % ("键", "数量", "类名", "有这些属性"))
print("-" * 78)
for i, k, v in p.dict_pairs(UBT):
    t = p.longval(k)
    items = p.list_items(v)
    if not items:
        print("%-6s %-8d %-26s" % (t, 0, "(空)"))
        continue
    o = items[0]
    cls = tpname(p.qf(o + 8))
    d = p.inst_dict(o)
    have = []
    names = {nm for _, nm, _ in p.dict_names(d)}
    for a in PROBE:
        if a in names:
            have.append(a)
    print("%-6s %-8d %-26s %s" % (t, len(items), cls, ", ".join(have)))
