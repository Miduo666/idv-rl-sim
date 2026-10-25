r"""离线比对两个版本 libclient.so 里 CPython 的静态数据: 验证"CPython 只平移不改"的先验。"""
import struct, sys, mmap

ROOT = r"C:\Users\31297\Desktop\逆向存档"
VERS = ["2026.0611.0155", "2026.0917_b6f53566"]
KNOWN_0917 = {  # 模块相对地址(= vaddr, 首个 LOAD 的 vaddr 为 0)
    "sys.modules槽": 0xA7029E8, "PyDict_Type": 0xA023BF0, "PyLong_Type": 0xA026498,
    "PyFloat_Type": 0xA0336F0, "True": 0xA0261A0, "False": 0xA0261C0,
}

class Elf:
    def __init__(s, path):
        s.f = open(path, "rb"); s.m = mmap.mmap(s.f.fileno(), 0, access=mmap.ACCESS_READ)
        m = s.m
        shoff, = struct.unpack_from("<Q", m, 0x28)
        shentsize, shnum, shstrndx = struct.unpack_from("<HHH", m, 0x3A)
        raw = [struct.unpack_from("<IIQQQQIIQQ", m, shoff + i * shentsize) for i in range(shnum)]
        stro = raw[shstrndx][4]
        s.sec = {}
        for r in raw:
            nm = m[stro + r[0]: m.find(b"\0", stro + r[0])].decode()
            s.sec[nm] = dict(type=r[1], addr=r[3], off=r[4], size=r[5])
        s.rel = {}   # R_AARCH64_RELATIVE: r_offset -> addend
        rd = s.sec[".rela.dyn"]
        for i in range(rd["size"] // 24):
            o, info, add = struct.unpack_from("<QQq", m, rd["off"] + i * 24)
            if info & 0xffffffff == 1027: s.rel[o] = add
    def secof(s, va):
        for n, x in s.sec.items():
            if x["addr"] and x["addr"] <= va < x["addr"] + x["size"]: return n
    def rd(s, va, n):
        x = s.sec[s.secof(va)]
        if x["type"] == 8: return b"\0" * n   # NOBITS
        o = va - x["addr"] + x["off"]; return s.m[o:o + n]
    def q(s, va): return s.rel.get(va, struct.unpack("<Q", s.rd(va, 8))[0])
    def cstrs(s, text):
        """.rodata 里所有精确等于 text 的 C 字符串地址"""
        ro = s.sec[".rodata"]; b = text.encode() + b"\0"; out = []; p = ro["off"]; end = p + ro["size"]
        while True:
            p = s.m.find(b, p, end)
            if p < 0: return out
            if s.m[p - 1] == 0: out.append(p - ro["off"] + ro["addr"])
            p += 1
    def types_named(s, name):
        """tp_name(+0x18) 指向 name、且 ob_type(+0x8) 有重定位的静态对象"""
        want = set(s.cstrs(name)); return [o - 0x18 for o, a in s.rel.items() if a in want and (o - 0x10) in s.rel]

res = {}
for v in VERS:
    e = Elf(rf"{ROOT}\{v}\binaries\libclient.so"); r = {}
    for nm in ("dict", "int", "float", "bool", "type", "str", "module"):
        c = e.types_named(nm)
        # 进一步: ob_type 指向 "type" 这个类型对象本身
        r[nm] = c
    tt = [t for t in r["type"] if e.rel.get(t + 8) == t]           # PyType_Type 的 ob_type 指向自己
    r["PyType_Type"] = tt
    for nm in ("dict", "int", "float", "bool", "str", "module"):
        r[nm] = [t for t in r[nm] if tt and e.rel.get(t + 8) == tt[0]]
    if r["bool"]:
        bt = r["bool"][0]
        r["bool对象"] = sorted(o - 8 for o, a in e.rel.items() if a == bt and e.secof(o) != ".data.rel.ro" or (a == bt and o - 8 not in r["bool"]))
    r["_e"] = e; res[v] = r
    print("==", v, " .PyRuntime=0x%X  .data=0x%X  .bss=0x%X" % (e.sec[".PyRuntime"]["addr"], e.sec[".data"]["addr"], e.sec[".bss"]["addr"]))
    for k in ("PyType_Type", "dict", "int", "float", "bool", "str", "module", "bool对象"):
        print("   %-12s" % k, ["0x%X(%s)" % (x, e.secof(x)) for x in r[k]])

o, n = res[VERS[0]], res[VERS[1]]
print("\n== 0917 已知值核对")
m = {"PyDict_Type": "dict", "PyLong_Type": "int", "PyFloat_Type": "float"}
for k, t in m.items(): print("  %-12s 已知0x%X  扫出%s" % (k, KNOWN_0917[k], ["0x%X" % x for x in n[t]]))
print("  True/False   已知0x%X/0x%X  bool对象%s" % (KNOWN_0917["True"], KNOWN_0917["False"], ["0x%X" % x for x in n["bool对象"]]))

print("\n== 两版平移量")
for k in ("PyType_Type", "dict", "int", "float", "bool", "str", "module"):
    if o[k] and n[k]: print("  %-12s 0x%X -> 0x%X  delta=+0x%X" % (k, o[k][0], n[k][0], n[k][0] - o[k][0]))
eo, en = o["_e"], n["_e"]
pro, prn = eo.sec[".PyRuntime"], en.sec[".PyRuntime"]
print("  .PyRuntime   0x%X -> 0x%X  delta=+0x%X  size %X/%X" % (pro["addr"], prn["addr"], prn["addr"] - pro["addr"], pro["size"], prn["size"]))
off = KNOWN_0917["sys.modules槽"] - prn["addr"]
print("  sys.modules槽 在 .PyRuntime 内 +0x%X -> 0611 预测 0x%X" % (off, pro["addr"] + off))

# .PyRuntime 内容逐 qword 比对: 非重定位的原值必须相同; 重定位的按"目标在哪个段 + 段内偏移"比较
same = diff = 0; bad = []
for i in range(0, pro["size"], 8):
    a, b = pro["addr"] + i, prn["addr"] + i
    ra, rb = eo.rel.get(a), en.rel.get(b)
    if ra is None and rb is None:
        ok = eo.rd(a, 8) == en.rd(b, 8)
    elif ra is not None and rb is not None:
        sa, sb = eo.secof(ra), en.secof(rb)
        ok = sa == sb and (ra - eo.sec[sa]["addr"] if sa != ".PyRuntime" else ra - pro["addr"]) == \
             (rb - en.sec[sb]["addr"] if sb != ".PyRuntime" else rb - prn["addr"]) if sa in (".PyRuntime",) else sa == sb
    else:
        ok = False
    if ok: same += 1
    else:
        diff += 1
        if len(bad) < 12: bad.append((i, ra, rb, eo.rd(a, 8).hex(), en.rd(b, 8).hex()))
print("\n== .PyRuntime 内容比对: 相同 %d / 不同 %d" % (same, diff))
for i, ra, rb, x, y in bad:
    print("   +0x%05X  rel %s / %s   raw %s / %s" % (i, ra and hex(ra), rb and hex(rb), x, y))
# 重定位目标里指向 .data/.bss 的，看段内偏移平移是否一致(CPython 静态数据块整体平移的证据)
ds = {}
for i in range(0, pro["size"], 8):
    ra, rb = eo.rel.get(pro["addr"] + i), en.rel.get(prn["addr"] + i)
    if ra and rb: ds.setdefault((eo.secof(ra), en.secof(rb)), {}).setdefault(rb - ra, 0); ds[(eo.secof(ra), en.secof(rb))][rb - ra] += 1
print("\n== .PyRuntime 里指针的平移量分布 (段, {delta: 次数})")
for k, v in ds.items(): print("  ", k, {hex(d): c for d, c in sorted(v.items(), key=lambda t: -t[1])[:6]})
