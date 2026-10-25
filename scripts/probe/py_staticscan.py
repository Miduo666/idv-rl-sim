# -*- coding: utf-8 -*-
r"""扫静态段(bss/.so .data)里所有"指向 Python 对象"的指针，用来找 _PyRuntime / 解释器状态。

CPython 3.12 把主解释器内嵌在静态的 _PyRuntime 里，所以 interp->imports.modules
(sys.modules) 等字段本身就落在固定模块偏移上 —— 那正是叠加层能写死的根。

    python py_staticscan.py
"""
import sys, struct, collections
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap
from devread import Mem
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
DICT_T = 0x7A9A623BF0
LO, HI = 0x7300000000, 0x7F00000000

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


SO = None
for ln in maps:
    if "libclient.so" in ln:
        a, b = (int(x, 16) for x in ln.split()[0].split("-"))
        SO = (a, b) if SO is None else (min(SO[0], a), max(SO[1], b))


def in_static(va):
    return SO[0] <= va < SO[1] or bss[0] <= va < bss[1]


stat = [im for im in h.imgs if "static" in im.name]
print("扫描镜像: %s" % ", ".join(i.name for i in stat))

cands = []
for im in stat:
    blob = im.blob
    n = len(blob) // 8 * 8
    for o in range(0, n, 8):
        v = struct.unpack_from("<Q", blob, o)[0]
        va = v & MASK
        if not (LO < va < HI) or va & 7:
            continue
        sa = im.off2va(o)
        if sa is None or not in_static(sa):
            continue
        cands.append((sa, va))
print("静态段内指向堆区的对齐指针: %d 个" % len(cands))

kinds = collections.Counter()
found = collections.defaultdict(list)
for sa, va in cands:
    b = h.read(va, 16)
    if not b:
        continue
    rc, tp = struct.unpack_from("<QQ", b, 0)
    tp &= MASK
    if not (0 < rc < 1 << 34 and 0x700000000 < tp < 0x800000000000):
        continue
    nm = tpname(tp)
    if not nm:
        continue
    kinds[nm] += 1
    found[nm].append((sa, va))

print("\n=== 静态指针指向的对象类型分布 ===")
for nm, c in kinds.most_common(30):
    print("   %-28s %d 处" % (nm, c))

def dict_keys_sample(va, n=6):
    """取 dict 前几个字符串键，用来认出它是 sys.modules / builtins 之类"""
    b = h.read(va, 48)
    if not b:
        return ""
    K = struct.unpack_from("<Q", b, 0x20)[0] & MASK
    hdr = h.read(K, 32)
    if not hdr:
        return ""
    lg, idxb, kind = hdr[8], hdr[9], hdr[10]
    nent = struct.unpack_from("<q", hdr, 24)[0]
    ent0 = K + 32 + (1 << idxb)
    step = 24 if kind == 0 else 16
    out = []
    for i in range(min(nent, 400)):
        e = ent0 + i * step + (8 if step == 24 else 0)
        kb = h.read(e, 8)
        if not kb:
            break
        kp = struct.unpack("<Q", kb)[0] & MASK
        sb = h.read(kp, 0x30)
        if not sb:
            continue
        ln = struct.unpack_from("<q", sb, 0x10)[0]
        if not (0 < ln < 60):
            continue
        s = h.read(kp + 0x30, ln)
        if s:
            try:
                out.append(s.decode("ascii"))
            except Exception:
                pass
        if len(out) >= n:
            break
    return ", ".join(out)


print("\n=== 指向 dict 的静态指针 (按 ma_used 降序, 前 25) ===")
rows = []
for sa, va in found.get("dict", []):
    b = h.read(va, 24)
    rows.append((struct.unpack_from("<q", b, 16)[0] if b else 0, sa, va))
for used, sa, va in sorted(rows, reverse=True)[:25]:
    print("   静态 0x%X (libbase+0x%-9X) -> 0x%X ma_used=%-6d 键样本: %s"
          % (sa, sa - libbase, va, used, dict_keys_sample(va)))

print("\n=== 指向 module 的静态指针 ===")
for sa, va in found.get("module", []):
    b = h.read(va, 24)
    md = struct.unpack_from("<Q", b, 16)[0] & MASK if b else 0
    print("   静态 0x%X (libbase+0x%X) -> module 0x%X  md_dict=0x%X  键样本: %s"
          % (sa, sa - libbase, va, md, dict_keys_sample(md)))
