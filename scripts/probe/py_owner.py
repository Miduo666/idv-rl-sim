# -*- coding: utf-8 -*-
r"""给一个"存着指针的位置"，认出它躺在哪个 Python 对象里；可连续往上爬。

    python py_owner.py 0x7CB974DE78              # 单步
    python py_owner.py 0x7C5B70FDC0 --climb 8    # 连爬

认得: list/tuple 的元素数组、dict 的 entries(两种布局)、managed-dict 实例、静态段。
"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap
from devread import Mem
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
TAG = 0xB4 << 56
CLIMB = int(sys.argv[sys.argv.index("--climb") + 1]) if "--climb" in sys.argv else 1
SHOW = int(sys.argv[sys.argv.index("--show") + 1]) if "--show" in sys.argv else 8
START = [int(a, 16) for a in sys.argv[1:] if a.startswith("0x")]

h = Heap()
pid, libbase, bss, maps = discover()
m = Mem(pid)
m.quiet = True
SO = None
for ln in maps:
    if "libclient.so" in ln:
        a, b = (int(x, 16) for x in ln.split()[0].split("-"))
        SO = (a, b) if SO is None else (min(SO[0], a), max(SO[1], b))
BSS = (bss[0], bss[1])


def rd(va, n):
    b = h.read(va, n)
    if b:
        return b
    m.fetch([va, va + n], "")
    return m.get(va, n)


def cstr(p, n=96):
    s = rd(p, n)
    return s.split(b"\0")[0].decode("utf-8", "replace") if s else "?"


_TPCACHE = {}


def tpname(tp):
    """tp_name 指向 .so 的只读段，快照里没有，只能活体读 —— 所以必须缓存，
    否则 owner() 每试一个偏移就是一次 adb 往返。"""
    if tp in _TPCACHE:
        return _TPCACHE[tp]
    _TPCACHE[tp] = None
    b = rd(tp + 0x18, 8)
    if b:
        p = struct.unpack("<Q", b)[0] & MASK
        if 0x700000000 < p < 0x800000000000:
            s = cstr(p)
            if s and (s[0].isalpha() or s[0] == "_"):
                _TPCACHE[tp] = s
    return _TPCACHE[tp]


def obj_kind(va):
    b = h.read(va, 16)          # 只查快照: 这个函数在 owner() 里被密集调用
    if not b:
        return None
    rc, tp = struct.unpack_from("<QQ", b, 0)
    tp &= MASK
    if not (0 < rc < 1 << 28 and 0x700000000 < tp < 0x800000000000):
        return None
    return tpname(tp)


def static(va):
    return (SO[0] <= va < SO[1]) or (BSS[0] <= va < BSS[1])


_REG = []
for _ln in maps:
    _p = _ln.split()
    if _p and "-" in _p[0]:
        _a, _b = (int(x, 16) for x in _p[0].split("-"))
        _REG.append((_a, _b, _ln.split(None, 5)[5].strip() if len(_p) > 5 else "[anon]"))
_REG.sort()


def region_name(va):
    for a, b, nm in _REG:
        if a <= va < b:
            return (nm or "[anon]")[:34]
    return "?"


def find_keys(ref):
    """从一处 entries 内的地址往回找 PyDictKeysObject 头，返回 (keys, kind, step, 序号, nent, 字段位置)

    这里只查快照(h.read)、绝不退化成活体逐地址读 —— 回扫最多两千次，
    每次一个 adb 往返的话整个脚本会卡死几十分钟。
    """
    for back in range(0x20, 0x4000, 8):
        B = ref - back
        b = h.read(B, 32)
        if not b:
            continue
        rc = struct.unpack_from("<q", b, 0)[0]
        lg, idxb, kind = b[8], b[9], b[10]
        usable, nent = struct.unpack_from("<qq", b, 16)
        if not (0 < rc < 1 << 20 and 3 <= lg <= 22 and lg <= idxb <= lg + 3):
            continue
        if not (0 <= nent <= (1 << lg) + 8 and 0 <= usable <= (1 << lg) + 8):
            continue
        ent0 = B + 32 + (1 << idxb)
        if ent0 > ref:
            continue
        step = 24 if kind == 0 else 16
        # 指针可能落在 entry 的任意一个字段上(hash/key/value)，不一定是 entry 起始
        pos = (ref - ent0) % step
        if pos not in (0, 8, 16)[:step // 8]:
            continue
        i = (ref - ent0) // step
        if i > nent + 2:
            continue
        return B, kind, step, i, nent, pos
    return None


def owner(ref):
    """返回 (描述, 下一个要继续爬的对象地址)"""
    if static(ref):
        return ("★静态段 libbase+0x%X" % (ref - libbase), None)
    for off, kinds in ((0x18, ("list",)), (0x18, ("tuple",))):
        k = obj_kind(ref - off)
        if k in kinds:
            return ("%s 0x%X 的元素 (+0x%X)" % (k, ref - off, off), ref - off)
    k = obj_kind(ref - 0x18)
    if k:
        return ("%s 0x%X 的 +0x18 字段" % (k, ref - 0x18), ref - 0x18)
    fk = find_keys(ref)
    if fk:
        K, kind, step, i, nent, pos = fk
        field = {0: "hash" if step == 24 else "key", 8: "key" if step == 24 else "value", 16: "value"}[pos]
        keyobj = rd(ref - pos + (8 if step == 24 else 0), 8)
        kd = ""
        if keyobj:
            kp = struct.unpack("<Q", keyobj)[0] & MASK
            kb = rd(kp, 32)
            if kb:
                tp = struct.unpack_from("<Q", kb, 8)[0] & MASK
                nm = tpname(tp)
                if nm == "int":
                    sz = struct.unpack_from("<q", kb, 16)[0]
                    kd = " 键=int %d" % (struct.unpack_from("<I", kb, 24)[0] if sz else 0)
                elif nm == "str":
                    ln = struct.unpack_from("<q", kb, 16)[0]
                    s = rd(kp + 0x30, min(ln, 64)) if 0 < ln < 200 else None
                    kd = " 键='%s'" % s.decode("utf-8", "replace") if s else ""
        # 找持有这个 keys 的 dict (ma_keys 在 dict+0x20)
        dr = h.findall(struct.pack("<Q", K | TAG), align=8, limit=8) + \
             h.findall(struct.pack("<Q", K), align=8, limit=8)
        for r in dr:
            if obj_kind(r - 0x20) == "dict":
                return ("dict 0x%X 的 entry#%d/%d 的 %s%s (keys=0x%X kind=%d)"
                        % (r - 0x20, i, nent, field, kd, K, kind), r - 0x20)
        return ("keys 0x%X 的 entry#%d/%d 的 %s%s (没找到 dict)" % (K, i, nent, field, kd), None)
    k = obj_kind(ref + 0x18)
    if k:
        return ("%s 实例 0x%X 的 managed-dict preheader" % (k, ref + 0x18), ref + 0x18)
    for back in range(0, 0x80, 8):
        k = obj_kind(ref - back)
        if k:
            return ("%s 0x%X 的 +0x%X" % (k, ref - back, back), ref - back)
    return ("<认不出>", None)


cur = list(START)
for step in range(CLIMB):
    nxt = []
    for va in cur:
        refs = sorted(set(h.findall(struct.pack("<Q", va | TAG), align=8, limit=40) +
                          h.findall(struct.pack("<Q", va), align=8, limit=40)))
        print("\n[%d] 0x%X (%s)  被 %d 处引用" % (step, va, obj_kind(va) or "?", len(refs)))
        for r in refs[:SHOW]:
            desc, nx = owner(r)
            print("      0x%X [%s]  ->  %s" % (r, region_name(r), desc))
            if nx and nx not in nxt:
                nxt.append(nx)
    if not nxt:
        break
    cur = nxt[:4]
