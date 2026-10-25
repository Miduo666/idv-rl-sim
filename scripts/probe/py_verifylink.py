# -*- coding: utf-8 -*-
r"""验证 GeneratorUnit.model -> +0x20/+0x28/+0x30 -> 场景对象 这条身份链对每台机器都成立。"""
import sys, os, json, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem
from idv_probe import discover, dump_bss, find_sigs, class_names, read_objects, MASK
from pyw import Py

SYS_MODULES_OFF = 0xA7029E8
PYLONG_T_OFF = 0xA026498
PYFLOAT_T_OFF = 0xA0336F0
MODNAME = "game_kernel"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_cache.json")

pid, libbase, bss, maps = discover()
d = dump_bss(pid, bss, True)
head = find_sigs(d, bss[0], libbase)["array"][0]
m = Mem(pid); m.quiet = True
r = read_objects(m, head)
names = class_names(m, r["objs"])
全部 = set(r["objs"])
senders = {o for o in r["objs"] if "sender" in names.get(o, "").lower()}
m.fetch([o + 0x240 for o in senders], "")
m.fetch([(m.q(o + 0x28) & MASK) + k for o in senders if m.q(o + 0x28) for k in (0, 0xa0)], "")

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
p = Py(pid, libbase)
LONG_T = libbase + PYLONG_T_OFF
FLOAT_T = libbase + PYFLOAT_T_OFF
SM = p.qf(libbase + SYS_MODULES_OFF)
_, mod = p.dget(SM, MODNAME, cache.get("mod"))
md = p.qf(mod + 0x10)
_, UM = p.dget(md, "unit_mgr", cache.get("unit_mgr"))
ud = p.inst_dict(UM)
_, UBT = p.dget(ud, "units_by_type", cache.get("units_by_type"))
lst = None
for i, k, v in p.dict_pairs(UBT):
    if p.longval(k) == 3:
        lst = v
        break
items = p.list_items(lst)
p.fetch([o - 0x18 for o in items], 0x20)


def 值(vp):
    if not vp:
        return None
    p.fetch([vp], 0x20)
    b = p.get(vp, 32)
    if not b:
        return None
    tp = struct.unpack_from("<Q", b, 8)[0] & MASK
    if tp == FLOAT_T:
        return struct.unpack_from("<d", b, 16)[0]
    if tp == LONG_T:
        sz = struct.unpack_from("<q", b, 16)[0]
        return float(struct.unpack_from("<I", b, 24)[0]) if sz else 0.0
    return None


print("%-14s %-6s %-8s %-16s %s" % ("GeneratorUnit", "属性数", "进度", "model对象", "model+0x20 -> 场景对象"))
print("-" * 104)
for o in items:
    dd = p.inst_dict(o)
    raw = p.dict_raw(dd)
    n = raw[2] if raw else 0
    mi, mv = p.dget(dd, "model", None)
    fi, fv = p.dget(dd, "fix_process", None)
    进度 = 值(fv)
    行 = "0x%-12X %-6d %-8s " % (o, n, "读不出" if 进度 is None else "%.1f" % 进度)
    if not mv:
        print(行 + "没有 model 属性")
        continue
    p.fetch([mv], 0x40)
    结果 = []
    for off in (0x20, 0x28, 0x30):
        sp = p.q(mv + off)
        sp = (sp & MASK) if sp else 0
        if not sp:
            结果.append("+0x%X:空" % off)
        elif sp in senders:
            e = m.d(sp + 0x240)
            结果.append("+0x%X:0x%X(sender,+0x240=%s)" % (off, sp, e))
        elif sp in 全部:
            结果.append("+0x%X:0x%X(在数组里,类名=%s)" % (off, sp, (names.get(sp, "?") or "?")[-28:]))
        else:
            结果.append("+0x%X:0x%X(不在数组里)" % (off, sp))
    print(行 + ("0x%-14X " % mv) + "  ".join(结果))
