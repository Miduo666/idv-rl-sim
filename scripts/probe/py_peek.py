# -*- coding: utf-8 -*-
r"""看某个地址被谁引用，并把引用点周围的原始字节摊开，供人工判断。

    python py_peek.py 0x7C5B6EEAE0 [--ctx 0x60]
"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap
from devread import Mem
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
TAG = 0xB4 << 56
CTX = int(sys.argv[sys.argv.index("--ctx") + 1], 0) if "--ctx" in sys.argv else 0x60
TGT = [int(a, 16) for a in sys.argv[1:] if a.startswith("0x")]

h = Heap()
pid, libbase, bss, maps = discover()
m = Mem(pid)
m.quiet = True


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
    return s if s and s[:1].isalpha() else None


for t in TGT:
    refs = sorted(set(h.findall(struct.pack("<Q", t | TAG), align=8, limit=80) +
                      h.findall(struct.pack("<Q", t), align=8, limit=80)))
    print("=" * 76)
    print("0x%X 被 %d 处引用   所在镜像=%s" % (t, len(refs), h.region_of(t)))
    for r in refs:
        print("\n  引用点 0x%X  (libbase%+#x)  镜像=%s" % (r, r - libbase, h.region_of(r)))
        b = rd(r - CTX // 2, CTX)
        if not b:
            print("    读不到")
            continue
        for o in range(0, CTX, 8):
            v = struct.unpack_from("<Q", b, o)[0]
            va = v & MASK
            mark = ""
            if v == (t | TAG) or v == t:
                mark = "   <<< 目标"
            elif 0x700000000 < va < 0x800000000000:
                hdr = rd(va, 16)
                if hdr:
                    tp = struct.unpack_from("<Q", hdr, 8)[0] & MASK
                    nm = tpname(tp)
                    if nm:
                        mark = "   -> %s" % nm
            print("    %+#07x  %016x%s" % (o - CTX // 2, v, mark))
