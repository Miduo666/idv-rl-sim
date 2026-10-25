# -*- coding: utf-8 -*-
r"""把某类单位的全部数值属性解出来，按值域筛。

用来找"不随时间变化、但取值有特征"的字段 —— 比如上次使用时刻(时间戳量级)、
冷却总长(配置常量)。这类字段 py_tick 的"找正在变的"抓不到，因为它们就是不变的。

    python py_valscan.py --type 1 [--lo 0 --hi 100] [--ts] [--near 18.3]

  --ts     只列时间戳量级(1.7e9~1.8e9)的
  --near X 只列接近 X 的(±2)
慢：要抓上千个散落的小对象，PC 侧一次 adb 往返 ~30ms，整轮 20~30 秒。
"""
import json
import os
import struct
import sys
import time

sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from pyw import Py
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
SYS_MODULES_OFF = 0xA7029E8
PYLONG_T_OFF = 0xA026498
PYFLOAT_T_OFF = 0xA0336F0
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_cache.json")


def arg(n, d):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


UTYPE = int(arg("--type", 1))
LO = float(arg("--lo", -1e18))
HI = float(arg("--hi", 1e18))
TS = "--ts" in sys.argv
NEAR = float(arg("--near", "nan"))

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
pid, libbase, bss, maps = discover()
LONG_T = libbase + PYLONG_T_OFF
FLOAT_T = libbase + PYFLOAT_T_OFF

p = Py(pid, libbase)
SM = p.qf(libbase + SYS_MODULES_OFF)
_, mod = p.dget(SM, "game_kernel", cache.get("mod"))
_, UM = p.dget(p.qf(mod + 0x10), "unit_mgr", cache.get("unit_mgr"))
_, UBT = p.dget(p.inst_dict(UM), "units_by_type", cache.get("units_by_type"))
if not UBT:
    sys.exit("拿不到 units_by_type，多半不在对局中")
lst = None
for _, nm, v in p.dict_pairs(UBT):
    if p.longval(nm) == UTYPE:
        lst = v
        break
if not lst:
    sys.exit("units_by_type 里没有键 %d" % UTYPE)

print("本机时间 %.3f" % time.time())
for o in p.list_items(lst):
    d = p.inst_dict(o)
    if not d:
        continue
    ent0, step, nent = p.dict_raw(d)     # entries 起始逐实例算
    if not ent0:
        continue
    值off = 8 if step == 16 else 16
    键off = 0 if step == 16 else 8
    t0 = time.time()
    p.fetch([ent0], nent * step)
    blk = p.get(ent0, nent * step)
    if not blk:
        print("单位 0x%X entries 读不到" % o)
        continue
    kp = {}
    vp = {}
    for i in range(nent):
        k = struct.unpack_from("<Q", blk, i * step + 键off)[0] & MASK
        v = struct.unpack_from("<Q", blk, i * step + 值off)[0] & MASK
        if 0x7000000000 < v < 0x8000000000:
            vp[i] = v
            kp[i] = k
    p.fetch(list(vp.values()), 0x20)
    出 = []
    for i, a in vp.items():
        b = p.get(a, 0x20)
        if not b or struct.unpack_from("<q", b, 0)[0] <= 0:
            continue
        tp = struct.unpack_from("<Q", b, 8)[0] & MASK
        if tp == FLOAT_T:
            val = struct.unpack_from("<d", b, 16)[0]
        elif tp == LONG_T:
            sz = struct.unpack_from("<q", b, 16)[0]
            val = 0.0 if sz == 0 else (
                float(struct.unpack_from("<I", b, 24)[0]) * (1 if sz > 0 else -1))
        else:
            continue
        if TS and not (1.7e9 < val < 1.8e9):
            continue
        if NEAR == NEAR and abs(val - NEAR) > 2:
            continue
        if not (LO <= val <= HI):
            continue
        出.append((i, val))
    print("\n单位 0x%X  %d 条属性, %d 条数值, 命中 %d 条  (%.1f 秒)"
          % (o, nent, len(vp), len(出), time.time() - t0))
    # 名字多半读不出来(字符串页常被换出)，能读出来就顺便打上
    p.fetch([kp[i] for i, _ in 出], 0x60)
    for i, val in 出:
        nm = p.pystr(kp[i]) or "(名字读不到)"
        print("   #%-5d %-30s %.4f" % (i, nm, val))
