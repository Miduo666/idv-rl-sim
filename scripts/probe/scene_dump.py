# -*- coding: utf-8 -*-
# 列出场景数组全部对象：类名 + 关键字段。  python scene_dump.py [关键字过滤...]
import struct, sys
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem
from idv_probe import discover

M = 0x00FFFFFFFFFFFFFF
pid, libbase, bss, maps = discover()
m = Mem(pid)
def ok(x): return 0x5000000000 < x < 0x8000000000

HEAD = libbase + 0xB40A638
m.fetch([HEAD])
arr, end = m.q(HEAD) & M, m.q(HEAD + 8) & M
n = (end - arr) // 8
m.fetch(list(range(arr, end, 0x1000)) + [end])
objs = [m.q(arr + i * 8) & M for i in range(n)]
objs = [o for o in objs if ok(o)]

# 对象本体 0x300 字节
m.fetch(sum([[o, o + 0x100, o + 0x200] for o in objs], []))
def chain(o):
    p = o + 0xf8
    for off in (0, 0x0, 0x8, 0x20, 0x20):
        m.fetch([p + off]); p = m.q(p + off) & M if m.q(p + off) is not None else 0
        if not ok(p): return None
    return p
names = {}
for o in objs:
    c = chain(o)
    if not c: continue
    m.fetch([c]); sp, ln = m.q(c + 8), m.d(c + 0x10)
    if sp is None or ln is None or not (0 < ln < 256): continue
    sp &= M; m.fetch([sp]); m.fetch([sp + ln])
    b = m.get(sp, ln)
    if b: names[o] = b.decode("latin1", "replace")
coor = {}
for o in objs:
    cp = m.q(o + 0x28)
    if cp is not None and ok(cp & M): coor[o] = cp & M
m.fetch([c + 0xa0 for c in coor.values()])

flt = [a.lower() for a in sys.argv[1:]]
print("count=%d  类名读出=%d" % (len(objs), len(names)))
print("%-12s %-5s %-4s %-4s %-9s %-26s %s" % ("obj", "240", "6D", "73", "1a0", "坐标 X/高/Y", "类名"))
for i, o in enumerate(objs):
    nm = names.get(o, "?")
    if flt and not any(f in nm.lower() for f in flt): continue
    v240 = m.d(o + 0x240); b6d = m.get(o + 0x6D, 1); b73 = m.get(o + 0x73, 1)
    f1a0 = m.f(o + 0x1a0)
    xyz = "-"
    if o in coor:
        b = m.get(coor[o] + 0xa0, 12)
        if b: xyz = "%7.1f %6.1f %7.1f" % struct.unpack("<fff", b)
    print("%-12X %-5s %-4s %-4s %-9s %-26s %s" % (o, v240, b6d.hex() if b6d else "?", b73.hex() if b73 else "?",
          ("%.1f" % f1a0) if f1a0 is not None and abs(f1a0) < 1e6 else "垃圾", xyz, nm))
