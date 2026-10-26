# -*- coding: utf-8 -*-
"""查 .rela.dyn 里 R_AARCH64_RELATIVE 的目标：给定 VA 区间，打印每个 8 字节槽位重定位后的指针（vtable / 函数表用）。
用法: relaptr.py <so> <起始VA hex> [槽位数=16]"""
import sys, struct, bisect

SO = sys.argv[1]
start = int(sys.argv[2], 16)
cnt = int(sys.argv[3]) if len(sys.argv) > 3 else 16
d = open(SO, "rb").read()
# 解析节头，找 .rela.dyn
shoff, = struct.unpack_from("<Q", d, 0x28)
shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x3A)
secs = [struct.unpack_from("<IIQQQQIIQQ", d, shoff + i * shentsize) for i in range(shnum)]
strtab = secs[shstrndx]
name = lambda s: d[strtab[4] + s[0]: d.index(b"\0", strtab[4] + s[0])].decode()
rela = [s for s in secs if name(s) == ".rela.dyn"][0]
off, size = rela[4], rela[5]
rel = {}
for o in range(off, off + size, 24):
    r_off, r_info, r_add = struct.unpack_from("<QQq", d, o)
    if (r_info & 0xFFFFFFFF) == 1027 and start <= r_off < start + cnt * 8:  # R_AARCH64_RELATIVE
        rel[r_off] = r_add
for i in range(cnt):
    va = start + i * 8
    print("0x%X  ->  %s" % (va, ("0x%X" % rel[va]) if va in rel else "(无 RELATIVE)"))
