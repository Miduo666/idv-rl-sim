# -*- coding: utf-8 -*-
r"""按 entry 序号直读某个单位的属性，**跳过 968 条键名全扫**。

py_chain 要按名字查属性，得把整张 dict 的键名读一遍；一旦有页换进 zram，
名字扫描就整体失败("这个类没有属性 X")，哪怕目标那一条其实读得到。
本脚本只算目标 entry 的槽位偏移直接取值，名字能读出来就顺便校验，读不出来不当错误。

    python py_entry.py --type 1 --idx 448,450,546 [--loop 6] [--gap 0.0]

值按 int / float / bool / None / list[int] / str 解；认不出就打印类型名和原始指针。
每次取值都做防竞态校验：读指针 -> 读对象 -> 再读一次指针确认没变。
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
PYDICT_T_OFF = 0xA023BF0
PYSTR_T_OFF = 0xA038140
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_cache.json")


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


UTYPE = int(arg("--type", 1))
IDXS = [int(x) for x in arg("--idx", "448,450,546").split(",")]
LOOP = int(arg("--loop", 1))
GAP = float(arg("--gap", 0.0))

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
pid, libbase, bss, maps = discover()
p = Py(pid, libbase)
LONG_T = libbase + PYLONG_T_OFF
FLOAT_T = libbase + PYFLOAT_T_OFF
STR_T = libbase + PYSTR_T_OFF
print("libbase=0x%X pid=%d type=%d idx=%s" % (libbase, pid, UTYPE, IDXS))

SM = p.qf(libbase + SYS_MODULES_OFF)
_, mod = p.dget(SM, "game_kernel", cache.get("mod"))
_, UM = p.dget(p.qf(mod + 0x10), "unit_mgr", cache.get("unit_mgr"))
_, UBT = p.dget(p.inst_dict(UM), "units_by_type", cache.get("units_by_type"))
if not UBT:
    sys.exit("拿不到 units_by_type，多半不在对局中")

lst = None
for i, nm, v in p.dict_pairs(UBT):
    if p.longval(nm) == UTYPE:
        lst = v
        break
if not lst:
    sys.exit("units_by_type 里没有键 %d" % UTYPE)
items = p.list_items(lst)
print("units_by_type[%d] -> %d 个单位\n" % (UTYPE, len(items)))


def tpname(tp):
    n = p.qf(tp + 0x18)
    if not n:
        return "?"
    p.fetch([n], 0x60)
    s = p.get(n, 64)
    return s.split(b"\0")[0].decode("utf-8", "replace") if s else "?"


def 解值(vp):
    """把值对象解成 python 值。读不到返回 ('读不到', None)。"""
    if not vp or not (0x7000000000 < vp < 0x8000000000):
        return "空指针", None
    p.fetch([vp], 0x40)
    b = p.get(vp, 0x28)
    if not b:
        return "读不到", None
    rc = struct.unpack_from("<q", b, 0)[0]
    tp = struct.unpack_from("<Q", b, 8)[0] & MASK
    if rc <= 0:                       # refcount 非正 -> 对象已废，值不可信
        return "refcount异常(%d)" % rc, None
    if tp == FLOAT_T:
        return "float", struct.unpack_from("<d", b, 16)[0]
    if tp == LONG_T:
        sz = struct.unpack_from("<q", b, 16)[0]
        if sz == 0:
            return "int", 0
        d = struct.unpack_from("<I", b, 24)[0]
        return "int", (d if sz > 0 else -d)
    if tp == STR_T:
        return "str", p.pystr(vp)
    名 = tpname(tp)
    if 名 == "list":
        vals = []
        for it in p.list_items(vp):
            _, v = 解值(it)
            vals.append(v)
        return "list", vals
    if 名 in ("bool", "NoneType"):
        return 名, None
    return 名, None


for 轮 in range(LOOP):
    t = time.time()
    for o in items:
        d = p.inst_dict(o)
        if not d:
            print("  单位 0x%X: 取不到实例 dict" % o)
            continue
        # entries 起始必须逐实例算(见 python-layer.md 第四节第 1 条)
        ent0, step, nent = p.dict_raw(d)
        if not ent0:
            print("  单位 0x%X: dict 头读不到" % o)
            continue
        print("  单位 0x%X  dict=0x%X  %d 条  step=%d" % (o, d, nent, step))
        for i in IDXS:
            if i >= nent:
                print("     #%-4d 越界(只有 %d 条)" % (i, nent))
                continue
            槽 = ent0 + i * step
            键off, 值off = (0, 8) if step == 16 else (8, 16)
            p.fetch([槽], step)
            b = p.get(槽, step)
            if not b:
                print("     #%-4d entry 读不到" % i)
                continue
            kp = struct.unpack_from("<Q", b, 键off)[0] & MASK
            vp = struct.unpack_from("<Q", b, 值off)[0] & MASK
            名 = p.pystr(kp) if kp else None
            类, 值 = 解值(vp)
            # 防竞态：解完再读一次指针，确认这期间没被重新赋值
            b2 = p.get(槽, step)
            vp2 = struct.unpack_from("<Q", b2, 值off)[0] & MASK if b2 else 0
            if vp2 != vp:
                类, 值 = "读取中被改写", None
            print("     #%-4d %-24s %-14s %s"
                  % (i, 名 or "(名字读不到)", 类,
                     "?" if 值 is None else repr(值)))
    print("  [%.3f 秒]\n" % (time.time() - t))
    if 轮 + 1 < LOOP and GAP:
        time.sleep(GAP)
