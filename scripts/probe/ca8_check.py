# -*- coding: utf-8 -*-
# 2026-09-24：验证若辰矩阵链的第二跳 —— 根对象 +0xA58 与 +0xCA8 是否指向同一个矩阵对象。
# 用法: python ca8_check.py [轮数]   每轮清缓存重读，避免 devread 缓存造成"构造出来的相同"
import sys, struct
from idv_probe import discover, dump_bss, find_sigs, resolve_matrix, Mem, MASK, PTR_MIN, PTR_MAX

rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
pid, libbase, bss, maps = discover()
d = dump_bss(pid, bss, True)
sigs = find_sigs(d, bss[0], libbase)
m = Mem(pid)
roots = []
for sa in sigs.get("matrix", []):
    for off, root, mat in resolve_matrix(m, sa):
        roots.append((sa, off, root))
print("pid=%d libbase=0x%X 可用槽位 %d 个" % (pid, libbase, len(roots)))

ok = bad = 0
for r in range(rounds):
    for sa, off, root in roots:
        m.cache.clear()
        m.fetch([root + 0xa58, root + 0xca8], "")
        a = m.q(root + 0xa58); b = m.q(root + 0xca8)
        a = (a or 0) & MASK; b = (b or 0) & MASK
        same = a == b and PTR_MIN < a < PTR_MAX
        ok += same; bad += (not same)
        extra = ""
        if same:
            m.fetch([a + 0x2c0], "")
            row = [m.f(a + 0x2c0 + i * 4) for i in range(4)]
            extra = " Matrix首行=" + " ".join("%.3f" % x if x is not None else "?" for x in row)
        print("  轮%d 槽+0x%03X 根=0x%X  +0xA58=0x%X  +0xCA8=0x%X  %s%s" % (
            r, off, root, a, b, "相同" if same else "不同", extra))
print("\n相同 %d / 不同 %d" % (ok, bad))
