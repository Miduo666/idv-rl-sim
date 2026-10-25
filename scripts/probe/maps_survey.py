# -*- coding: utf-8 -*-
"""列出目标进程可写段的分布与常驻情况，评估全内存反查的代价。"""
import sys, struct, subprocess, os, collections
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import sh, ADB, PAGE, TMP
from idv_probe import discover

ANCHORS = [int(a, 16) for a in sys.argv[1:] if a.startswith("0x")]

pid, libbase, bss, maps = discover()
print("pid=%d  libbase=0x%X\n" % (pid, libbase))

rw = []
for ln in maps:
    p = ln.split()
    if not p or "-" not in p[0]:
        continue
    a, b = (int(x, 16) for x in p[0].split("-"))
    if not p[1].startswith("rw"):
        continue
    name = p[5] if len(p) > 5 else "[anon]"
    rw.append((a, b, b - a, name))

tot = sum(r[2] for r in rw)
print("可写段 %d 个, 合计 %.1f MB" % (len(rw), tot / 1048576.0))

by = collections.Counter()
for a, b, n, name in rw:
    by[name] += n
print("\n按名字聚合 (前15):")
for name, n in by.most_common(15):
    print("   %-46s %8.1f MB" % (name[:46], n / 1048576.0))

for anc in ANCHORS:
    for a, b, n, name in rw:
        if a <= anc < b:
            print("\n锚点 0x%X 落在: 0x%X-0x%X (%.1f MB) %s" % (anc, a, b, n / 1048576.0, name))
            break
    else:
        print("\n锚点 0x%X 不在任何可写段内 (!)" % anc)

# 常驻率: 只对锚点所在的那些段统计，决定能不能整段 dd
tgt = []
for anc in ANCHORS:
    for a, b, n, name in rw:
        if a <= anc < b and (a, b) not in [(x[0], x[1]) for x in tgt]:
            tgt.append((a, b, n, name))
print("\n=== 锚点所在段的常驻率 ===")
for a, b, n, name in tgt:
    npg = n // PAGE
    sh("dd if=/proc/%d/pagemap bs=8 skip=%d count=%d of=/data/local/tmp/pm.bin 2>/dev/null; "
       "chmod 666 /data/local/tmp/pm.bin" % (pid, a // PAGE, npg))
    lp = os.path.join(TMP, "pm_region.bin")
    subprocess.run([ADB, "pull", "/data/local/tmp/pm.bin", lp], capture_output=True)
    d = open(lp, "rb").read()
    res = swp = 0
    for i in range(min(npg, len(d) // 8)):
        e = struct.unpack_from("<Q", d, i * 8)[0]
        if e >> 63:
            res += 1
        elif (e >> 62) & 1:
            swp += 1
    print("   0x%X-0x%X %7.1f MB  常驻 %d/%d (%.0f%%)  换出 %d  %s"
          % (a, b, n / 1048576.0, res, npg, 100.0 * res / max(npg, 1), swp, name))
