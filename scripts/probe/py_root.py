# -*- coding: utf-8 -*-
r"""找静态根: (1) 认出几个候选 dict 的宿主实例类名; (2) 在静态镜像里搜指向给定对象的指针。

    python py_root.py
"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap
from devread import Mem
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
TAG = 0xB4 << 56

# 持有 'unit_mgr' 属性、但属性数偏少的 dict —— 不像单位，更像房间/世界
CAND = [0x7C58930F40, 0x7C5A15FE40, 0x7C5BE11390, 0x7C5B784DB0, 0x7C5BDF6130,
        0x7C5B9DC2C0, 0x7C5BA62460]
# 想在静态段里找的目标
WANT = {
    "UnitManager 实例": 0x7C5AE63A20,
    "UnitManager dict": 0x7C587C13D0,
    "units_by_type dict": 0x7C5BCA5380,
    "generator list": 0x7C5B6EEAE0,
    "GeneratorUnit 类型": 0x7CEA99D1A0,
    "模块 dict": 0x7C5B5118D0,
    "模块对象": 0x7BCAD7EA80,
}

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


print("=== 候选 dict 的宿主实例 ===")
for D in CAND:
    refs = sorted(set(h.findall(struct.pack("<Q", D | TAG), align=8, limit=8) +
                      h.findall(struct.pack("<Q", D), align=8, limit=8)))
    used = struct.unpack_from("<q", h.read(D, 24) or b"\0" * 24, 16)[0]
    shown = False
    for r in refs:
        inst = r + 0x18                       # managed-dict preheader
        b = h.read(inst, 16)
        if not b:
            continue
        rc, tp = struct.unpack_from("<QQ", b, 0)
        tp &= MASK
        nm = tpname(tp)
        if nm:
            print("   dict 0x%X (ma_used=%d) -> 实例 0x%X  类=%s" % (D, used, inst, nm))
            shown = True
            break
    if not shown:
        print("   dict 0x%X (ma_used=%d) -> 宿主没认出 (引用 %d 处)" % (D, used, len(refs)))

# ---- 静态镜像里的指针搜索 ----
stat = [im for im in h.imgs if "static" in im.name]
print("\n=== 静态镜像搜索 (%s) ===" % ", ".join(i.name for i in stat))
SO = None
for ln in maps:
    if "libclient.so" in ln:
        a, b = (int(x, 16) for x in ln.split()[0].split("-"))
        SO = (a, b) if SO is None else (min(SO[0], a), max(SO[1], b))
for name, va in WANT.items():
    hits = []
    for im in stat:
        for val in (va | TAG, va):
            pat = struct.pack("<Q", val)
            o = im.blob.find(pat)
            while o != -1:
                v2 = im.off2va(o)
                if v2 is not None and v2 % 8 == 0:
                    hits.append(v2)
                o = im.blob.find(pat, o + 1)
    hits = sorted(set(hits))
    inso = [x for x in hits if SO[0] <= x < SO[1] or bss[0] <= x < bss[1]]
    print("   %-20s 静态镜像内命中 %d 处, 其中在 so/bss 内 %d 处 %s"
          % (name, len(hits), len(inso), " ".join("0x%X(libbase+0x%X)" % (x, x - libbase) for x in inso[:6])))
