# -*- coding: utf-8 -*-
"""密码机破译进度字段定位：按已知进度分档做差分。

用法:
    python sender_progress.py 0x73cdfcab50=100 0x73ce018d00=100 0x73ce018350=80 0x73ce021e50=25

未在命令行给出的 sender 对象一律当成 0%。
思路: 进度字段必须对已知进度**单调**，且同档位对象取值一致。
"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem, PAGE
from idv_probe import discover, dump_bss, find_sigs, class_names, read_objects, MASK

WIN = 0x1000          # 每个对象扫描的窗口大小
KW = "sender"

known = {}
for a in sys.argv[1:]:
    k, _, v = a.partition("=")
    known[int(k, 16)] = float(v)

pid, libbase, bss, maps = discover()
d = dump_bss(pid, bss, True)
head = find_sigs(d, bss[0], libbase)["array"][0]
m = Mem(pid)
m.quiet = True
r = read_objects(m, head)
objs = r["objs"]
names = class_names(m, objs)

# 真实密码机: 类名含 sender 且 +0x240==2 (skill 里两视角验证过的存在性判据)
send = []
for o in objs:
    if KW not in names.get(o, "").lower():
        continue
    if m.d(o + 0x240) == 2:
        send.append(o)

print("数组 count=%d  类名读出=%d  sender且+0x240==2 的对象 %d 个\n" % (r["count"], len(names), len(send)))

miss = [a for a in known if a not in send]
if miss:
    print("!! 命令行给的地址不在筛选结果里: %s" % ", ".join("0x%X" % a for a in miss))
    for a in miss:                      # 仍然纳入分析，顺便报告它为什么没被筛进来
        print("   0x%X: +0x240=%s 类名=%s" % (a, m.d(a + 0x240), names.get(a, "<读不出>")[:50]))
    send = sorted(set(send) | set(miss))

# 一次性把所有窗口拉进缓存，尽量让 7 个对象是同一瞬间的快照
m.fetch([o + k for o in send for k in list(range(0, WIN, PAGE)) + [WIN - 8]], "")

blob = {}
for o in send:
    b = m.get(o, WIN)
    if b is None:                       # 跨页有空洞时退化成逐页拼
        b = b"".join((m.get(o + k, min(PAGE, WIN - k)) or b"\xAA" * min(PAGE, WIN - k))
                     for k in range(0, WIN, PAGE))
    blob[o] = b

prog = {o: known.get(o, 0.0) for o in send}
print("=== 参与差分的对象 ===")
for o in sorted(send, key=lambda x: -prog[x]):
    print("   0x%X  已知进度=%5.1f%%  %s" % (o, prog[o], names.get(o, "")[:56]))

lo = [o for o in send if prog[o] == 0]
hi = sorted([o for o in send if prog[o] > 0], key=lambda x: prog[x])

print("\n=== 单调候选 (同档一致 + 随进度单调) ===")
hits = []
for off in range(0, WIN - 4, 4):
    for tag, unpack in (("f32", "<f"), ("u32", "<I")):
        try:
            v = {o: struct.unpack_from(unpack, blob[o], off)[0] for o in send}
        except struct.error:
            continue
        if any(x != x for x in v.values()):          # NaN
            continue
        z = {v[o] for o in lo}
        if len(z) != 1:                              # 0% 档必须完全一致
            continue
        base = z.pop()
        if any(v[o] == base for o in hi):            # 非0档不能和0档同值
            continue
        seq = [v[o] for o in hi]
        if len(set(seq)) != len(seq):                # 不同进度必须给出不同值
            continue
        if not (all(a < b for a, b in zip(seq, seq[1:])) or
                all(a > b for a, b in zip(seq, seq[1:]))):
            continue
        hits.append((off, tag, base, [(prog[o], v[o]) for o in hi]))

for off, tag, base, seq in hits:
    print("   +0x%03X %s  0%%档=%-12.6g  %s" % (
        off, tag, base, "  ".join("%.0f%%->%-12.6g" % s for s in seq)))
if not hits:
    print("   无 —— 进度不在对象本体前 0x%X 字节里，需要跟指针进子对象" % WIN)

print("\n=== 全部有差异的偏移 (供人工挑) ===")
for off in range(0, WIN - 4, 4):
    v = [struct.unpack_from("<I", blob[o], off)[0] for o in send]
    if len(set(v)) == 1:
        continue
    fv = [struct.unpack_from("<f", blob[o], off)[0] for o in send]
    show = []
    for o, iv, ff in zip(send, v, fv):
        s = "%.4g" % ff if (ff == ff and 1e-6 < abs(ff) < 1e9) else "%08x" % iv
        show.append("%s:%s" % (("%.0f%%" % prog[o]), s))
    print("   +0x%03X  %s" % (off, " ".join(show)))
