# -*- coding: utf-8 -*-
r"""权威诊断: 对某类单位的某个属性，每轮都按名字全扫取值，并打印 dict 头。

    python py_attrdbg.py --type 6 --attr hack_process --n 3

重点看 ma_values: 非 0 说明是 split table，值在 values 数组里，
entries 的 value 字段不能用 —— 那正是"按槽位偏移读出垃圾"的典型原因。
"""
import sys, os, json, time, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from idv_probe import discover
from pyw import Py, MASK

SYS_MODULES_OFF = 0xA7029E8
PYLONG_T_OFF = 0xA026498
PYFLOAT_T_OFF = 0xA0336F0
MODNAME = "game_kernel"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_cache.json")


def arg(n, d):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


UTYPE = int(arg("--type", 6))
ATTR = arg("--attr", "hack_process")
N = int(arg("--n", 3))
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

pid, libbase, bss, maps = discover()
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
    if p.longval(k) == UTYPE:
        lst = v
        break
items = p.list_items(lst)
print("type=%d 单位 %d 个\n" % (UTYPE, len(items)))


def read_validated(slot, tries=5):
    """读值并校验: 解引用之后再读一次指针确认没变，且 refcount>0、类型是 int/float。

    属性如果每帧被重新赋值，旧的 float 会被释放并从 freelist 复用，
    "先读指针、下一次往返再解引用"就会读到已经变成别人的内存。
    """
    log = []
    for _ in range(tries):
        p.m.cache.clear()
        p.fetch([slot], 16)
        vp = p.q(slot)
        if not vp or not (0x7000000000 < vp < 0x8000000000):
            log.append("指针非法")
            continue
        p.m.cache.clear()
        p.fetch([slot, vp], 0x20)          # 同一批里同时拿"对象"和"指针的第二次读"
        vp2 = p.q(slot)
        b = p.get(vp, 32)
        if vp2 != vp:
            log.append("指针变了 0x%X->0x%X" % (vp, vp2))
            continue
        if not b:
            log.append("对象读不到")
            continue
        rc = struct.unpack_from("<q", b, 0)[0]
        tp = struct.unpack_from("<Q", b, 8)[0] & MASK
        if rc <= 0:
            log.append("rc=%d(已释放)" % rc)
            continue
        if tp == FLOAT_T:
            return "float %.4f (obj=0x%X rc=%d)" % (struct.unpack_from("<d", b, 16)[0], vp, rc), log
        if tp == LONG_T:
            sz = struct.unpack_from("<q", b, 16)[0]
            v = struct.unpack_from("<I", b, 24)[0] if sz else 0
            return "int %d (obj=0x%X rc=%d)" % (v, vp, rc), log
        log.append("类型不对 0x%X" % tp)
    return None, log


def show(vp):
    if not vp or not (0x7000000000 < vp < 0x8000000000):
        return "指针非法 0x%X" % (vp or 0)
    p.fetch([vp], 0x20)
    b = p.get(vp, 32)
    if not b:
        return "对象 0x%X 读不到" % vp
    rc = struct.unpack_from("<q", b, 0)[0]
    tp = struct.unpack_from("<Q", b, 8)[0] & MASK
    if tp == FLOAT_T:
        return "float %.4f (obj=0x%X rc=%d)" % (struct.unpack_from("<d", b, 16)[0], vp, rc)
    if tp == LONG_T:
        sz = struct.unpack_from("<q", b, 16)[0]
        v = struct.unpack_from("<I", b, 24)[0] if sz else 0
        return "int %d (obj=0x%X rc=%d)" % (v, vp, rc)
    return "其它类型 0x%X (obj=0x%X rc=%d)" % (tp, vp, rc)


for t in range(N):
    p.m.cache.clear()
    print("--- 第 %d 轮 %s ---" % (t + 1, time.strftime("%H:%M:%S")))
    for o in items:
        D = p.inst_dict(o)
        p.fetch([D], 0x40)
        hb = p.get(D, 48)
        used = struct.unpack_from("<q", hb, 0x10)[0]
        K = struct.unpack_from("<Q", hb, 0x20)[0] & MASK
        MV = struct.unpack_from("<Q", hb, 0x28)[0] & MASK
        p.fetch([K], 0x40)
        kh = p.get(K, 32)
        lg, idxb, kind = kh[8], kh[9], kh[10]
        nent = struct.unpack_from("<q", kh, 24)[0]
        print("  单位 0x%X  dict=0x%X ma_used=%d ma_keys=0x%X ma_values=0x%X"
              % (o, D, used, K, MV))
        print("      keys: log2size=%d idxbytes=%d kind=%d nentries=%d" % (lg, idxb, kind, nent))
        # 按名字全扫
        idx = val = None
        for i, nm, v in p.dict_names(D):
            if nm == ATTR:
                idx, val = i, v
                break
        print("      全扫: %s 在 entry#%s -> %s" % (ATTR, idx, show(val) if val else "没找到"))
        if idx is not None:
            ent0, step, _ = p.dict_raw(D)
            slot = ent0 + idx * step + (8 if step == 16 else 16)
            ok, log = read_validated(slot)
            print("      校验读: %s" % (ok or "失败"))
            if log:
                print("      (重试原因: %s)" % "; ".join(log))
        if MV and idx is not None:
            p.fetch([MV + idx * 8], 16)
            sv = p.q(MV + idx * 8)
            print("      split values[%d] -> %s" % (idx, show(sv)))
    print()

