# -*- coding: utf-8 -*-
"""找出"哪个字段能把真实存在的密码机和池子里的候选对象分开"""
import sys, os, struct, collections
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, SP)
from devread import Mem, sh
from idv_probe import discover, dump_bss, find_sigs, class_names, MASK, PTR_MIN, PTR_MAX

pid, libbase, bss, maps = discover()
d = dump_bss(pid, bss, False)
sigs = find_sigs(d, bss[0], libbase)
head = sigs["array"][0]

m = Mem(pid)
m.fetch([head, head + 8], "")
arr = m.q(head) & MASK
end = m.q(head + 8) & MASK
cnt = (end - arr) // 8
m.fetch([arr + i * 8 for i in range(cnt)], "")
objs = [m.q(arr + i * 8) & MASK for i in range(cnt)
        if m.q(arr + i * 8) and PTR_MIN < (m.q(arr + i * 8) & MASK) < PTR_MAX]
m.fetch([o + k for o in objs for k in (0, 0x100, 0x200)], "")
names = class_names(m, objs)
m.fetch([(m.q(o + 0x28) & MASK) + k for o in objs if m.q(o + 0x28) for k in (0, 0xa0)], "")

def coord(o):
    c = m.q(o + 0x28)
    if not c:
        return None
    cc = c & MASK
    v = [m.f(cc + 0xa0 + i * 4) for i in range(3)]
    return None if any(x is None for x in v) else v

groups = collections.defaultdict(list)
for o in objs:
    nm = names.get(o, "")
    if "sender" in nm:
        groups["sender"].append(o)
    elif "gallo" in nm:
        groups["gallows"].append(o)

for gname, lst in groups.items():
    print("\n================ %s : 共 %d 个对象 ================" % (gname, len(lst)))
    for o in lst:
        xyz = coord(o)
        print("  0x%X %s +0x70=%-10s +0x1a0=%-7s +0x298=%-7s +0xa8=%-11s +0x148=%-7s +0xaa=%s" % (
            o,
            ("(%8.1f,%6.2f,%8.1f)" % tuple(xyz)) if xyz else "坐标N/A            ",
            ("0x%X" % m.d(o + 0x70)) if m.d(o + 0x70) is not None else "N/A",
            ("%.0f" % m.f(o + 0x1a0)) if m.f(o + 0x1a0) is not None else "N/A",
            ("%.0f" % m.f(o + 0x298)) if m.f(o + 0x298) is not None else "N/A",
            ("0x%X" % m.d(o + 0xa8)) if m.d(o + 0xa8) is not None else "N/A",
            ("0x%X" % m.d(o + 0x148)) if m.d(o + 0x148) is not None else "N/A",
            ("0x%02X" % m.get(o + 0xaa, 1)[0]) if m.get(o + 0xaa, 1) else "N/A"))

    # 自动找能把这组切成 "少数真实的 vs 其余" 的字段
    print("\n  --- 能区分的字段(4字节对齐, 值分成2~3类) ---")
    data = {}
    for o in lst:
        b = m.get(o, 0x300)
        if b:
            data[o] = b
    if len(data) < 4:
        print("    可读样本不足")
        continue
    for off in range(0, 0x300 - 4, 4):
        vals = {o: struct.unpack_from("<I", b, off)[0] for o, b in data.items()}
        c = collections.Counter(vals.values())
        if 2 <= len(c) <= 3:
            parts = []
            for v, n in c.most_common():
                fv = struct.unpack("<f", struct.pack("<I", v))[0]
                parts.append("0x%X(f=%.0f)x%d" % (v, fv if -1e9 < fv < 1e9 else 0, n))
            print("    +0x%03X  %s" % (off, "  ".join(parts)))
