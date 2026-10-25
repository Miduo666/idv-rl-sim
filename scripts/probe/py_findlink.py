# -*- coding: utf-8 -*-
r"""找 GeneratorUnit -> 场景对象 的直接链接，替掉不可靠的坐标配对。

    python py_findlink.py                # 自动挑一对坐标能配上的做样本

做法: 取一台坐标能配上的机器，扫它 dict 里全部属性的值；
      对每个值对象，再扫它前 0x400 字节里有没有出现那个场景对象的地址。
      命中的属性(+ 该对象内的偏移)就是一条可用的身份链。
顺便打印 position / visual_position / logic_position 三者，看哪个更靠谱。
"""
import sys, os, json, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem
from idv_probe import discover, dump_bss, find_sigs, class_names, read_objects, MASK
from pyw import Py

SYS_MODULES_OFF = 0xA7029E8
MODNAME = "game_kernel"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_cache.json")

pid, libbase, bss, maps = discover()
print("pid=%d libbase=0x%X" % (pid, libbase))

# ---- 场景侧: 所有 sender 对象及坐标 ----
d = dump_bss(pid, bss, True)
head = find_sigs(d, bss[0], libbase)["array"][0]
m = Mem(pid); m.quiet = True
r = read_objects(m, head)
names = class_names(m, r["objs"])
senders = [o for o in r["objs"] if "sender" in names.get(o, "").lower()]
m.fetch([(m.q(o + 0x28) & MASK) + k for o in senders if m.q(o + 0x28) for k in (0, 0xa0)], "")
场景 = {}
for o in senders:
    c = m.q(o + 0x28)
    cc = (c & MASK) if c else 0
    if not cc:
        continue
    x, z, y = (m.f(cc + 0xa0), m.f(cc + 0xa4), m.f(cc + 0xa8))
    if x is not None and y is not None:
        场景[o] = (x, y)
print("场景侧 sender 对象 %d 个" % len(场景))

# ---- Python 侧 ----
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
p = Py(pid, libbase)
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

d0 = p.inst_dict(items[0])
名表 = p.dict_names(d0)
序号 = {nm: i for i, nm, _ in 名表}
print("GeneratorUnit %d 台, 属性 %d 个\n" % (len(items), len(名表)))


def 读坐标(dd, 属性名):
    i = 序号.get(属性名)
    if i is None:
        return None
    _, pos = p.dict_entry(dd, i)
    if not pos:
        return None
    p.fetch([pos], 0x20)
    b = p.get(pos + 0x10, 12)
    return struct.unpack("<3f", b) if b else None


print("=== 三种坐标属性对比 ===")
单位 = []
for o in items:
    dd = p.inst_dict(o)
    a = 读坐标(dd, "position")
    b = 读坐标(dd, "visual_position")
    c = 读坐标(dd, "logic_position")
    单位.append((o, dd, a))
    f = lambda t: ("(%9.2f,%6.2f,%9.2f)" % t) if t else "无"
    print("   0x%-12X position=%s visual=%s logic=%s" % (o, f(a), f(b), f(c)))

# 挑一台坐标能配上的作样本
样本 = None
for o, dd, a in 单位:
    if not a or (a[0] == 0.0 and a[2] == 0.0):
        continue
    for so, (sx, sy) in 场景.items():
        if abs(sx - a[0]) + abs(sy - a[2]) < 1.0:
            样本 = (o, dd, so)
            break
    if 样本:
        break
if not 样本:
    sys.exit("\n没有坐标能配上的样本，换个时机再跑")

单位obj, 单位dict, 场景obj = 样本
print("\n=== 样本: GeneratorUnit 0x%X  <->  场景对象 0x%X ===" % (单位obj, 场景obj))
目标 = [struct.pack("<Q", 场景obj), struct.pack("<Q", 场景obj | 0xB4 << 56)]

pairs = p.dict_pairs(单位dict)
p.fetch([v for _, _, v in pairs], 0x40)
命中 = []
for i, k, v in pairs:
    nm = None
    for ii, nn, _ in 名表:
        if ii == i:
            nm = nn
            break
    if not v:
        continue
    if v == 场景obj:
        命中.append((i, nm, "属性值本身就是场景对象"))
        continue
    p.fetch([v], 0x400)
    b = p.get(v, 0x400)
    if not b:
        continue
    for pat in 目标:
        off = b.find(pat)
        while off != -1:
            if off % 8 == 0:
                命中.append((i, nm, "值对象 0x%X 的 +0x%X" % (v, off)))
            off = b.find(pat, off + 1)

print("\n=== 指向场景对象的属性 %d 处 ===" % len(命中))
for i, nm, where in 命中:
    print("   #%-4d %-34s %s" % (i, nm, where))
if not 命中:
    print("   无 —— 这台机器身上没有直接指向场景节点的属性，得换思路")
