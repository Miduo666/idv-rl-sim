# -*- coding: utf-8 -*-
"""在 .text 里找 BL/B 到指定地址(通常是 PLT 跳板)的调用点。用法: blxref.py <so> <目标hex...>
环境变量 TEXT_OFF/TEXT_SIZE 同 xref.py（热更版 0x3b1c000 / 0x5f1daa0）。"""
import sys, os, struct
SO = sys.argv[1]
targets = set(int(x, 16) for x in sys.argv[2:])
TEXT_OFF = int(os.environ.get("TEXT_OFF", "0x3b1c000"), 16)
TEXT_SIZE = int(os.environ.get("TEXT_SIZE", "0x5f1daa0"), 16)
with open(SO, "rb") as f:
    f.seek(TEXT_OFF); data = f.read(TEXT_SIZE)
n = len(data) // 4
words = struct.unpack("<%dI" % n, data[:n * 4])
hits = {t: [] for t in targets}
for i in range(n):
    w = words[i]
    op = w & 0xFC000000
    if op == 0x94000000 or op == 0x14000000:      # BL / B
        imm = w & 0x03FFFFFF
        if imm & 0x02000000: imm -= 1 << 26
        pc = TEXT_OFF + i * 4
        tgt = pc + (imm << 2)
        if tgt in targets:
            hits[tgt].append((pc, "BL" if op == 0x94000000 else "B"))
for t, lst in hits.items():
    print("target 0x%X: %d call sites" % (t, len(lst)))
    for pc, k in lst[:40]:
        print("   %s at 0x%X" % (k, pc))
