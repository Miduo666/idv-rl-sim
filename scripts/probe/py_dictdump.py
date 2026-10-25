# -*- coding: utf-8 -*-
r"""把一组同构实例 dict 的全部条目读出来，并按属性名过滤展示。

    python py_dictdump.py                 # 默认 7 台密码机的 dict
    python py_dictdump.py --names         # 只列出全部属性名
    python py_dictdump.py --grep pos uid  # 只看名字含这些子串的属性

用来回答两个问题: 每个属性在 entries 里的固定序号是多少; 哪个 dict 对应哪台机器。
"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap

MASK = 0x00FFFFFFFFFFFFFF
FLOAT_T = 0x7A9A6336F0
LONG_T = 0x7A9A626498
STR_T = 0x7A9A638140
INT0, INT100 = 0x7A9ACF4380, 0x7A9ACF5000

DICTS = [0x7C5B737010, 0x7C5B77DF10, 0x7C5B714B50, 0x7C5B79A430,
         0x7C5B70BC80, 0x7C5B6F85E0, 0x7C5B729E10]
GREP = []
if "--grep" in sys.argv:
    GREP = [a.lower() for a in sys.argv[sys.argv.index("--grep") + 1:] if not a.startswith("--")]

h = Heap()


def q(va):
    b = h.read(va, 8)
    return struct.unpack("<Q", b)[0] if b else None


def pystr(va):
    b = h.read(va, 0x30)
    if b is None:
        return None
    ln = struct.unpack_from("<q", b, 0x10)[0]
    if not (0 < ln < 200):
        return None
    s = h.read(va + 0x30, ln)
    return s.decode("utf-8", "replace") if s else None


def pyval(va):
    """把一个 PyObject 渲染成可读文本"""
    if va == INT0:
        return "0"
    if va == INT100:
        return "100"
    b = h.read(va, 32)
    if b is None:
        return "<0x%X 不在快照内>" % va
    tp = struct.unpack_from("<Q", b, 8)[0] & MASK
    if tp == FLOAT_T:
        return "%.4f" % struct.unpack_from("<d", b, 16)[0]
    if tp == LONG_T:
        sz = struct.unpack_from("<q", b, 16)[0]
        if sz == 0:
            return "0"
        d = struct.unpack_from("<I", b, 24)[0]
        return str(d if sz > 0 else -d)
    if tp == STR_T:
        return repr(pystr(va))
    return "<obj 0x%X type=0x%X>" % (va, tp)


def entries(D):
    K = q(D + 0x20)
    if K is None:
        return None, []
    K &= MASK
    hdr = h.read(K, 32)
    if hdr is None:
        return K, []
    lg, idxb, kind = hdr[8], hdr[9], hdr[10]
    nent = struct.unpack_from("<q", hdr, 24)[0]
    ent0 = K + 32 + (1 << idxb)
    step = 16 if kind != 0 else 24
    out = []
    for i in range(nent):
        e = ent0 + i * step
        kp = q(e if step == 16 else e + 8)
        vp = q((e + 8) if step == 16 else (e + 16))
        if kp is None:
            break
        out.append((i, (kp & MASK), (vp or 0) & MASK))
    return K, out


K0, ent0 = entries(DICTS[0])
names = {i: (pystr(kp) or "?") for i, kp, _ in ent0}
print("第一个 dict 0x%X 的 keys=0x%X, 共 %d 条\n" % (DICTS[0], K0, len(ent0)))

if "--names" in sys.argv:
    for i in sorted(names):
        print("   #%-4d %s" % (i, names[i]))
    sys.exit()

sel = [i for i in sorted(names)
       if (not GREP and names[i] in ("fix_process",)) or
       (GREP and any(g in names[i].lower() for g in GREP))]
if not sel:
    sel = [i for i in sorted(names) if "fix" in names[i].lower()]

print("选中属性: " + ", ".join("#%d %s" % (i, names[i]) for i in sel) + "\n")
for D in DICTS:
    K, ee = entries(D)
    vals = {i: v for i, _, v in ee}
    row = "  ".join("%s=%s" % (names[i], pyval(vals[i])) for i in sel if i in vals)
    print("dict 0x%X keys=0x%X  %s" % (D, K, row))
