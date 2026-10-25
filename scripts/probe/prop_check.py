# -*- coding: utf-8 -*-
r"""按 +0x6D 的位分组列出全部 +0x240==2 的对象并带上类名。

用来验证"某个位能不能区分道具真假" —— 只看计数不够，必须看清每一组里到底是些什么东西。

    python prop_check.py                 全部
    python prop_check.py --only chr\prop 只看类名含该子串的
"""
import collections
import struct
import sys

sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem
from idv_probe import discover, dump_bss, find_sigs, class_names, read_objects, MASK

ONLY = sys.argv[sys.argv.index("--only") + 1].lower() if "--only" in sys.argv else None

pid, libbase, bss, maps = discover()
d = dump_bss(pid, bss, True)
head = find_sigs(d, bss[0], libbase)["array"][0]
m = Mem(pid)
m.quiet = True
r = read_objects(m, head)
objs = r["objs"]
names = class_names(m, objs)
print("数组 count=%d 类名读出=%d" % (r["count"], len(names)))

组 = collections.defaultdict(list)
无名 = collections.Counter()
for o in objs:
    b = m.get(o, 0x300)
    if b is None:
        continue
    if struct.unpack_from("<I", b, 0x240)[0] != 2:
        continue
    名 = names.get(o, "")
    if ONLY and ONLY not in 名.lower():
        continue
    if not 名:
        无名[b[0x6D]] += 1
        continue
    组[b[0x6D]].append((o, struct.unpack_from("<f", b, 0x1A0)[0], b[0x73], 名))

print("\n=== +0x240==2 的对象，按 +0x6D 分组%s ===" % (" (只看 %s)" % ONLY if ONLY else ""))
for k in sorted(set(list(组) + list(无名))):
    有40 = "带0x40" if (k & 0x40) else "**无0x40**"
    print("\n  +0x6D=0x%02X  %s   类名可读 %d 个，类名读不出 %d 个"
          % (k, 有40, len(组[k]), 无名[k]))
    for a, t, v, n in 组[k]:
        短 = n.split("\\")[-1] if "\\" in n else n
        print("     0x%-13X +0x1a0=%-9.4g +0x73=%d  %s" % (a, t, v, 短[:52]))
