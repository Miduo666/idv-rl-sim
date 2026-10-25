# -*- coding: utf-8 -*-
r"""解析一次链路，然后对同一批槽位连续采样 —— 用来分辨"真实变化"和"读到垃圾"。

    python py_watch.py --type 6 --attr hack_process --n 4
    python py_watch.py --type 3 --attr fix_process --n 6 --gap 2

每次采样都清掉页缓存重读，否则 devread 的 Mem 会把上一轮的页直接返回。
"""
import sys, os, json, time, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from idv_probe import discover
from pyw import Py, MASK

SYS_MODULES_OFF = 0xA7029E8
SMALLINT_OFF = 0xA6F42E0
PYLONG_T_OFF = 0xA026498
PYFLOAT_T_OFF = 0xA0336F0
MODNAME = "game_kernel"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_cache.json")


def arg(n, d):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


UTYPE = int(arg("--type", 6))
ATTR = arg("--attr", "hack_process")
N = int(arg("--n", 4))
GAP = float(arg("--gap", 0))
CK = "t%d.%s" % (UTYPE, ATTR)
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

pid, libbase, bss, maps = discover()
p = Py(pid, libbase)
LONG_T = libbase + PYLONG_T_OFF
FLOAT_T = libbase + PYFLOAT_T_OFF
INT0 = libbase + SMALLINT_OFF + 5 * 32

SM = p.qf(libbase + SYS_MODULES_OFF)
mi, mod = p.dget(SM, MODNAME, cache.get("mod"))
md = p.qf(mod + 0x10)
ui, UM = p.dget(md, "unit_mgr", cache.get("unit_mgr"))
ud = p.inst_dict(UM)
bi, UBT = p.dget(ud, "units_by_type", cache.get("units_by_type"))
lst = None
for i, k, v in p.dict_pairs(UBT):
    if p.longval(k) == UTYPE:
        lst = v
        break
items = p.list_items(lst)
p.fetch([o - 0x18 for o in items], 0x20)
d0 = p.inst_dict(items[0])
ai, _ = p.dget(d0, ATTR, cache.get(CK))
uidx, _ = p.dget(d0, "uid", cache.get("uid"))
ent0, step, nent = p.dict_raw(d0)
VOFF = (ent0 - p.qf(d0 + 0x20)) + ai * step + (8 if step == 16 else 16)
print("type=%d %s entry#%d  值指针 = ma_keys + 0x%X   单位 %d 个\n" % (UTYPE, ATTR, ai, VOFF, len(items)))

dicts = [p.inst_dict(o) for o in items]
uids = []
for d in dicts:
    _, u = p.dict_entry(d, uidx) if uidx is not None else (None, None)
    uids.append(p.longval(u) if u else 0)


def sample():
    p.m.cache.clear()                     # 必须清: 否则拿到的是上一轮的页
    # 槽位地址逐实例重算: 不同实例的 dict 形状可以不同，共用一个偏移会读错属性
    slots = [p.value_slot(d, ai) if d else None for d in dicts]
    p.fetch([s for s in slots if s], 16)
    vps = [p.q(s) if s else None for s in slots]
    p.fetch([v for v in vps if v], 0x20)
    out = []
    for vp in vps:
        if not vp or not (0x7000000000 < vp < 0x8000000000):
            out.append((vp, None, None))
            continue
        b = p.get(vp, 32)
        if not b:
            out.append((vp, None, None))
            continue
        tp = struct.unpack_from("<Q", b, 8)[0] & MASK
        rc = struct.unpack_from("<q", b, 0)[0]
        if tp == FLOAT_T:
            out.append((vp, struct.unpack_from("<d", b, 16)[0], "float rc=%d" % rc))
        elif tp == LONG_T:
            sz = struct.unpack_from("<q", b, 16)[0]
            out.append((vp, float(struct.unpack_from("<I", b, 24)[0]) if sz else 0.0,
                        "int rc=%d" % rc))
        else:
            out.append((vp, None, "type=0x%X" % tp))
    return out


for t in range(N):
    r = sample()
    print("采样 %d  %s" % (t + 1, time.strftime("%H:%M:%S")))
    for uid, (vp, val, kind) in zip(uids, r):
        print("   uid=%-8d 值对象=0x%-12X %-14s %s"
              % (uid, vp or 0, kind or "?", "读不出" if val is None else "%.4f" % val))
    if GAP and t < N - 1:
        time.sleep(GAP)

