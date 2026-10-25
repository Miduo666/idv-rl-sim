# -*- coding: utf-8 -*-
r"""确认堆快照里那批对象在活体内存里还是同一批（对局没换、对象没被释放）。"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
LIST = 0x7C5B70FDC0
INST = [0x7C5B79CE20, 0x7C5B75DC20, 0x7C5B7C3DE0, 0x7C5B73AC70,
        0x7C5B7C6BD0, 0x7C5B770FF0, 0x7C5B71E3E0]
GENTYPE = 0x7CEA99D1A0
KEYS = {1000007: 0x7D0959F260, 1000008: 0x7D094D73F0, 1000009: 0x7D09528F20,
        1000010: 0x7D095351D0, 1000011: 0x7D094E36A0, 1000012: 0x7D09543050,
        1000013: 0x7D09578E80}

pid, libbase, bss, maps = discover()
m = Mem(pid)
m.quiet = True
print("pid=%d libbase=0x%X" % (pid, libbase))

m.fetch([LIST, LIST + 0x40], "")
b = m.get(LIST, 8 * 7)
ok = 0
if b:
    for i in range(7):
        v = struct.unpack_from("<Q", b, i * 8)[0] & MASK
        if v == INST[i]:
            ok += 1
print("列表 0x%X 仍指向原来的实例: %d/7" % (LIST, ok))

m.fetch([o + k for o in INST for k in (0, 16)], "")
good = 0
for o in INST:
    hb = m.get(o, 16)
    if hb and (struct.unpack_from("<Q", hb, 8)[0] & MASK) == GENTYPE:
        good += 1
print("实例 ob_type 仍是 GeneratorUnit: %d/7" % good)

print("\n当前 fix_process (直接用 keys + 0x1348):")
INT0, INT100 = 0x7A9ACF4380, 0x7A9ACF5000
m.fetch([k + 0x1348 for k in KEYS.values()], "")
for uid, K in sorted(KEYS.items()):
    vb = m.get(K + 0x1348, 8)
    if not vb:
        print("   uid=%d 读不到" % uid)
        continue
    v = struct.unpack("<Q", vb)[0] & MASK
    if v == INT0:
        s = "0"
    elif v == INT100:
        s = "100 (已破译)"
    else:
        m.fetch([v, v + 24], "")
        ob = m.get(v, 24)
        s = ("%.4f" % struct.unpack_from("<d", ob, 16)[0]) if ob else "对象 0x%X 读不到" % v
    print("   uid=%d  fix_process = %s" % (uid, s))
