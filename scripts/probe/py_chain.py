# -*- coding: utf-8 -*-
r"""从静态根走到某类单位的某个属性 —— 全程按名字查表，不写死堆地址。
这份脚本就是叠加层 C++ 端要实现的逻辑的原型。

    python py_chain.py                              # 密码机进度 (type 3, fix_process)
    python py_chain.py --type 6 --attr hack_process # 大门进度
    python py_chain.py --type 4 --attr state        # 狂欢之椅
    python py_chain.py --attrs                      # 顺带列出该类的全部属性名
    python py_chain.py --scan                       # 强制全表扫描(热更后重新确定序号)

静态根: *(libbase + 0xA7029E8) = sys.modules  (CPython 3.12 主解释器内嵌在静态 _PyRuntime)

为什么缓存 entry 序号: devread 每次 fetch 是 push+shell+pull 三次 adb 往返(~0.4s)。
挨个试模块的字典去找 unit_mgr 要几百次 fetch = 好几分钟；按序号直取再用名字校验只要十几次。
序号对不上会自动回退全扫，所以热更后不会给出错误结果，只是慢一次。
"""
import sys, os, json, time, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from idv_probe import discover
from pyw import Py, MASK

SYS_MODULES_OFF = 0xA7029E8
SMALLINT_OFF = 0xA6F42E0        # 小整数缓存基址(-5)，每个 32 字节
PYLONG_T_OFF = 0xA026498
PYFLOAT_T_OFF = 0xA0336F0
MODNAME = "game_kernel"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_cache.json")


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


UTYPE = int(arg("--type", 3))
ATTR = arg("--attr", "fix_process")
SCAN = "--scan" in sys.argv
SHOW_ATTRS = "--attrs" in sys.argv
CK = "t%d.%s" % (UTYPE, ATTR)          # 每种 (类型,属性) 一份序号缓存

cache = {}
if not SCAN and os.path.exists(CACHE):
    try:
        cache = json.load(open(CACHE))
    except Exception:
        cache = {}

t0 = time.time()
pid, libbase, bss, maps = discover()
p = Py(pid, libbase)
INT0 = libbase + SMALLINT_OFF + 5 * 32
LONG_T = libbase + PYLONG_T_OFF
FLOAT_T = libbase + PYFLOAT_T_OFF
print("libbase=0x%X pid=%d  type=%d attr=%s  (%s)"
      % (libbase, pid, UTYPE, ATTR, "全表扫描" if SCAN else "用缓存序号"))

SM = p.qf(libbase + SYS_MODULES_OFF)
mi, mod = p.dget(SM, MODNAME, cache.get("mod"))
if not mod:
    sys.exit("sys.modules 里没有 '%s'" % MODNAME)
md = p.qf(mod + 0x10)
ui, UM = p.dget(md, "unit_mgr", cache.get("unit_mgr"))
if not UM:
    sys.exit("模块里没有 unit_mgr")
ud = p.inst_dict(UM)
bi, UBT = p.dget(ud, "units_by_type", cache.get("units_by_type"))
if not UBT:
    sys.exit("UnitManager 里没有 units_by_type")
print("[链] sys.modules=0x%X -> %s#%d -> unit_mgr#%d=0x%X -> units_by_type#%d=0x%X"
      % (SM, MODNAME, mi, ui, UM, bi, UBT))

lst = None
for i, k, v in p.dict_pairs(UBT):
    if p.longval(k) == UTYPE:
        lst = v
        break
if not lst:
    sys.exit("units_by_type 里没有键 %d" % UTYPE)
items = p.list_items(lst)
print("[链] units_by_type[%d] = 0x%X   %d 个单位\n" % (UTYPE, lst, len(items)))
if not items:
    sys.exit("该类型本局没有单位")


def tpname(tp):
    n = p.qf(tp + 0x18)
    if not n:
        return "?"
    p.fetch([n], 0x60)
    s = p.get(n, 64)
    return s.split(b"\0")[0].decode("utf-8", "replace") if s else "?"


p.fetch([o - 0x18 for o in items] + [o for o in items], 0x20)
d0 = p.inst_dict(items[0])
print("类名 = %s" % tpname(p.qf(items[0] + 8)))

if SHOW_ATTRS:
    names = p.dict_names(d0)
    print("属性 %d 个:" % len(names))
    for i, nm, _ in names:
        print("   #%-4d %s" % (i, nm))

ai, _ = p.dget(d0, ATTR, cache.get(CK))
if ai is None:
    sys.exit("这个类没有属性 '%s'" % ATTR)
uidx, _ = p.dget(d0, "uid", cache.get("uid"))
posx, _ = p.dget(d0, "position", cache.get("position"))
ent0, step, nent = p.dict_raw(d0)
KEYS0 = p.qf(d0 + 0x20)
VOFF = (ent0 - KEYS0) + ai * step + (8 if step == 16 else 16)
print("%s 在 entry#%d/%d -> 值指针 = ma_keys + 0x%X   (uid#%s position#%s)\n"
      % (ATTR, ai, nent, VOFF, uidx, posx))


def decode(vp):
    """解成数值；读坏了返回 None 而不是 0。类型在 int/float 之间会变，两种都要认。"""
    if not vp or not (0x7000000000 < vp < 0x8000000000):
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


dicts = [p.inst_dict(o) for o in items]
p.fetch([d for d in dicts if d], 0x30)
keys = [p.q(d + 0x20) if d else None for d in dicts]
p.fetch([k + VOFF for k in keys if k], 16)
rows = []
for o, d, k in zip(items, dicts, keys):
    vp = p.q(k + VOFF) if k else None
    _, uid = p.dict_entry(d, uidx) if uidx is not None else (None, None)
    _, pos = p.dict_entry(d, posx) if posx is not None else (None, None)
    rows.append((o, vp, uid, pos))
p.fetch([r[3] for r in rows if r[3]], 0x20)

print("=== %s ===" % ATTR)
for o, vp, uid, pos in rows:
    val = decode(vp)
    pb = p.get(pos + 0x10, 12) if pos else None
    xyz = struct.unpack("<3f", pb) if pb else (0, 0, 0)
    txt = "读取失败" if val is None else ("%.4f" % val)
    raw = ""
    if vp:
        p.fetch([vp], 0x20)
        b = p.get(vp, 32)
        if b:
            raw = "  [值对象 0x%X ob_type=0x%X]" % (vp, struct.unpack_from("<Q", b, 8)[0] & MASK)
        else:
            raw = "  [值指针 0x%X 读不到]" % vp
    print("   0x%-12X uid=%-8s (%9.2f,%6.2f,%9.2f)  %s = %s%s"
          % (o, p.longval(uid) if uid else "?", xyz[0], xyz[1], xyz[2], ATTR, txt, raw))

GREP = arg("--grep", None)
if GREP:
    pats = [g.lower() for g in GREP.split(",")]
    names = p.dict_names(d0)
    sel = [(i, nm) for i, nm, _ in names if any(g in nm.lower() for g in pats)]
    print("\n=== 名字含 %s 的属性 (%d 个) ===" % (pats, len(sel)))
    for o, d in zip(items, dicts):
        print("   单位 0x%X:" % o)
        for i, nm in sel:
            _, v = p.dict_entry(d, i)
            dv = decode(v) if v else None
            if dv is not None:
                s = "%.4f" % dv
            elif v:
                p.fetch([v], 0x40)
                b = p.get(v, 16)
                tp = (struct.unpack_from("<Q", b, 8)[0] & MASK) if b else 0
                s = "<obj 0x%X type=%s>" % (v, tpname(tp) if tp else "?")
            else:
                s = "<空>"
            print("      #%-4d %-34s = %s" % (i, nm, s))

cache.update({"mod": mi, "unit_mgr": ui, "units_by_type": bi,
              "uid": uidx, "position": posx, CK: ai})
json.dump(cache, open(CACHE, "w"))
print("\n用时 %.1f 秒" % (time.time() - t0))

