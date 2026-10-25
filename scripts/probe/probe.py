# -*- coding: utf-8 -*-
import sys, struct, subprocess, time
SP = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-----\3d04aa5f-eccd-4e15-a4af-0eb66ba48c11\scratchpad"
sys.path.insert(0, SP)
from devread import Mem, sh, ADB

LIB = 0x77a180b000
M = 0x00FFFFFFFFFFFFFF
SIG = LIB + 0xA9E9038
PID = 17226


def pagemap(pages):
    script = "".join("dd if=/proc/%d/pagemap bs=8 skip=%d count=1 2>/dev/null\n" % (PID, p) for p in pages)
    open(SP + r"\pm2.sh", "w", newline="\n").write(script)
    subprocess.run([ADB, "push", SP + r"\pm2.sh", "/data/local/tmp/pm2.sh"], capture_output=True)
    sh("sh /data/local/tmp/pm2.sh > /data/local/tmp/pm2.bin; chmod 666 /data/local/tmp/pm2.bin")
    subprocess.run([ADB, "pull", "/data/local/tmp/pm2.bin", SP + r"\pm2.bin"], capture_output=True)
    d = open(SP + r"\pm2.bin", "rb").read()
    out = []
    for i in range(len(pages)):
        e = struct.unpack_from("<Q", d, i * 8)[0] if (i + 1) * 8 <= len(d) else 0
        out.append((pages[i], e, bool(e >> 63), bool((e >> 62) & 1)))
    return out


m = Mem(PID)
AA = LIB + 0xb40a638
m.fetch([AA, AA + 8], "(数组头)")
arr = m.q(AA) & M
end = m.q(AA + 8) & M
print("数组头: arr=0x%X end=0x%X count=%d" % (arr, end, (end - arr) // 8))

print("\n--- 连续 3 次采样关键页的 present/swap 状态 ---")
keys = [AA // 4096, arr // 4096, (end - 8) // 4096, SIG // 4096]
labels = ["数组头(bss)", "数组指针页", "数组尾页", "签名页(bss)"]
for t in range(3):
    st = pagemap(keys)
    print("  第%d次: %s" % (t + 1, "  ".join(
        "%s=%s" % (labels[i], "常驻" if st[i][2] else ("换出" if st[i][3] else "缺失0x%X" % st[i][1]))
        for i in range(len(keys)))))
    time.sleep(1)

print("\n--- 矩阵是否在实时更新(你刚移动过) ---")
m.fetch([SIG + 0x440], "")
p1 = m.q(SIG + 0x440)
if p1:
    p1 &= M
    m.fetch([p1 + 0xa58], "")
    p2 = m.q(p1 + 0xa58)
    if p2:
        MAT = (p2 & M) + 0x2c0
        m.fetch([MAT, MAT + 0x40], "")
        row = [m.f(MAT + i * 4) for i in range(16)]
        if all(r is not None for r in row):
            print("  Matrix=0x%X" % MAT)
            for r in range(4):
                print("    " + " ".join("%12.4f" % row[r * 4 + c] for c in range(4)))

print("\n--- 设备内存/交换压力 ---")
print(sh("grep -E 'MemFree|SwapTotal|SwapFree' /proc/meminfo").decode(errors="replace").strip())
print(sh("grep -E 'VmSwap|VmRSS' /proc/%d/status" % PID).decode(errors="replace").strip())
print(sh("cat /proc/%d/oom_score_adj; dumpsys activity processes 2>/dev/null | grep -m2 dwrg" % PID).decode(errors="replace").strip()[:400])
