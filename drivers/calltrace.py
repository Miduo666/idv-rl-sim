# -*- coding: utf-8 -*-
"""从一个函数地址出发递归跟 bl/b 调用（llvm-objdump 反汇编，函数到第一个 ret 为止，最多 0x800 字节），
命中已知符号（llvm-nm -D -C）就打印路径。用法: calltrace.py <so> <起始地址hex> [深度=3] [符号过滤正则]"""
import sys, re, subprocess, os

SO, START = sys.argv[1], int(sys.argv[2], 16)
DEPTH = int(sys.argv[3]) if len(sys.argv) > 3 else 3
FILT = re.compile(sys.argv[4]) if len(sys.argv) > 4 else None
BIN = r"C:\Users\31297\AppData\Local\Android\Sdk\ndk\28.2.13676358\toolchains\llvm\prebuilt\windows-x86_64\bin"
syms = {}
for line in subprocess.run([os.path.join(BIN, "llvm-nm.exe"), "-D", "-C", "--defined-only", SO], capture_output=True, text=True).stdout.splitlines():
    p = line.split(" ", 2)
    if len(p) == 3 and p[1] in "Tt":
        syms[int(p[0], 16)] = p[2]
cache = {}


def callees(addr):
    if addr in cache:
        return cache[addr]
    out = subprocess.run([os.path.join(BIN, "llvm-objdump.exe"), "-d", "--no-show-raw-insn", "--start-address=0x%x" % addr,
                          "--stop-address=0x%x" % (addr + 0x800), SO], capture_output=True, text=True).stdout
    res = []
    for line in out.splitlines():
        m = re.match(r"\s*([0-9a-f]+):\s+(\w+)\s+(.*)", line)
        if not m:
            continue
        op, args = m.group(2), m.group(3)
        if op in ("bl", "b") and re.match(r"0x[0-9a-f]+", args):
            t = int(args.split()[0], 16)
            if op == "bl" or t < addr or t >= addr + 0x800:
                res.append((int(m.group(1), 16), op, t))
        if op == "ret":
            break
    cache[addr] = res
    return res


def walk(addr, depth, path):
    for site, op, t in callees(addr):
        name = syms.get(t)
        if name and (FILT is None or FILT.search(name)):
            print("  " * len(path) + "0x%x %s -> 0x%x %s" % (site, op, t, name[:110]))
        if depth > 1 and not (name and "@plt" in name) and t not in path:
            walk(t, depth - 1, path + [t])


walk(START, DEPTH, [START])
