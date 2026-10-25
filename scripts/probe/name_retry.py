# -*- coding: utf-8 -*-
"""对指定对象反复重试读类名链，并报告卡在哪一跳。
类名读不出来几乎都是页不常驻(安全策略拒读)，多试几次 + 前台活跃通常能补齐。
用法: python name_retry.py            # 对当前所有 +0x1a0==450 的对象
      python name_retry.py 0x... 0x... # 指定对象
"""
import sys, os, time
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, SP)
from devread import Mem
from idv_probe import discover, dump_bss, find_sigs, MASK, PTR_MIN, PTR_MAX

HOPS = (0x0, 0x8, 0x20, 0x20)

def chain(m, o):
    """返回 (类名 or None, 失败在第几跳)"""
    v = m.q(o + 0xf8)
    if v is None:
        return None, 0
    for n, add in enumerate(HOPS):
        p = (v & MASK) + add
        m.fetch([p], "")
        v = m.q(p)
        if v is None:
            return None, n + 1
    p = v & MASK
    m.fetch([p, p + 0x18], "")
    s, L = m.q(p + 0x8), m.q(p + 0x10)
    if s is None or L is None:
        return None, 5
    L &= 0xFFFFFFFF
    if not (0 < L < 512):
        return None, 6
    m.fetch([(s & MASK), (s & MASK) + L], "")
    b = m.get(s & MASK, L)
    return (b.decode("utf-8", "replace") if b else None), (7 if not b else -1)

pid, libbase, bss, maps = discover()
d = dump_bss(pid, bss, False)
head = find_sigs(d, bss[0], libbase)["array"][0]

want = [int(a, 16) for a in sys.argv[1:]]
found = {}
for attempt in range(6):
    m = Mem(pid, refresh=(attempt == 0))
    m.quiet = True
    m.fetch([head, head + 8], "")
    arr = m.q(head) & MASK
    end = m.q(head + 8) & MASK
    cnt = (end - arr) // 8
    m.fetch([arr + i * 8 for i in range(cnt)], "")
    objs = [m.q(arr + i * 8) & MASK for i in range(cnt)
            if m.q(arr + i * 8) and PTR_MIN < (m.q(arr + i * 8) & MASK) < PTR_MAX]
    m.fetch([o + k for o in objs for k in (0, 0x100, 0x200)], "")

    targets = want if want else [o for o in objs if m.f(o + 0x1a0) == 450.0]
    m.fetch([(m.q(o + 0x28) & MASK) + k for o in targets if m.q(o + 0x28) for k in (0, 0xa0)], "")
    miss = 0
    for o in targets:
        if o in found:
            continue
        nm, fail = chain(m, o)
        if nm:
            c = m.q(o + 0x28)
            cc = (c & MASK) if c else 0
            xyz = [m.f(cc + 0xa0 + i * 4) for i in range(3)] if cc else [None] * 3
            p = m.q(o + 0x30)
            found[o] = (nm, xyz, bool(p and PTR_MIN < (p & MASK) < PTR_MAX),
                        m.d(o + 0x70), m.d(o + 0x1e0), m.d(o + 0x240))
        else:
            miss += 1
    print("第%d轮: 目标%d 已解出%d 仍缺%d" % (attempt + 1, len(targets), len(found), miss))
    if miss == 0:
        break
    time.sleep(2)

print("\n=== 结果 ===")
for o, (nm, xyz, has30, jx, e1, e2) in sorted(found.items(), key=lambda kv: kv[1][0]):
    print("  0x%X %s +0x30=%-5s +0x70=%-10s +0x1e0=%-3s +0x240=%-3s" % (
        o, ("(%8.1f,%6.2f,%8.1f)" % tuple(xyz)) if all(v is not None for v in xyz) else "坐标N/A            ",
        "有" if has30 else "NULL", ("0x%X" % jx) if jx is not None else "N/A", e1, e2))
    print("        %s" % nm)
