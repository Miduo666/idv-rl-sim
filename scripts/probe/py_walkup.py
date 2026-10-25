# -*- coding: utf-8 -*-
r"""从 dict 槽位往上走: 槽位 -> PyDictKeysObject -> PyDictObject -> 实例 -> 类名。

CPython 3.11 布局:
  PyDictKeysObject: dk_refcnt(+0) dk_log2_size(+8,u8) dk_log2_index_bytes(+9,u8)
                    dk_kind(+10,u8) dk_version(+12,u32) dk_usable(+16) dk_nentries(+24)
                    dk_indices[](+32, 长度 1<<dk_log2_index_bytes) 之后才是 entries
  全 unicode 键时 entry 是 PyDictUnicodeEntry{key,value} 16 字节(不存 hash)
  PyDictObject:     ma_used(+16) ma_version_tag(+24) ma_keys(+32) ma_values(+40)

类型对象在 .so 里、不在堆快照中，所以 tp_name 走活体读。
"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap
from devread import Mem
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
TAG = 0xB4 << 56
SLOTS = [int(a, 16) for a in sys.argv[1:]] or [
    0x7D094D8730, 0x7D094E49E0, 0x7D0952A260,
    0x7D09536510, 0x7D09544390, 0x7D0957A1C0, 0x7D095A05A0]

h = Heap()
pid, libbase, bss, maps = discover()
m = Mem(pid)
m.quiet = True


def q(va):
    b = h.read(va, 8)
    return struct.unpack("<Q", b)[0] if b else None


def find_keys(slot):
    """从槽位往回找 PyDictKeysObject 头"""
    for back in range(0x20, 0x2000, 8):
        B = slot - back
        b = h.read(B, 32)
        if b is None:
            continue
        rc = struct.unpack_from("<q", b, 0)[0]
        lg, idxb, kind = b[8], b[9], b[10]
        usable, nent = struct.unpack_from("<qq", b, 16)
        if not (0 < rc < 1 << 20 and 3 <= lg <= 20 and lg <= idxb <= lg + 3):
            continue
        if not (0 <= nent <= (1 << lg) and 0 <= usable <= (1 << lg)):
            continue
        ent0 = B + 32 + (1 << idxb)
        if ent0 > slot:
            continue
        step = 16 if kind != 0 else 24        # 0=GENERAL(带hash,24字节)
        if (slot - ent0) % step:
            continue
        if (slot - ent0) // step >= max(nent, 1) + 2:
            continue
        return B, lg, idxb, kind, usable, nent, ent0, (slot - ent0) // step
    return None


def refs_to(va, limit=40):
    return h.findall(struct.pack("<Q", va | TAG), align=8, limit=limit) + \
           h.findall(struct.pack("<Q", va), align=8, limit=limit)


def tp_name(tp):
    """类型对象在 .so 里，活体读 tp_name (PyTypeObject +0x18 是 tp_name)"""
    m.fetch([tp, tp + 0x20], "")
    b = m.get(tp + 0x18, 8)
    if not b:
        return "?"
    p = struct.unpack("<Q", b)[0] & MASK
    if not p:
        return "?"
    m.fetch([p, p + 0x40], "")
    s = m.get(p, 64)
    if not s:
        return "?"
    return s.split(b"\0")[0].decode("utf-8", "replace")


for slot in SLOTS:
    print("=" * 78)
    val = q(slot + 8)
    vv = (val or 0) & MASK
    ob = h.read(vv, 24)
    desc = "?"
    if ob:
        tp = struct.unpack_from("<Q", ob, 8)[0] & MASK
        if tp == 0x7A9A6336F0:
            desc = "float %.4f" % struct.unpack_from("<d", ob, 16)[0]
        elif tp == 0x7A9A626498:
            sz = struct.unpack_from("<q", ob, 16)[0]
            dg = struct.unpack_from("<I", ob, 24)[0] if sz else 0
            desc = "int %d" % (dg if sz > 0 else 0)
    else:
        desc = "静态对象 0x%X" % vv
        if vv == 0x7A9ACF4380:
            desc += " (int 0)"
        elif vv == 0x7A9ACF5000:
            desc += " (int 100)"
    print("槽位 0x%X   fix_process = %s" % (slot, desc))

    k = find_keys(slot)
    if not k:
        print("   找不到 keys 对象头")
        continue
    K, lg, idxb, kind, usable, nent, ent0, ei = k
    print("   keys=0x%X log2size=%d idxbytes=%d kind=%d nentries=%d entry#%d"
          % (K, lg, idxb, kind, nent, ei))

    dicts = [r - 32 for r in refs_to(K) if q(r - 32) is not None]
    print("   指向 keys 的位置 %d 处 -> 候选 dict:" % len(dicts))
    for D in dicts[:6]:
        db = h.read(D, 48)
        if db is None:
            continue
        rc, tp = struct.unpack_from("<QQ", db, 0)
        used = struct.unpack_from("<q", db, 16)[0]
        if not (0 < rc < 1 << 30 and 0 <= used <= 1000):
            continue
        print("      dict=0x%X refcnt=%d ma_used=%d ob_type=0x%X" % (D, rc, used, tp & MASK))
        inst = refs_to(D, limit=12)
        for I in inst[:6]:
            for off in (0x10, 0x18, 0x20, 0x28, 0x30, 0x38, -0x8):
                base = I - off
                ib = h.read(base, 16)
                if ib is None:
                    continue
                irc, itp = struct.unpack_from("<QQ", ib, 0)
                itp &= MASK
                if not (0 < irc < 1 << 30) or itp < 0x700000000:
                    continue
                nm = tp_name(itp)
                if nm and nm != "?" and not nm.startswith("\\"):
                    print("         实例 0x%X (dict在+0x%X) 类型=0x%X tp_name=%s"
                          % (base, off, itp, nm))
                    break
