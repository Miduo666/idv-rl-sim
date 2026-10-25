# -*- coding: utf-8 -*-
# PC 侧：完全按 PyGenius.h 的 C++ 读法(read_dict / str_equals / read_list / eid_key_string)读 final_genius_dict，
# 找出 C++ 在哪一步失败。输入是 cmd_fgd.py 的输出文件(里面有 FGD / SEAT 行)。
# 用法: python fgd_mem.py <cmd_fgd 输出文件>
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
from devread import Mem, sh

M = 0x00FFFFFFFFFFFFFF
is_obj = lambda p: p is not None and 0x7000000000 < p < 0x8000000000

lines = open(sys.argv[1], encoding="utf-8-sig", errors="replace").read().splitlines()
fgd = None; seats = []
for ln in lines:
    p = ln.split("\t")
    if p[0] == "FGD": fgd = int(p[1], 16) & M
    elif p[0] == "SEAT": seats.append((p[1], int(p[2], 16) & M, p[3]))
if not fgd:
    sys.exit("输出里没有 FGD 行")

pid = int(sh("pidof com.netease.dwrg").decode().split()[0])
m = Mem(pid)
m._say = lambda s: None                       # 静音 devread 的逐页日志

def rd(addr, n):
    m.fetch([addr, addr + n - 1])
    return m.get(addr, n)
def q(addr):
    b = rd(addr, 8); return None if b is None else struct.unpack("<Q", b)[0]
def ptr(addr):
    v = q(addr); return None if v is None else v & M

def str_at(s):
    """复刻 str_equals 的读法：+0x10 长度，+0x20 state，+0x30 数据"""
    if not is_obj(s): return "非对象指针 0x%X" % (s or 0)
    ln = q(s + 0x10); st = rd(s + 0x20, 4)
    if ln is None or st is None: return "读不到(页不可读/换出)"
    st = struct.unpack("<I", st)[0]
    ascii_ = (st >> 6) & 1; compact = (st >> 5) & 1; kind = (st >> 2) & 7
    data = rd(s + 0x30, ln) if 0 < ln < 64 else None
    return "len=%d compact=%d ascii=%d kind=%d data=%r" % (ln, compact, ascii_, kind, data)

print("== final_genius_dict @0x%X，按 C++ read_dict 的读法 ==" % fgd)
keys = ptr(fgd + 0x20)
print("  ma_keys = 0x%X  ma_values(+0x28) = 0x%X" % (keys or 0, ptr(fgd + 0x28) or 0))
if not is_obj(keys): sys.exit("  ma_keys 无效 -> C++ read_dict 在这里失败")
hdr = rd(keys, 32)
if hdr is None: sys.exit("  keys 头读不到 -> C++ read_dict 在这里失败(页换出?)")
idxb, kind = hdr[9], hdr[10]
nent = struct.unpack_from("<q", hdr, 24)[0]
stride = 24 if kind == 0 else 16
entries = keys + 32 + (1 << idxb)
print("  log2_index_bytes=%d kind=%d nentries=%d -> stride=%d entries=0x%X" % (idxb, kind, nent, stride, entries))
if idxb > 30 or nent < 0 or nent > (1 << 22): print("  !! 头部校验不过 -> read_dict 返回 false")
koff, voff = (8, 16) if stride == 24 else (0, 8)
table = {}
for i in range(max(0, min(nent, 64))):
    kp = ptr(entries + i * stride + koff); vp = ptr(entries + i * stride + voff)
    info = str_at(kp) if kp else "NULL(已删除条目)"
    val = "?"
    if is_obj(vp):
        n = q(vp + 0x10); it = ptr(vp + 0x18)
        tp = ptr(vp + 8)
        val = "对象@0x%X type@0x%X ob_size=%s items=0x%X" % (vp, tp or 0, n, it or 0)
        if n is not None and 0 < n <= 8 and is_obj(it):
            ints = []
            for j in range(n):
                e = ptr(it + j * 8)
                ints.append(q(e + 0x18) & 0xFFFFFFFF if is_obj(e) else None)
            val += " 值=%s" % ints
    elif vp:
        val = "非对象 0x%X" % vp
    print("  #%d key 0x%X: %s\n       value: %s" % (i, kp or 0, info, val))
    if kp:
        s = str_at(kp)
        if "data=b'" in s: table[s.split("data=b'")[1].rstrip("'")] = val

print("\n== 按 C++ eid_key_string 的读法拼座位键 ==")
for seat, eid, py_key in seats:
    tp = ptr(eid + 8)
    b = ptr(eid + 0x10)
    how = ""
    if b is not None and is_obj(b):
        n = q(b + 0x10); raw = rd(b + 0x20, 12)
        if n == 12 and raw: how = "ObjectId -> %s" % raw.hex()
    ivsz = q(eid + 0x10)
    print("  座位%s eid@0x%X Python键=%r  | C++ ObjectId 路径: %s | +0x10 当 int 的 ob_size=%s" % (
        seat, eid, py_key, how or "不成立", ivsz))
    print("        final_genius_dict 里按 Python 键找到: %s" % table.get(py_key, "<没找到>"))
