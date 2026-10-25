# -*- coding: utf-8 -*-
r"""按**名字**读某类单位的属性，一轮全部搞定。

为什么要单独写一个 —— entry 序号不能跨实例套用(同一个类的不同实例 dict 形状不同，
见 python-layer.md 四·1)，所以每次都得重新按名字定位；而 py_chain 的 --grep
是一条条解对象，964 条要 100 秒以上，冷却这种会走的量根本等不起。

这里把往返压到三次：
  1) 读 entries 整块(连续内存)拿到全部 键指针/值指针
  2) 批量预取全部键对象 -> 建 名字->序号 表
  3) 批量预取要的那几个值对象 -> 解值

    python py_named.py --type 1 --names last_flash_time,last_cd_delta
    python py_named.py --type 1 --grep flash,cd      # 按子串筛
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
PYSTR_T_OFF = 0xA038140
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_cache.json")


def arg(n, d):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


UTYPE = int(arg("--type", 1))
NAMES = [x for x in arg("--names", "").split(",") if x]
GREP = [x.lower() for x in arg("--grep", "").split(",") if x]
INTO = arg("--into", None)      # 先下钻到这个属性指向的实例，再在它的 dict 里查
TICK = "--tick" in sys.argv     # 采两次按**名字**比差值(序号会漂，名字不会)
GAP = float(arg("--gap", 4))

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
pid, libbase, bss, maps = discover()
LONG_T = libbase + PYLONG_T_OFF
FLOAT_T = libbase + PYFLOAT_T_OFF
STR_T = libbase + PYSTR_T_OFF

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


def 解值(vp, 深=0):
    b = p.get(vp, 0x28)
    if not b:
        return "读不到", None
    if struct.unpack_from("<q", b, 0)[0] <= 0:
        return "refcount异常", None
    tp = struct.unpack_from("<Q", b, 8)[0] & MASK
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
    n = p.qf(tp + 0x18)
    p.fetch([n], 0x40)
    s = p.get(n, 48)
    名 = s.split(b"\0")[0].decode("utf-8", "replace") if s else "?"
    if 名 == "list" and 深 < 2:
        its = p.list_items(vp)
        p.fetch(its, 0x20)
        return "list", [解值(x, 深 + 1)[1] for x in its]
    if 名 in ("set", "frozenset") and 深 < 2:
        return 名, 解集合(vp, 深)
    return 名, None


def 解集合(vp, 深=0):
    """CPython 3.11 PySetObject: +0x18 used, +0x20 mask, +0x28 table。
    表项是 setentry{key, hash} 共 16 字节，槽位数 = mask+1，空槽 key 为 NULL。
    小集合用内嵌的 smalltable(+0x40)，此时 table 指针就指向它，照读即可。"""
    p.fetch([vp], 0x40)
    h = p.get(vp, 0x30)
    if not h:
        return None
    used = struct.unpack_from("<q", h, 0x18)[0]
    mask = struct.unpack_from("<q", h, 0x20)[0]
    table = struct.unpack_from("<Q", h, 0x28)[0] & MASK
    if not (0 <= used <= 4096) or not (0 <= mask < (1 << 20)) or not table:
        return None
    槽数 = mask + 1
    p.fetch([table], 槽数 * 16)
    blk = p.get(table, 槽数 * 16)
    if not blk:
        return None
    键 = []
    for i in range(槽数):
        k = struct.unpack_from("<Q", blk, i * 16)[0] & MASK
        if 0x7000000000 < k < 0x8000000000:     # 跳过空槽 / dummy
            键.append(k)
        if len(键) >= used:
            break
    p.fetch(键, 0x40)                           # 元素对象散落在别处，必须批量预取
    出 = []
    for k in 键:
        类, 值 = 解值(k, 深 + 1)
        # 元素常常是实例对象而不是数字，那就把类型名打出来，别显示成 None
        出.append(值 if 值 is not None else "<%s 0x%X>" % (类, k))
    return 出


print("本机时间 %.3f   libbase=0x%X pid=%d" % (time.time(), libbase, pid))
def 键值表(d):
    """读一个 dict 的 entries 整块，返回 (名字表, 值指针表, 条数)。"""
    ent0, step, nent = p.dict_raw(d)        # entries 起始逐实例算
    if not ent0:
        return {}, {}, 0
    键off = 0 if step == 16 else 8
    值off = 8 if step == 16 else 16
    p.fetch([ent0], nent * step)
    blk = p.get(ent0, nent * step)
    if not blk:
        return {}, {}, 0
    kp, vp = {}, {}
    for i in range(nent):
        k = struct.unpack_from("<Q", blk, i * step + 键off)[0] & MASK
        v = struct.unpack_from("<Q", blk, i * step + 值off)[0] & MASK
        if 0x7000000000 < k < 0x8000000000:
            kp[i] = k
        if 0x7000000000 < v < 0x8000000000:
            vp[i] = v
    p.fetch(list(kp.values()), 0x60)        # 一次把所有键字符串抓回来
    名表 = {}
    for i, a in kp.items():
        s = p.pystr(a)
        if s:
            名表[i] = s
    return 名表, vp, nent


for o in p.list_items(lst):
    d = p.inst_dict(o)
    if not d:
        continue
    t0 = time.time()
    if INTO:
        名表0, vp0, _ = 键值表(d)
        目标 = [i for i, s in 名表0.items() if s == INTO]
        if not 目标:
            print("单位 0x%X 没有属性 '%s'" % (o, INTO))
            continue
        子 = vp0.get(目标[0])
        if not 子:
            print("单位 0x%X 的 '%s' 是空的" % (o, INTO))
            continue
        d = p.inst_dict(子)                 # 当成实例取它的 managed dict
        if not d:
            print("单位 0x%X 的 '%s'(0x%X) 取不到实例 dict" % (o, INTO, 子))
            continue
        print("\n下钻 %s -> 0x%X  dict=0x%X" % (INTO, 子, d))
    名表, vp, nent = 键值表(d)
    if not nent:
        print("单位 0x%X entries 读不到" % o)
        continue
    # 不给 --names / --grep 就列全部
    选 = [i for i, s in 名表.items()
         if (not NAMES and not GREP)
         or (s in NAMES) or (GREP and any(g in s.lower() for g in GREP))]
    选.sort()
    p.fetch([vp[i] for i in 选 if i in vp], 0x40)
    print("\n单位 0x%X  %d 条(名字认出 %d 条)  命中 %d 条  (%.1f 秒)"
          % (o, nent, len(名表), len(选), time.time() - t0))
    for i in 选:
        if i not in vp:
            print("   #%-5d %-30s <空>" % (i, 名表[i]))
            continue
        类, 值 = 解值(vp[i])
        print("   #%-5d %-30s %-8s %s"
              % (i, 名表[i], 类, "?" if 值 is None else repr(值)))
    漏 = [n for n in NAMES if n not in 名表.values()]
    if 漏:
        print("   没找到(名字没读出来或这个类没有): %s" % ", ".join(漏))
