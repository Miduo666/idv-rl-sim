# -*- coding: utf-8 -*-
r"""把目标进程的常驻堆一次性拉到 PC，之后所有搜索都离线做。

    python heap_dump.py                 # 默认 scudo(C++堆) + 无名 anon(CPython 的 pymalloc arena 在这里)
    python heap_dump.py --only scudo

产物: <TMP>\heap_<pid>.bin  +  heap_<pid>.idx  (索引: 每条 vaddr,文件偏移,长度)

为什么要批量: 常驻段有近两万个不连续片段，逐段 adb 往返要一个多小时。
这里把上千条 dd 合成一个脚本、输出拼成一个大文件，一个批次只来回一次。
只读 pagemap 标常驻的页，不触发目标缺页。
"""
import sys, os, struct, subprocess, time
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import sh, ADB, PAGE, TMP
from idv_probe import discover

BATCH_PAGES = 8192                      # 每批 32MB
ONLY = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else ""
PATS = [p.strip() for p in ONLY.split(",")] if ONLY else []


def is_anon(name):
    return name == "" or name == "[anon]"   # 无名匿名段: CPython pymalloc arena 落在这里


def want(name):
    if not PATS:
        return "scudo" in name or is_anon(name)
    for p in PATS:
        if (is_anon(name) if p == "anon" else p in name):   # 无名段匹配不了子串，单独判
            return True
    return False


pid, libbase, bss, maps = discover()
regions = []
for ln in maps:
    p = ln.split()
    if not p or "-" not in p[0] or not p[1].startswith("rw"):
        continue
    a, b = (int(x, 16) for x in p[0].split("-"))
    name = ln.split(None, 5)[5].strip() if len(p) > 5 else ""
    if want(name):
        regions.append((a, b, name))
print("pid=%d  选中可写段 %d 个, 虚拟 %.1f MB"
      % (pid, len(regions), sum(b - a for a, b, _ in regions) / 1048576.0))

# ---- 一次性取所有选中段的 pagemap ----
print("读 pagemap ...")
runs = []
lines = []
for a, b, _ in regions:
    lines.append("dd if=/proc/%d/pagemap bs=8 skip=%d count=%d 2>/dev/null\n"
                 % (pid, a // PAGE, (b - a) // PAGE))
sp = os.path.join(TMP, "pmall.sh")
open(sp, "w", newline="\n").write("".join(lines))
subprocess.run([ADB, "push", sp, "/data/local/tmp/pmall.sh"], capture_output=True)
sh("sh /data/local/tmp/pmall.sh > /data/local/tmp/pmall.bin; chmod 666 /data/local/tmp/pmall.bin")
lp = os.path.join(TMP, "pmall.bin")
if os.path.exists(lp):
    os.remove(lp)
subprocess.run([ADB, "pull", "/data/local/tmp/pmall.bin", lp], capture_output=True)
pm = open(lp, "rb").read()

pos = 0
for a, b, _ in regions:
    n = (b - a) // PAGE
    for i in range(n):
        if (pos + i) * 8 + 8 > len(pm):
            break
        if struct.unpack_from("<Q", pm, (pos + i) * 8)[0] >> 63:
            pg = a // PAGE + i
            if runs and runs[-1][0] + runs[-1][1] == pg:
                runs[-1][1] += 1
            else:
                runs.append([pg, 1])
    pos += n
tot = sum(r[1] for r in runs)
print("常驻 %.1f MB, 连续段 %d 个" % (tot * PAGE / 1048576.0, len(runs)))
if "--size" in sys.argv:
    sys.exit()

# ---- 分批拉取 ----
blob = os.path.join(TMP, "heap_%d%s.bin" % (pid, TAG and "_" + TAG))
idx = os.path.join(TMP, "heap_%d%s.idx" % (pid, TAG and "_" + TAG))
fb = open(blob, "wb")
fi = open(idx, "w")
off = 0
batch = []
bp = 0
t0 = time.time()
done = 0


def flush(batch):
    global off, done
    if not batch:
        return
    sp = os.path.join(TMP, "rdall.sh")
    open(sp, "w", newline="\n").write("".join(
        "dd if=/proc/%d/mem bs=4096 skip=%d count=%d 2>/dev/null\n" % (pid, s, n) for s, n in batch))
    subprocess.run([ADB, "push", sp, "/data/local/tmp/rdall.sh"], capture_output=True)
    sh("sh /data/local/tmp/rdall.sh > /data/local/tmp/rdall.bin; chmod 666 /data/local/tmp/rdall.bin")
    lp = os.path.join(TMP, "rdall.bin")
    if os.path.exists(lp):
        os.remove(lp)
    subprocess.run([ADB, "pull", "/data/local/tmp/rdall.bin", lp], capture_output=True)
    d = open(lp, "rb").read() if os.path.exists(lp) else b""
    p = 0
    for s, n in batch:
        seg = d[p:p + n * PAGE]
        p += n * PAGE
        if len(seg) != n * PAGE:            # 读短了就丢掉这段，宁缺毋滥
            continue
        fb.write(seg)
        fi.write("%x %d %d\n" % (s * PAGE, off, len(seg)))
        off += len(seg)
    done += sum(n for _, n in batch)
    print("   %.1f/%.1f MB  用时 %.0fs" % (done * PAGE / 1048576.0, tot * PAGE / 1048576.0, time.time() - t0))


for s, n in runs:
    while n > 0:
        take = min(n, BATCH_PAGES - bp)
        batch.append((s, take))
        s += take
        n -= take
        bp += take
        if bp >= BATCH_PAGES:
            flush(batch)
            batch, bp = [], 0
flush(batch)
fb.close()
fi.close()
print("\n落盘: %s (%.1f MB)\n索引: %s" % (blob, off / 1048576.0, idx))
