# -*- coding: utf-8 -*-
"""验证候选判据在多次采样下是否稳定给出 7 台密码机"""
import sys, os, time, struct
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, SP)
from devread import Mem
from idv_probe import discover, dump_bss, find_sigs, class_names, MASK, PTR_MIN, PTR_MAX

pid, libbase, bss, maps = discover()
d = dump_bss(pid, bss, False)
head = find_sigs(d, bss[0], libbase)["array"][0]

for t in range(4):
    m = Mem(pid, refresh=(t == 0))
    m.quiet = True
    m.fetch([head, head + 8], "")
    arr = m.q(head) & MASK
    end = m.q(head + 8) & MASK
    cnt = (end - arr) // 8
    m.fetch([arr + i * 8 for i in range(cnt)], "")
    objs = [m.q(arr + i * 8) & MASK for i in range(cnt)
            if m.q(arr + i * 8) and PTR_MIN < (m.q(arr + i * 8) & MASK) < PTR_MAX]
    m.fetch([o + k for o in objs for k in (0, 0x100, 0x200)], "")
    names = class_names(m, objs)
    senders = [o for o in objs if "sender" in names.get(o, "")]
    m.fetch([(m.q(o + 0x28) & MASK) + k for o in senders if m.q(o + 0x28) for k in (0, 0xa0)], "")

    def ok30(o):
        p = m.q(o + 0x30)
        return p is not None and PTR_MIN < (p & MASK) < PTR_MAX

    def f1a0(o):
        return m.f(o + 0x1a0) == 500.0

    def d1e0(o):
        return m.d(o + 0x1e0) == 1

    def d240(o):
        return m.d(o + 0x240) == 2

    crit = {
        "旧: +0x1a0==500": [o for o in senders if f1a0(o)],
        "A: +0x30 非空": [o for o in senders if ok30(o)],
        "B: +0x30 非空 且 +0x1a0==500": [o for o in senders if ok30(o) and f1a0(o)],
        "C: +0x1e0==1": [o for o in senders if d1e0(o)],
        "D: +0x240==2": [o for o in senders if d240(o)],
        "E: +0x1e0==1 且 +0x240==2": [o for o in senders if d1e0(o) and d240(o)],
    }
    print("\n--- 采样%d: sender对象 %d 个 ---" % (t + 1, len(senders)))
    for k, v in crit.items():
        print("   %-32s -> %d 个 %s" % (k, len(v), "✓" if len(v) == 7 else "✗"))
    if t == 0:
        print("\n   逐个明细:")
        for o in senders:
            c = m.q(o + 0x28)
            cc = (c & MASK) if c else 0
            xyz = [m.f(cc + 0xa0 + i * 4) for i in range(3)] if cc else [None] * 3
            p30 = m.q(o + 0x30)
            print("     0x%X %s +0x30=%-14s +0x70=%-10s +0x1a0=%-8s +0x1e0=%-4s +0x240=%s" % (
                o, ("(%8.1f,%6.2f,%8.1f)" % tuple(xyz)) if all(v is not None for v in xyz) else "坐标N/A            ",
                ("0x%X" % (p30 & MASK)) if p30 else "NULL",
                ("0x%X" % m.d(o + 0x70)) if m.d(o + 0x70) is not None else "N/A",
                ("%.4g" % m.f(o + 0x1a0)) if m.f(o + 0x1a0) is not None else "N/A",
                m.d(o + 0x1e0), m.d(o + 0x240)))
    time.sleep(3)
