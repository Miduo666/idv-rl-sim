# -*- coding: utf-8 -*-
# 自动盖板上机核对：列出所有 woodplane 板子 + 监管的「状态/动作号」和朝向字段。
#   python pallet_probe.py            # 一次快照
#   python pallet_probe.py 5          # 每 1 秒一次，共 5 次(观察放板前后状态变化)
#
# 要核对的(全部来自若辰 10.1.74 反汇编，2026-09-26，见 skill auto-pallet.md 若辰一节)：
#   状态 = u32 [[obj+0x750]+0x30]   板子立着 == 16，放下后应变成别的值
#   朝向 = objcoor+0xb8 / +0xc0      若辰用它当板子水平方向(判定矩形沿它的长度 ±8.63 单位)
#   监管动作号同样是 [[obj+0x750]+0x30]，小丑拉锯 ≈ 0x1802CE(1573582)
# 顺带打印旧版「帝五」用的 +0x730 那条和旋转矩阵三行，方便对照。
import struct, sys, time
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem
from idv_probe import discover

M = 0x00FFFFFFFFFFFFFF
def ok(x): return x is not None and 0x5000000000 < x < 0x8000000000

pid, libbase, bss, maps = discover()
HEAD = libbase + 0xB40A638

def snapshot(m):
    m.cache.clear()
    m.fetch([HEAD])
    arr, end = m.q(HEAD) & M, m.q(HEAD + 8) & M
    n = (end - arr) // 8
    m.fetch(list(range(arr, end, 0x1000)) + [end])
    objs = [m.q(arr + i * 8) & M for i in range(n)]
    objs = [o for o in objs if ok(o)]
    m.fetch(sum([[o, o + 0x100, o + 0x200, o + 0x700] for o in objs], []))

    def chain(o):
        p = o + 0xf8
        for off in (0, 0x0, 0x8, 0x20, 0x20):
            m.fetch([p + off]); v = m.q(p + off)
            p = (v & M) if v is not None else 0
            if not ok(p): return None
        return p
    rows = []
    for o in objs:
        c = chain(o)
        if not c: continue
        m.fetch([c]); sp, ln = m.q(c + 8), m.d(c + 0x10)
        if sp is None or ln is None or not (0 < ln < 256): continue
        sp &= M; m.fetch([sp]); m.fetch([sp + ln])
        b = m.get(sp, ln)
        if not b: continue
        nm = b.decode("latin1", "replace")
        low = nm.lower()
        if "woodplane" in low or ("boss" in low and m.f(o + 0x1a0) == 450.0):
            rows.append((o, nm))
    return rows

def comp(m, o, off):
    p = m.q(o + off)
    if not ok(p & M if p is not None else None): return None
    p &= M
    m.fetch([p + 0x30])
    return m.d(p + 0x30)

def show(m, rows):
    print("%-12s %-7s %-10s %-10s %-24s %-18s %-40s %s" % ("obj", "240", "状态750", "状态730", "坐标 X/高/Y", "朝向b8/c0", "旋转 X行x,z / Z行x,z", "类名"))
    for o, nm in rows:
        m.fetch([o + 0x28, o + 0x240, o + 0x730, o + 0x750])
        cp = m.q(o + 0x28)
        xyz = dirs = rot = "-"
        if ok(cp & M if cp is not None else None):
            cp &= M
            m.fetch([cp + 0x78, cp + 0xc0])
            b = m.get(cp + 0x78, 0x4c)
            if b:
                f = struct.unpack("<19f", b)
                # +0x78 X行(3) +0x84 Y行(3) +0x90 Z行(3) +0x9c ? +0xa0 位置(3) ... +0xb8 +0xbc +0xc0
                xyz = "%7.1f %6.1f %7.1f" % f[10:13]
                rot = "X(%.2f,%.2f) Z(%.2f,%.2f)" % (f[0], f[2], f[6], f[8])
                dirs = "%.3f %.3f" % (f[16], f[18])
        s750, s730 = comp(m, o, 0x750), comp(m, o, 0x730)
        f = lambda v: "-" if v is None else ("%d/0x%X" % (v, v & 0xffffffff))
        print("%-12X %-7s %-10s %-10s %-24s %-18s %-40s %s" % (o, m.d(o + 0x240), f(s750), f(s730), xyz, dirs, rot, nm))

m = Mem(pid)
times = int(sys.argv[1]) if len(sys.argv) > 1 else 1
rows = snapshot(m)
print("板子/监管 共 %d 个" % len(rows))
for k in range(times):
    if k: time.sleep(1); m.cache.clear()
    print("---- %s" % time.strftime("%H:%M:%S"))
    show(m, rows)
