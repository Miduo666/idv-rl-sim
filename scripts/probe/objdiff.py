# -*- coding: utf-8 -*-
r"""对比两个场景对象的原始字节，找可以区分它们的字段。

    python objdiff.py 0x7AD5B1B800 0x7AC2998F40 [--len 0x300] [--label 废弃,真实]

先打印已知语义字段(见 idv-reverse-resume 的字段表)，再把两者不同的偏移按
1/2/4字节宽度列出来，最后沿 +0xf8 五级链读类名确认是不是同一个类。
"""
import struct
import sys

sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF


def arg(n, d):
    return sys.argv[n] if len(sys.argv) > n else d


A = int(sys.argv[1], 16)
B = int(sys.argv[2], 16)
N = int(sys.argv[sys.argv.index("--len") + 1], 0) if "--len" in sys.argv else 0x300
标签 = (sys.argv[sys.argv.index("--label") + 1].split(",")
       if "--label" in sys.argv else ["A", "B"])

pid, libbase, bss, maps = discover()
m = Mem(pid)
m.quiet = True
print("pid=%d libbase=0x%X" % (pid, libbase))

m.fetch([A, A + N, B, B + N], "")
ba = m.get(A, N)
bb = m.get(B, N)
if not ba or not bb:
    sys.exit("读不到: %s%s" % ("A " if not ba else "", "B" if not bb else ""))


def 类名(base):
    """+0xf8 -> +0x0 -> +0x8 -> +0x20 -> +0x20 = 类名对象; 其 +0x8=串指针 +0x10=长度"""
    p = base
    for off in (0xF8, 0x0, 0x8, 0x20, 0x20):
        m.fetch([p + off, p + off + 8], "")
        b = m.get(p + off, 8)
        if not b:
            return "(链断在 +0x%X)" % off
        p = struct.unpack("<Q", b)[0] & MASK
        if not (0x7000000000 < p < 0x8000000000):
            return "(指针无效于 +0x%X)" % off
    m.fetch([p, p + 24], "")
    h = m.get(p, 24)
    if not h:
        return "(类名头读不到)"
    sp = struct.unpack_from("<Q", h, 8)[0] & MASK
    ln = struct.unpack_from("<I", h, 16)[0]
    if not (0 < ln < 256):
        return "(长度异常 %d)" % ln
    m.fetch([sp, sp + ln], "")
    s = m.get(sp, ln)
    return s.decode("utf-8", "replace") if s else "(串读不到)"


def f32(b, o):
    return struct.unpack_from("<f", b, o)[0]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


print("\n=== 类名 ===")
print("  %-6s 0x%X  %s" % (标签[0], A, 类名(A)))
print("  %-6s 0x%X  %s" % (标签[1], B, 类名(B)))

已知 = [
    (0x6D, "u8", "实体种类位域"),
    (0x70, "u32", "活跃位(对本机可见)"),
    (0xA8, "u32", "256=已使用(椅子/摄影机)"),
    (0xAA, "u8", "通用存活/可交互位"),
    (0x148, "u32", "0=已用完(箱子)"),
    (0x1A0, "f32", "类型 450=角色 500=可交互物"),
    (0x240, "u32", "本局是否真实存在(==2)"),
    (0x298, "u32", "备用判定 pd2"),
]
print("\n=== 已知语义字段 ===")
print("  %-8s %-34s %18s %18s" % ("偏移", "含义", 标签[0], 标签[1]))
for off, w, 说明 in 已知:
    if off + 4 > N:
        continue
    if w == "u8":
        va, vb = ba[off], bb[off]
        fa, fb = "0x%02X" % va, "0x%02X" % vb
    elif w == "f32":
        va, vb = f32(ba, off), f32(bb, off)
        fa, fb = "%.4f" % va, "%.4f" % vb
    else:
        va, vb = u32(ba, off), u32(bb, off)
        fa, fb = "%d (0x%X)" % (va, va), "%d (0x%X)" % (vb, vb)
    记 = "  <<< 不同" if va != vb else ""
    print("  +0x%-6X %-34s %18s %18s%s" % (off, 说明, fa, fb, 记))

print("\n=== 全部不同的 4 字节槽 (跳过坐标区 0xA0~0xB0) ===")
print("  %-8s %-22s %-22s %s" % ("偏移", 标签[0], 标签[1], "浮点解读"))
for off in range(0, N - 4, 4):
    va, vb = u32(ba, off), u32(bb, off)
    if va == vb:
        continue
    fa, fb = f32(ba, off), f32(bb, off)
    浮 = ""
    if abs(fa) < 1e6 and abs(fb) < 1e6:
        浮 = "%.3f / %.3f" % (fa, fb)
    print("  +0x%-6X %-22s %-22s %s"
          % (off, "%d(0x%X)" % (va, va), "%d(0x%X)" % (vb, vb), 浮))
