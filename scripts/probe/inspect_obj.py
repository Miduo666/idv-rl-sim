# -*- coding: utf-8 -*-
"""对比一个可疑对象和已知真实对象的全部字段，找出能把它们分开的判据
用法: python inspect_obj.py 0x77d2330220 [更多地址...]
"""
import sys, os, struct, collections
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, SP)
from devread import Mem
from idv_probe import discover, dump_bss, find_sigs, class_names, MASK, PTR_MIN, PTR_MAX

suspects = [int(a, 16) for a in sys.argv[1:]]

pid, libbase, bss, maps = discover()
d = dump_bss(pid, bss, False)
head = find_sigs(d, bss[0], libbase)["array"][0]

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

# 当前通过旧判据(+0x1a0==500)的 sender
passed = [o for o in objs if "sender" in names.get(o, "") and m.f(o + 0x1a0) == 500.0]
print("类名含 sender 的对象: %d 个" % sum(1 for o in objs if "sender" in names.get(o, "")))
print("其中通过 +0x1a0==500 的: %d 个" % len(passed))
for o in passed:
    xyz = coord(o)
    mark = "  <<< 用户报告是假的" if o in suspects else ""
    print("   0x%X %s%s" % (o, ("(%8.1f,%6.2f,%8.1f)" % tuple(xyz)) if xyz else "坐标N/A", mark))

for s in suspects:
    if s not in objs:
        print("\n!! 0x%X 不在当前对象数组里(可能已重开局/地址变了)" % s)

bad = [o for o in passed if o in suspects]
good = [o for o in passed if o not in suspects]
if not bad:
    print("\n可疑对象不在通过列表里，无法做差分。")
    sys.exit()

print("\n=== 找能把 %d 个真实的 和 %d 个假的 分开的字段 ===" % (len(good), len(bad)))
blobs = {}
for o in passed:
    b = m.get(o, 0x300)
    if b:
        blobs[o] = b
for off in range(0, 0x300 - 4, 4):
    gv = {struct.unpack_from("<I", blobs[o], off)[0] for o in good if o in blobs}
    bv = {struct.unpack_from("<I", blobs[o], off)[0] for o in bad if o in blobs}
    if gv and bv and not (gv & bv):          # 真假两组取值完全不重叠 => 可用判据
        def fmt(vs):
            out = []
            for v in sorted(vs)[:4]:
                fv = struct.unpack("<f", struct.pack("<I", v))[0]
                out.append("0x%X%s" % (v, ("(f=%.4g)" % fv) if -1e9 < fv < 1e9 else ""))
            return " ".join(out) + ("..." if len(vs) > 4 else "")
        print("  +0x%03X  真实={%s}   假={%s}" % (off, fmt(gv), fmt(bv)))

# 顺便看看坐标子对象本身有没有区别
print("\n=== objcoor 指针与所在区段 ===")
for o in passed:
    c = m.q(o + 0x28)
    cc = (c & MASK) if c else 0
    r = m.region(cc) if cc else None
    print("   0x%X coor=0x%X [%s]%s" % (o, cc, (r[3].split()[-1] if r and len(r[3].split()) > 5 else (r[2] if r else "未映射")),
                                        "  <<< 假" if o in bad else ""))
