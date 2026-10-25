# -*- coding: utf-8 -*-
"""探索 .scn_col 格式：按猜测的结构解析第一个物体，打印索引之后的字节，帮助确定剩余字段。"""
import sys, struct

d = open(sys.argv[1], "rb").read()
u32 = lambda o: struct.unpack_from("<I", d, o)[0]
f32 = lambda o: struct.unpack_from("<f", d, o)[0]
p = 0
print("hdr", u32(0), u32(4))
p = 8
for obj in range(int(sys.argv[2]) if len(sys.argv) > 2 else 3):
    st = p
    a = u32(p); nv = u32(p + 4); p += 8
    verts = [struct.unpack_from("<3f", d, p + 12 * i) for i in range(nv)]
    p += 12 * nv
    nt = u32(p); p += 4
    tflags = [u32(p + 4 * i) for i in range(nt)]
    p += 4 * nt
    ni = u32(p); p += 4
    idx = [u32(p + 4 * i) for i in range(ni)]
    p += 4 * ni
    print("obj%d @%#x a=%d nv=%d nt=%d ni=%d  tflags[:6]=%s idx[:9]=%s" % (obj, st, a, nv, nt, ni, tflags[:6], idx[:9]))
    print("   verts[:3]", [tuple(round(x, 2) for x in v) for v in verts[:3]])
    print("   next 96B:", d[p:p + 96].hex())
    fl = struct.unpack_from("<24f", d, p)
    print("   as f32:", [round(x, 3) for x in fl])
    # 尝试猜：之后是否是 3x4 或 4x4 矩阵 + 下一物体
    inp = input() if len(sys.argv) > 3 else None
    # 让调用方指定跳过字节数
    skip = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    p += skip
