# -*- coding: utf-8 -*-
r"""沿引用关系逐层往上爬，直到落进静态段(bss / libclient.so 的 .data)——那里才有固定偏移。

    python py_climb.py 0x7C5B70FDC0 --depth 6

每一跳会尝试认出"这个指针躺在什么对象里": list / tuple / dict / 实例 / 静态段。
静态命中会直接打印 libbase 相对偏移，那就是叠加层能写死的东西。
"""
import sys, struct, collections
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap
from devread import Mem
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
TAG = 0xB4 << 56
DEPTH = int(sys.argv[sys.argv.index("--depth") + 1]) if "--depth" in sys.argv else 5
MAXREF = int(sys.argv[sys.argv.index("--maxref") + 1]) if "--maxref" in sys.argv else 6
START = [int(a, 16) for a in sys.argv[1:] if a.startswith("0x")] or [0x7C5B70FDC0]

h = Heap()
pid, libbase, bss, maps = discover()
m = Mem(pid)
m.quiet = True

# 模块自身的映射范围(静态段判定用)
lo_so = hi_so = None
for ln in maps:
    if "libclient.so" in ln:
        a, b = (int(x, 16) for x in ln.split()[0].split("-"))
        lo_so = a if lo_so is None else min(lo_so, a)
        hi_so = b if hi_so is None else max(hi_so, b)
BSS = (bss[0], bss[1])
print("libbase=0x%X  so映射=0x%X-0x%X  bss=0x%X-0x%X\n" % (libbase, lo_so, hi_so, BSS[0], BSS[1]))


def rd(va, n):
    b = h.read(va, n)
    if b:
        return b
    m.fetch([va, va + n], "")
    return m.get(va, n)


def cstr(p, n=96):
    s = rd(p, n)
    return s.split(b"\0")[0].decode("utf-8", "replace") if s else "?"


def tpname(tp):
    b = rd(tp + 0x18, 8)
    if not b:
        return None
    p = struct.unpack("<Q", b)[0] & MASK
    if not (0x700000000 < p < 0x800000000000):
        return None
    s = cstr(p)
    return s if s and all(32 <= ord(c) < 127 for c in s[:24]) else None


def is_static(va):
    return (lo_so <= va < hi_so) or (BSS[0] <= va < BSS[1])


def identify(ref):
    """ref 是一个"存着目标指针的位置"，判断它躺在什么东西里"""
    if is_static(ref):
        return ("静态", ref, ref - libbase, None)
    # 往回找 PyObject 头
    for back in range(0, 0x60, 8):
        base = ref - back
        b = rd(base, 16)
        if not b:
            continue
        rc, tp = struct.unpack_from("<QQ", b, 0)
        tp &= MASK
        if not (0 < rc < 1 << 28 and 0x700000000 < tp < 0x800000000000):
            continue
        nm = tpname(tp)
        if nm:
            return (nm, base, back, tp)
    # managed dict preheader: 实例在后面 0x18
    b = rd(ref + 0x18, 16)
    if b:
        rc, tp = struct.unpack_from("<QQ", b, 0)
        tp &= MASK
        if 0 < rc < 1 << 28 and 0x700000000 < tp < 0x800000000000:
            nm = tpname(tp)
            if nm:
                return (nm + "(实例,preheader)", ref + 0x18, -0x18, tp)
    return (None, None, None, None)


seen = set()
frontier = [(a, "") for a in START]
hits = []
for d in range(DEPTH):
    nxt = []
    print("===== 第 %d 层 (%d 个节点) =====" % (d, len(frontier)))
    for va, path in frontier:
        if va in seen:
            continue
        seen.add(va)
        refs = h.findall(struct.pack("<Q", va | TAG), align=8, limit=60) + \
               h.findall(struct.pack("<Q", va), align=8, limit=60)
        refs = sorted(set(refs))
        st = [r for r in refs if is_static(r)]
        for r in st:
            hits.append((r, r - libbase, path + " <- 0x%X" % va))
            print("   ★ 静态命中 0x%X (libbase+0x%X)   路径 %s" % (r, r - libbase, path + " <- 0x%X" % va))
        show = [r for r in refs if not is_static(r)][:MAXREF]
        print("   0x%-14X 引用者 %d 处 (静态 %d)" % (va, len(refs), len(st)))
        for r in show:
            kind, base, off, tp = identify(r)
            if kind is None:
                continue
            print("      0x%X 在 %s 0x%X (+0x%X)" % (r, kind, base, off) if off is not None and off >= 0
                  else "      0x%X 在 %s 0x%X" % (r, kind, base))
            if base is not None and base not in seen:
                nxt.append((base, path + " <- 0x%X(%s)" % (base, kind)))
    frontier = nxt
    if not frontier:
        break

print("\n=== 静态命中汇总 %d 处 ===" % len(hits))
for r, off, path in hits:
    print("   0x%X  libbase+0x%X   %s" % (r, off, path))
