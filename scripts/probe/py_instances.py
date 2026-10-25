# -*- coding: utf-8 -*-
r"""从"存 dict 指针的位置"定位 Python 实例，并解出它的类。

CPython 3.12 的 Py_TPFLAGS_MANAGED_DICT: dict 指针放在对象**前** 24 字节的 preheader 里，
所以 实例 = 引用者 + 0x18（早前往前找是错的方向）。

PyTypeObject 关键偏移(64位): tp_name +0x18, tp_basicsize +0x20, tp_itemsize +0x28,
                             tp_dictoffset +0x88, tp_flags +0xA8
"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap
from devread import Mem
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
REF = {1000007: 0x7C5B79CE08, 1000008: 0x7C5B75DC08, 1000009: 0x7C5B7C3DC8,
       1000010: 0x7C5B73AC58, 1000011: 0x7C5B7C6BB8, 1000012: 0x7C5B770FD8,
       1000013: 0x7C5B71E3C8}

h = Heap()
pid, libbase, bss, maps = discover()
m = Mem(pid)
m.quiet = True


def rd(va, n):
    """先查堆快照，缺的再走活体（类型对象在 .so 里，快照没覆盖）"""
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
        return "?"
    p = struct.unpack("<Q", b)[0] & MASK
    return cstr(p) if p else "?"


print("libbase = 0x%X\n" % libbase)
types = {}
for uid, r in sorted(REF.items()):
    obj = r + 0x18
    b = rd(obj, 16)
    if not b:
        print("uid=%d 实例读不到" % uid)
        continue
    rc, tp = struct.unpack_from("<QQ", b, 0)
    tp &= MASK
    types.setdefault(tp, []).append(uid)
    print("uid=%d  实例=0x%X  refcnt=%-4d ob_type=0x%X  tp_name=%s" % (uid, obj, rc, tp, tpname(tp)))

print("\n类型归并:")
for tp, us in types.items():
    print("   type=0x%X  tp_name=%s  实例 %d 个" % (tp, tpname(tp), len(us)))
    b = rd(tp, 0x100)
    if not b:
        continue
    basic, item = struct.unpack_from("<qq", b, 0x20)
    dictoff = struct.unpack_from("<q", b, 0x88)[0]
    flags = struct.unpack_from("<Q", b, 0xA8)[0]
    print("      tp_basicsize=%d tp_itemsize=%d tp_dictoffset=%d tp_flags=0x%X  MANAGED_DICT=%s"
          % (basic, item, dictoff, flags, bool(flags & (1 << 4))))
    mro = struct.unpack_from("<Q", b, 0xC0)[0] & MASK       # tp_mro
    tb = rd(mro, 16)
    if tb:
        n = struct.unpack_from("<q", tb, 8)[0] if False else None
    # 直接列 tp_bases/tp_mro 的元素
    for name, off in (("tp_base", 0xB8), ("tp_mro", 0xC0)):
        p = struct.unpack_from("<Q", b, off)[0] & MASK
        if not p:
            continue
        if name == "tp_base":
            print("      tp_base = 0x%X %s" % (p, tpname(p)))
        else:
            tb = rd(p, 16)
            cnt = struct.unpack_from("<q", tb, 16 - 8)[0] if tb else 0
            items = rd(p + 24, 8 * min(cnt, 12)) if 0 < cnt < 64 else None
            if items:
                names = []
                for i in range(len(items) // 8):
                    e = struct.unpack_from("<Q", items, i * 8)[0] & MASK
                    names.append(tpname(e))
                print("      tp_mro  = " + " -> ".join(names))
