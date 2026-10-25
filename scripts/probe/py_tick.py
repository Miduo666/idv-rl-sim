# -*- coding: utf-8 -*-
r"""找"正在随时间变化"的属性：两阶段差分，不依赖键名。

键名页一旦换进 zram，py_chain 那套按名字查属性的路全断，但**值照样读得到**。
这个脚本不认名字，只看行为：谁在按秒递减，谁就是冷却。

为什么分两阶段 —— 直接把每条属性的值都解出来要抓上千个散落的小对象，
PC 侧一次 adb 往返 ~30ms，全扫一遍要 25 秒，慢到实例都换了。
但 dict 的 entries 是**一整块连续内存**(nentries × 16 字节)，一次就读完。
属性每被重新赋值一次就换一个新的值对象，所以：

  阶段一  只读 entries 块，比较两次的**值指针** -> 圈出正在被重新赋值的少数条目
  阶段二  只对这几条解值、再采一次算差值 -> 谁在按秒递减一目了然

    python py_tick.py --type 1 [--gap 3] [--top 40]
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
GAP = float(arg("--gap", 3))
TOP = int(arg("--top", 40))

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
pid, libbase, bss, maps = discover()
LONG_T = libbase + PYLONG_T_OFF
FLOAT_T = libbase + PYFLOAT_T_OFF


def 定位():
    """走到 units_by_type[UTYPE]，返回 [(单位地址, entries起始, 步长, 条数)]。"""
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
    出 = []
    for o in p.list_items(lst):
        d = p.inst_dict(o)
        if not d:
            continue
        ent0, step, nent = p.dict_raw(d)
        if ent0:
            # entries 起始必须逐实例算，不能套用别的实例(python-layer.md 四·1)
            出.append((o, ent0, step, nent))
    return 出


def 读指针(槽位):
    """一次读完整块 entries，取出全部值指针。"""
    o, ent0, step, nent = 槽位
    值off = 8 if step == 16 else 16
    p = Py(pid, libbase)                      # 新建以绕开读缓存
    p.fetch([ent0], nent * step)
    blk = p.get(ent0, nent * step)
    if not blk:
        return None
    出 = {}
    for i in range(nent):
        vp = struct.unpack_from("<Q", blk, i * step + 值off)[0] & MASK
        if 0x7000000000 < vp < 0x8000000000:
            出[i] = vp
    return 出


def 解值(p, vp):
    b = p.get(vp, 0x20)
    if not b or struct.unpack_from("<q", b, 0)[0] <= 0:   # refcount 非正 -> 不可信
        return None
    tp = struct.unpack_from("<Q", b, 8)[0] & MASK
    if tp == FLOAT_T:
        return struct.unpack_from("<d", b, 16)[0]
    if tp == LONG_T:
        sz = struct.unpack_from("<q", b, 16)[0]
        if sz == 0:
            return 0.0
        return float(struct.unpack_from("<I", b, 24)[0]) * (1 if sz > 0 else -1)
    return None


def 采值(槽位, 序号们):
    """只解指定序号的值，并做防竞态校验：读指针 -> 解值 -> 再读指针确认没变。"""
    o, ent0, step, nent = 槽位
    值off = 8 if step == 16 else 16
    p = Py(pid, libbase)
    槽 = [ent0 + i * step for i in 序号们]
    p.fetch([ent0], nent * step)
    指针 = {}
    for i, s in zip(序号们, 槽):
        b = p.get(s, step)
        if b:
            vp = struct.unpack_from("<Q", b, 值off)[0] & MASK
            if 0x7000000000 < vp < 0x8000000000:
                指针[i] = vp
    p.fetch(list(指针.values()), 0x20)
    值 = {}
    for i, vp in 指针.items():
        v = 解值(p, vp)
        if v is None:
            continue
        b2 = p.get(ent0 + i * step, step)                 # 复核指针没被改写
        if b2 and (struct.unpack_from("<Q", b2, 值off)[0] & MASK) == vp:
            值[i] = v
    return 值


槽位表 = 定位()
print("units_by_type[%d] -> %d 个单位" % (UTYPE, len(槽位表)))
for 槽位 in 槽位表:
    o, ent0, step, nent = 槽位
    print("\n单位 0x%X  entries=0x%X  %d 条  步长%d" % (o, ent0, nent, step))

    t0 = time.time()
    A = 读指针(槽位)
    t1 = time.time()
    if A is None:
        print("  entries 块读不到")
        continue
    print("  阶段一: 读 %d 条值指针, %.2f 秒" % (len(A), t1 - t0))
    time.sleep(GAP)
    B = 读指针(槽位)
    if B is None:
        print("  第二次读不到")
        continue
    动 = sorted(i for i in A if i in B and A[i] != B[i])
    print("  %.1f 秒内有 %d 条被重新赋值: %s"
          % (GAP, len(动), 动[:60] if 动 else "(无)"))
    if not 动:
        print("  没有正在变的属性 —— 回放可能是暂停的")
        continue

    ta = time.time()
    V1 = 采值(槽位, 动)
    时1 = (time.time() + ta) / 2
    time.sleep(GAP)
    tb = time.time()
    V2 = 采值(槽位, 动)
    时2 = (time.time() + tb) / 2
    隔 = 时2 - 时1
    print("  阶段二: 两次取值中点相距 %.2f 秒\n" % 隔)

    行 = []
    for i in 动:
        if i in V1 and i in V2:
            d = V2[i] - V1[i]
            行.append((abs(d + 隔), i, V1[i], V2[i], d))   # 越接近 -隔 排越前
    行.sort()
    print("  %-6s %14s %14s %10s %s" % ("序号", "先", "后", "差", "判断"))
    for _, i, a, b, d in 行[:TOP]:
        判 = ""
        if abs(d + 隔) < max(0.6, 隔 * 0.15):
            判 = "<<< 按秒递减，像冷却/计时"
        elif abs(d - 隔) < max(0.6, 隔 * 0.15):
            判 = "<<< 按秒递增，像时间戳"
        print("  #%-5d %14.4f %14.4f %+10.4f %s" % (i, a, b, d, 判))
