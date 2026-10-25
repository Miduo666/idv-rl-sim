# -*- coding: utf-8 -*-
"""thd/*.thy|*.thh = b"THFB" + u32 + FlatBuffers。逐层打印表的字段：标量 / 子表 / 向量(长度+头部字节)。"""
import sys, struct

def u8(d, o): return d[o]
def u32(d, o): return struct.unpack_from("<I", d, o)[0]
def i32(d, o): return struct.unpack_from("<i", d, o)[0]
def u16(d, o): return struct.unpack_from("<H", d, o)[0]


def show_table(d, t, depth, seen):
    if t in seen or depth > 4: return
    seen.add(t)
    vt = t - i32(d, t)
    vlen, tlen = u16(d, vt), u16(d, vt + 2)
    offs = [u16(d, vt + 4 + 2 * k) for k in range((vlen - 4) // 2)]
    pad = "  " * depth
    print("%stable@%#x vt@%#x tlen=%d field_offs=%s" % (pad, t, vt, tlen, offs))
    # 字段大小 = 下一个字段偏移 - 本偏移（按偏移排序估算）
    present = sorted((o, k) for k, o in enumerate(offs) if o)
    for idx_, (o, k) in enumerate(present):
        nxt = present[idx_ + 1][0] if idx_ + 1 < len(present) else tlen
        size = nxt - o
        p = t + o
        raw = d[p:p + size]
        line = "%s  f%d @+%d size~%d raw=%s" % (pad, k, o, size, raw.hex())
        if size >= 4:
            q = p + u32(d, p)
            if q + 4 <= len(d):
                n = u32(d, q)
                line += " | as-ref -> %#x (u32 there=%d, next16=%s)" % (q, n, d[q + 4:q + 20].hex())
        print(line)
        if size == 4:
            q = p + u32(d, p)
            if 0 < q < len(d) - 8:
                # 试当子表
                try:
                    vt2 = q - i32(d, q)
                    if 0 <= vt2 < len(d) and 4 <= u16(d, vt2) < 64 and u16(d, vt2) % 2 == 0:
                        show_table(d, q, depth + 1, seen)
                except Exception:
                    pass


if __name__ == "__main__":
    for path in sys.argv[1:]:
        raw = open(path, "rb").read()
        print("=====", path.split("\\")[-1], len(raw), raw[:4], raw[4:8].hex())
        d = raw[8:]
        show_table(d, u32(d, 0), 0, set())
