# -*- coding: utf-8 -*-
"""在 .text 里找 MOVZ/MOVK 拼出的立即数常量(按寄存器跟踪，32/64 位)。
用法: movconst.py <so> <常量hex或4/8字符标签>...   环境变量 TEXT_OFF/TEXT_SIZE 同 xref.py"""
import sys, os, struct

SO = sys.argv[1]
targets = {}
for a in sys.argv[2:]:
    if a.startswith("0x"):
        targets[int(a, 16)] = a
    else:
        b = a.encode()
        targets[int.from_bytes(b, "little")] = a
TEXT_OFF = int(os.environ.get("TEXT_OFF", "0x3b1c000"), 16)
TEXT_SIZE = int(os.environ.get("TEXT_SIZE", "0x5f1daa0"), 16)
with open(SO, "rb") as f:
    f.seek(TEXT_OFF); data = f.read(TEXT_SIZE)
n = len(data) // 4
words = struct.unpack("<%dI" % n, data[:n * 4])
val = [None] * 32
for i in range(n):
    w = words[i]
    op = w & 0x7F800000
    if op in (0x52800000, 0x72800000):  # MOVZ / MOVK (sf 位在 bit31)
        sf = w >> 31; rd = w & 31; hw = (w >> 21) & 3; imm = (w >> 5) & 0xFFFF
        if op == 0x52800000:
            v = imm << (16 * hw)
        else:
            if val[rd] is None:
                continue
            v = (val[rd] & ~(0xFFFF << (16 * hw))) | (imm << (16 * hw))
        if not sf:
            v &= 0xFFFFFFFF
        val[rd] = v
        if v in targets:
            print("0x%08X  x%d = 0x%X  (%s)" % (TEXT_OFF + i * 4, rd, v, targets[v]))
    else:
        rd = w & 31
        val[rd] = None if rd != 31 else val[rd]
