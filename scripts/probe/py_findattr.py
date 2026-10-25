# -*- coding: utf-8 -*-
r"""按属性名反查: 找 interned 字符串对象 -> 找持有它的 dict 槽位 -> 认出宿主。

    python py_findattr.py g_unit
"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap
from devread import Mem
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
TAG = 0xB4 << 56
NAME = sys.argv[1] if len(sys.argv) > 1 else "g_unit"

h = Heap()
pid, libbase, bss, maps = discover()
m = Mem(pid)
m.quiet = True
_tp = {}


def rd(va, n):
    b = h.read(va, n)
    if b:
        return b
    m.fetch([va, va + n], "")
    return m.get(va, n)


def tpname(tp):
    if tp in _tp:
        return _tp[tp]
    _tp[tp] = None
    b = rd(tp + 0x18, 8)
    if b:
        p = struct.unpack("<Q", b)[0] & MASK
        if 0x700000000 < p < 0x800000000000:
            s = rd(p, 96)
            if s:
                s = s.split(b"\0")[0].decode("utf-8", "replace")
                if s and (s[0].isalpha() or s[0] == "_"):
                    _tp[tp] = s
    return _tp[tp]


# 1. interned 字符串对象
objs = []
for va in h.findall(NAME.encode() + b"\0", limit=400):
    b = h.read(va - 0x30, 0x30)
    if not b:
        continue
    rc, tp, ln, hsh = struct.unpack_from("<QQqQ", b, 0)
    state = struct.unpack_from("<I", b, 0x20)[0]
    if ln == len(NAME) and 0 < rc < 10 ** 9 and (state & 0x3F) == 0x25:
        objs.append(va - 0x30)
print("'%s' 的 interned 字符串对象: %s" % (NAME, [hex(o) for o in objs]))

for S in objs:
    refs = sorted(set(h.findall(struct.pack("<Q", S | TAG), align=8, limit=20000) +
                      h.findall(struct.pack("<Q", S), align=8, limit=20000)))
    print("\n0x%X 被 %d 处引用 (值是 str 的基本都是 code object 的 co_names，已跳过)" % (S, len(refs)))
    for r in refs:
        # 作为 unicode-entry 的 key，value 在 +8
        v = h.read(r + 8, 8)
        if not v:
            continue
        vp = struct.unpack("<Q", v)[0] & MASK
        vb = h.read(vp, 16) if vp else None
        vt = None
        if vb:
            t = struct.unpack_from("<Q", vb, 8)[0] & MASK
            vt = tpname(t)
        if vt in ("str", "NoneType", None, "code", "tuple"):
            continue
        # 往回找 keys 头，再找 dict，再找宿主实例
        info = ""
        for back in range(0x20, 0x4000, 8):
            B = r - back
            hd = h.read(B, 32)
            if not hd:
                continue
            dr = struct.unpack_from("<q", hd, 0)[0]
            lg, idxb, kind = hd[8], hd[9], hd[10]
            usable, nent = struct.unpack_from("<qq", hd, 16)
            if not (0 < dr < 1 << 20 and 3 <= lg <= 22 and lg <= idxb <= lg + 3):
                continue
            if not (0 <= nent <= (1 << lg) + 8):
                continue
            ent0 = B + 32 + (1 << idxb)
            step = 24 if kind == 0 else 16
            if ent0 > r or (r - ent0) % step:
                continue
            i = (r - ent0) // step
            if i > nent + 2:
                continue
            dd = h.findall(struct.pack("<Q", B | TAG), align=8, limit=6) + \
                 h.findall(struct.pack("<Q", B), align=8, limit=6)
            host = ""
            for x in dd:
                D = x - 0x20
                db = h.read(D, 16)
                if db and tpname(struct.unpack_from("<Q", db, 8)[0] & MASK) == "dict":
                    # 谁持有这个 dict
                    hr = h.findall(struct.pack("<Q", D | TAG), align=8, limit=6) + \
                         h.findall(struct.pack("<Q", D), align=8, limit=6)
                    for y in hr:
                        ib = h.read(y + 0x18, 16)
                        if ib:
                            t2 = struct.unpack_from("<Q", ib, 8)[0] & MASK
                            n2 = tpname(t2)
                            if n2:
                                host = " 宿主=%s 实例0x%X" % (n2, y + 0x18)
                                break
                        mb = h.read(y - 0x10, 16)
                        if mb and tpname(struct.unpack_from("<Q", mb, 8)[0] & MASK) == "module":
                            host = " 宿主=module 0x%X" % (y - 0x10)
                            break
                    info = " dict=0x%X entry#%d/%d%s" % (D, i, nent, host)
                    break
            if not info:
                info = " keys=0x%X entry#%d/%d" % (B, i, nent)
            break
        print("   0x%X  value=0x%X(%s)%s" % (r, vp, vt, info))
