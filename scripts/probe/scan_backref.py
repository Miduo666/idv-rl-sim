# -*- coding: utf-8 -*-
"""在目标进程的 C++ 堆(scudo)里反查"谁指向这些对象"。

    python scan_backref.py --size                       # 只估算常驻体积，不读数据
    python scan_backref.py 0x73cdfcab50 0x73ce018d00 …  # 真正扫描

只扫 scudo:primary / scudo:secondary（C++ 堆），跳过 dalvik(Java堆)/kgsl(GPU)/文件映射。
只读 pagemap 标了常驻的页 —— 绝不因为扫描去触发目标进程缺页。
指针高位带 0xB4 标签，所以每个锚点要同时匹配裸值和带标签值。
"""
import sys, os, struct, subprocess, collections
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import sh, ADB, PAGE, TMP
from idv_probe import discover

WANT = ("scudo:primary", "scudo:secondary")
ANCHORS = [int(a, 16) for a in sys.argv[1:] if a.startswith("0x")]
SIZE_ONLY = "--size" in sys.argv

pid, libbase, bss, maps = discover()
regions = []
for ln in maps:
    p = ln.split()
    if not p or "-" not in p[0] or not p[1].startswith("rw"):
        continue
    a, b = (int(x, 16) for x in p[0].split("-"))
    name = ln.split(None, 5)[5].strip() if len(p) > 5 else ""
    if any(w in name for w in WANT):
        regions.append((a, b, name))
print("pid=%d  scudo 可写段 %d 个, 虚拟合计 %.1f MB"
      % (pid, len(regions), sum(b - a for a, b, _ in regions) / 1048576.0))


def pagemap(a, b):
    """整段一次性取 pagemap，返回常驻页号列表"""
    npg = (b - a) // PAGE
    sh("dd if=/proc/%d/pagemap bs=8 skip=%d count=%d of=/data/local/tmp/pm.bin 2>/dev/null; "
       "chmod 666 /data/local/tmp/pm.bin" % (pid, a // PAGE, npg))
    lp = os.path.join(TMP, "pm_region.bin")
    if os.path.exists(lp):
        os.remove(lp)
    subprocess.run([ADB, "pull", "/data/local/tmp/pm.bin", lp], capture_output=True)
    if not os.path.exists(lp):
        return []
    d = open(lp, "rb").read()
    return [a // PAGE + i for i in range(min(npg, len(d) // 8))
            if struct.unpack_from("<Q", d, i * 8)[0] >> 63]


def runs(pages):
    """把页号压成连续段 [(起始页, 页数), ...]，让 dd 能整段读"""
    out = []
    for p in pages:
        if out and out[-1][0] + out[-1][1] == p:
            out[-1][1] += 1
        else:
            out.append([p, 1])
    return out


total = 0
plan = []
for a, b, name in regions:
    pg = pagemap(a, b)
    total += len(pg)
    if pg:
        plan.append((a, b, name, runs(pg)))
    print("   0x%X-0x%X %7.2f MB 常驻 %d 页 (%.1f MB)"
          % (a, b, (b - a) / 1048576.0, len(pg), len(pg) * PAGE / 1048576.0))
print("\n常驻合计 %.1f MB, 连续段 %d 个" % (total * PAGE / 1048576.0, sum(len(p[3]) for p in plan)))
if SIZE_ONLY or not ANCHORS:
    sys.exit()

targets = {}
for anc in ANCHORS:
    targets[struct.pack("<Q", anc)] = (anc, "裸")
    targets[struct.pack("<Q", anc | 0xB4 << 56)] = (anc, "带0xB4标签")

hits = collections.defaultdict(list)
done = 0
for a, b, name, rr in plan:
    for start, n in rr:
        sh("dd if=/proc/%d/mem bs=4096 skip=%d count=%d of=/data/local/tmp/blk.bin 2>/dev/null; "
           "chmod 666 /data/local/tmp/blk.bin" % (pid, start, n))
        lp = os.path.join(TMP, "blk.bin")
        if os.path.exists(lp):
            os.remove(lp)
        subprocess.run([ADB, "pull", "/data/local/tmp/blk.bin", lp], capture_output=True)
        if not os.path.exists(lp):
            continue
        d = open(lp, "rb").read()
        for pat, (anc, kind) in targets.items():
            o = d.find(pat)
            while o != -1:
                if o % 8 == 0:
                    hits[anc].append((start * PAGE + o, kind))
                o = d.find(pat, o + 1)
        done += n
    print("   扫过 %.1f MB, 累计命中 %d" % (done * PAGE / 1048576.0, sum(len(v) for v in hits.values())))

print("\n=== 反查结果 ===")
for anc in ANCHORS:
    h = hits.get(anc, [])
    print("0x%X 被 %d 处引用" % (anc, len(h)))
    for addr, kind in h[:20]:
        print("    引用者 0x%X (%s)" % (addr, kind))
