# -*- coding: utf-8 -*-
"""按 Python 绑定的方法名找 C 实现：PyMethodDef = {const char* name; PyCFunction meth; int flags; const char* doc}，
name/meth 指针在 .rela.dyn 里是 R_AARCH64_RELATIVE。先找名字串的 VA，再找 addend==该 VA 的重定位槽，槽+8 的重定位就是函数。
用法: pymethods.py <so> <方法名>...   （.rodata 文件偏移 == VA）"""
import sys, struct, re

SO = sys.argv[1]
names = sys.argv[2:]
d = open(SO, "rb").read()
shoff, = struct.unpack_from("<Q", d, 0x28)
shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x3A)
secs = [struct.unpack_from("<IIQQQQIIQQ", d, shoff + i * shentsize) for i in range(shnum)]
strtab = secs[shstrndx]
sname = lambda s: d[strtab[4] + s[0]: d.index(b"\0", strtab[4] + s[0])].decode()
rela = [s for s in secs if sname(s) == ".rela.dyn"][0]
rod = [s for s in secs if sname(s) == ".rodata"][0]
rel = {}
by_add = {}
for o in range(rela[4], rela[4] + rela[5], 24):
    r_off, r_info, r_add = struct.unpack_from("<QQq", d, o)
    if (r_info & 0xFFFFFFFF) == 1027:
        rel[r_off] = r_add
        by_add.setdefault(r_add, []).append(r_off)
for n in names:
    pat = re.compile(b"(?<=\\x00)" + re.escape(n.encode()) + b"\\x00")
    for m in pat.finditer(d, rod[4], rod[4] + rod[5]):
        va = m.start()
        for slot in by_add.get(va, []):
            fn = rel.get(slot + 8)
            flags, = struct.unpack_from("<I", d, slot + 16 - (0x4000 if slot >= 0x9a7cf10 and slot < 0x9fc8390 else 0x8000)) if False else (0,)
            doc = rel.get(slot + 24)
            print("%-28s 名字 0x%X  槽 0x%X  函数 %s  doc %s" % (n, va, slot, ("0x%X" % fn) if fn else "-",
                                                             ("0x%X" % doc) if doc else "-"))
