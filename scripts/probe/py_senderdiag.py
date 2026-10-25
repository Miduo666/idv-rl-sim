# -*- coding: utf-8 -*-
r"""场景对象侧 与 Python 侧 的密码机对照诊断。

    python py_senderdiag.py [0x场景对象地址 ...]

回答"叠加层为什么还在画这台机器": 看它在场景侧的判据过不过、在 Python 侧能不能按坐标配上。
"""
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
关注 = [int(a, 16) for a in sys.argv[1:] if a.startswith("0x")]

pid, libbase, bss, maps = discover()
print("pid=%d libbase=0x%X\n" % (pid, libbase))

# ---------------- 场景对象侧 ----------------
d = dump_bss(pid, bss, True)
head = find_sigs(d, bss[0], libbase)["array"][0]
m = Mem(pid)
m.quiet = True
r = read_objects(m, head)
names = class_names(m, r["objs"])
senders = [o for o in r["objs"] if "sender" in names.get(o, "").lower()]
m.fetch([o + k for o in senders for k in (0, 0x100, 0x200, 0x240)], "")
m.fetch([(m.q(o + 0x28) & MASK) + k for o in senders if m.q(o + 0x28) for k in (0, 0xa0)], "")

print("=== 场景侧 类名含 sender 的对象 %d 个 ===" % len(senders))
print("%-16s %-8s %-8s %-10s %s" % ("对象", "+0x1a0", "+0x240", "是真实机", "坐标(X, 高, Y)"))
场景 = {}
for o in senders:
    f = m.f(o + 0x1a0)
    e = m.d(o + 0x240)
    c = m.q(o + 0x28)
    cc = (c & MASK) if c else 0
    xyz = [m.f(cc + 0xa0 + i * 4) for i in range(3)] if cc else [None] * 3
    真 = (f == 500.0 and e == 2)
    if 真 and all(v is not None for v in xyz):
        场景[o] = (xyz[0], xyz[2])
    mark = "  <<< 你问的" if o in 关注 else ""
    print("0x%-14X %-8s %-8s %-10s %s%s"
          % (o, ("%.1f" % f) if f is not None else "?", e, "是" if 真 else "否",
             ("(%9.2f,%6.2f,%9.2f)" % tuple(xyz)) if all(v is not None for v in xyz) else "读不出", mark))

for a in 关注:
    if a not in senders:
        print("\n!! 0x%X 不在 sender 列表里 —— 类名=%s" % (a, names.get(a, "<读不出>")))

# ---------------- Python 侧 ----------------
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
p = Py(pid, libbase)
LONG_T = libbase + PYLONG_T_OFF
FLOAT_T = libbase + PYFLOAT_T_OFF
SM = p.qf(libbase + SYS_MODULES_OFF)
mi, mod = p.dget(SM, MODNAME, cache.get("mod"))
md = p.qf(mod + 0x10)
ui, UM = p.dget(md, "unit_mgr", cache.get("unit_mgr"))
ud = p.inst_dict(UM)
bi, UBT = p.dget(ud, "units_by_type", cache.get("units_by_type"))
lst = None
for i, k, v in p.dict_pairs(UBT):
    if p.longval(k) == 3:
        lst = v
        break
items = p.list_items(lst)
p.fetch([o - 0x18 for o in items], 0x20)
d0 = p.inst_dict(items[0])
fi, _ = p.dget(d0, "fix_process", cache.get("t3.fix_process"))
pi, _ = p.dget(d0, "position", cache.get("position"))
ui2, _ = p.dget(d0, "uid", cache.get("uid"))
print("\n=== Python 侧 GeneratorUnit %d 个 (fix#%s position#%s) ===" % (len(items), fi, pi))


def val(vp):
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


py = []
for o in items:
    dd = p.inst_dict(o)
    _, vp = p.dict_entry(dd, fi)
    _, pos = p.dict_entry(dd, pi)
    _, uid = p.dict_entry(dd, ui2)
    p.fetch([pos], 0x20)
    pb = p.get(pos + 0x10, 12) if pos else None
    xyz = struct.unpack("<3f", pb) if pb else (0.0, 0.0, 0.0)
    v = val(vp)
    py.append((o, p.longval(uid) if uid else 0, xyz, v))
    print("   0x%-12X uid=%-8s (%9.2f,%6.2f,%9.2f)  fix_process=%s"
          % (o, p.longval(uid) if uid else "?", xyz[0], xyz[1], xyz[2],
             "读不出" if v is None else "%.4f" % v))

# ---------------- 配对 ----------------
print("\n=== 按坐标配对 (叠加层用的就是这个) ===")
for o, (sx, sy) in 场景.items():
    best, bd = None, 2.0
    for po, uid, xyz, v in py:
        if xyz[0] == 0.0 and xyz[2] == 0.0:
            continue
        dd = abs(xyz[0] - sx) + abs(xyz[2] - sy)
        if dd < bd:
            bd, best = dd, (uid, v)
    mark = "  <<< 你问的" if o in 关注 else ""
    if best:
        print("   场景 0x%-14X (%8.1f,%8.1f) -> uid=%d 进度=%s%s"
              % (o, sx, sy, best[0], "读不出" if best[1] is None else "%.1f" % best[1], mark))
    else:
        print("   场景 0x%-14X (%8.1f,%8.1f) -> **配不上**，所以既不显示进度也不会被隐藏%s"
              % (o, sx, sy, mark))
