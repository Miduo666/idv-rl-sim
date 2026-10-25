# -*- coding: utf-8 -*-
r"""调试 sys.modules 的读取"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem, PAGE
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
pid, libbase, bss, maps = discover()
m = Mem(pid)
m.quiet = False


def rd(va, n):
    pages = list(range(va // PAGE * PAGE, va + n + PAGE, PAGE))
    m.fetch(pages, "")
    return m.get(va, n)


SM = struct.unpack("<Q", rd(libbase + 0xA7029E8, 8))[0] & MASK
print("sys.modules = 0x%X" % SM)
b = rd(SM, 48)
print("dict 头:", b[:48].hex() if b else None)
rc, tp = struct.unpack_from("<QQ", b, 0)
used = struct.unpack_from("<q", b, 16)[0]
K = struct.unpack_from("<Q", b, 0x20)[0] & MASK
vals = struct.unpack_from("<Q", b, 0x28)[0] & MASK
print("refcnt=%d ob_type=0x%X ma_used=%d ma_keys=0x%X ma_values=0x%X"
      % (rc, tp & MASK, used, K, vals))
hdr = rd(K, 48)
print("keys 头:", hdr.hex() if hdr else None)
if hdr:
    dk_ref = struct.unpack_from("<q", hdr, 0)[0]
    lg, idxb, kind = hdr[8], hdr[9], hdr[10]
    usable, nent = struct.unpack_from("<qq", hdr, 16)
    print("dk_refcnt=%d log2size=%d idxbytes=%d kind=%d usable=%d nentries=%d"
          % (dk_ref, lg, idxb, kind, usable, nent))
    ent0 = K + 32 + (1 << idxb)
    step = 24 if kind == 0 else 16
    print("ent0=0x%X step=%d 需要读 %d 字节" % (ent0, step, nent * step))
    blob = rd(ent0, min(nent, 40) * step)
    print("读到 %s 字节" % (len(blob) if blob else None))
    if blob:
        for i in range(min(nent, 12)):
            o = i * step
            k = struct.unpack_from("<Q", blob, o + (8 if step == 24 else 0))[0] & MASK
            v = struct.unpack_from("<Q", blob, o + (16 if step == 24 else 8))[0] & MASK
            sb = rd(k, 0x30) if k else None
            nm = None
            if sb:
                ln = struct.unpack_from("<q", sb, 0x10)[0]
                if 0 < ln < 80:
                    s = rd(k + 0x30, ln)
                    nm = s.decode("ascii", "replace") if s else None
            print("   #%d key=0x%X val=0x%X name=%r" % (i, k, v, nm))
