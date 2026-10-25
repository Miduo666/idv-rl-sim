# -*- coding: utf-8 -*-
"""列出类名匹配关键字的全部对象及其存在性字段。
用法: python yith_all.py yith ghost boss
"""
import sys, struct, collections
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem
from idv_probe import discover, dump_bss, find_sigs, class_names, read_objects, MASK

kws = [k.lower() for k in sys.argv[1:]] or ["yith"]

pid, libbase, bss, maps = discover()
d = dump_bss(pid, bss, True)
head = find_sigs(d, bss[0], libbase)["array"][0]
m = Mem(pid)
m.quiet = True
r = read_objects(m, head)
objs = r["objs"]
names = class_names(m, objs)
m.fetch([(m.q(o + 0x28) & MASK) + k for o in objs if m.q(o + 0x28) for k in (0, 0xa0)], "")
print("数组 count=%d 类名读出=%d\n" % (r["count"], len(names)))

hit = [o for o in objs if any(k in names.get(o, "").lower() for k in kws)]
print("=== 类名匹配 %s 的对象 %d 个 ===" % (kws, len(hit)))
for o in hit:
    b = m.get(o, 0x300)
    if b is None:
        print("   0x%X %s  <读不出>" % (o, names[o][:50]))
        continue
    c = m.q(o + 0x28)
    cc = (c & MASK) if c else 0
    xyz = [m.f(cc + 0xa0 + i * 4) for i in range(3)] if cc else [None] * 3
    print("   0x%X +0x240=%-4d +0x73=%d +0x6D=0x%02X +0x1a0=%-8.4g %s %s"
          % (o, struct.unpack_from("<I", b, 0x240)[0], b[0x73], b[0x6D],
             struct.unpack_from("<f", b, 0x1a0)[0],
             ("(%8.1f,%6.2f,%8.1f)" % tuple(xyz)) if all(v is not None for v in xyz) else "坐标N/A".ljust(26),
             names[o][:58]))

# 所有 +0x240==2 的对象里，按 +0x6D 归类
print("\n=== +0x240==2 的对象按 +0x6D 归类 ===")
c = collections.Counter()
for o in objs:
    b = m.get(o, 0x300)
    if b is None:
        continue
    if struct.unpack_from("<I", b, 0x240)[0] == 2:
        c[b[0x6D]] += 1
for k, v in sorted(c.items()):
    print("   +0x6D=0x%02X : %d 个" % (k, v))
