# -*- coding: utf-8 -*-
""".scn_col 解析（服务端静态场景碰撞）。
每个物体：[u32 a][u32 flags][u32 c][u32 nv][nv×3 f32 局部顶点][u32 nt][nt×u32 三角标志][u32 ni][ni×u32 索引]
          [u32 4][16 f32 矩阵][u32 3][3 f32 位置]
用法: scncol.py <file.scn_col> [--obj out.obj]"""
import sys, struct


class ColObj:
    __slots__ = ("off", "a", "flags", "c", "verts", "tflags", "idx", "mat", "pos", "bvh", "extra")


def parse(d):
    p = 0
    objs = []
    u = lambda o: struct.unpack_from("<I", d, o)[0]
    while p < len(d):
        o = ColObj(); o.off = p
        o.a, o.flags, o.c, nv = struct.unpack_from("<4I", d, p); p += 16
        o.verts = [struct.unpack_from("<3f", d, p + 12 * i) for i in range(nv)]; p += 12 * nv
        nt = u(p); p += 4
        o.tflags = list(struct.unpack_from("<%dI" % nt, d, p)); p += 4 * nt
        ni = u(p); p += 4
        o.idx = list(struct.unpack_from("<%dI" % ni, d, p)); p += 4 * ni
        o.bvh = None
        if o.c == 3:                      # 类型 3：后跟 Bullet 序列化的量化 BVH（"BULLETf_v284QBVH"）
            n = u(p); p += 4
            o.bvh = d[p:p + n]; p += n
        o.mat = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
        o.pos = (0.0, 0.0, 0.0)
        o.extra = []
        while p < len(d):                 # 尾部是带标签的可选字段；遇到 1 = 下一个物体开始
            t = u(p)
            if t == 1:
                break
            p += 4
            if t == 4:
                o.mat = struct.unpack_from("<16f", d, p); p += 64
            elif t == 3:
                o.pos = struct.unpack_from("<3f", d, p); p += 12
            elif t == 5:                  # 两个 u32（像材质/组编号 + 标志位）
                o.extra.append(struct.unpack_from("<2I", d, p)); p += 8
            else:
                raise AssertionError(("unknown tag", hex(p - 4), t))
        assert ni == 3 * nt, ("ni!=3nt", o.off, ni, nt)
        assert all(i < nv for i in o.idx), ("idx range", o.off)
        objs.append(o)
    assert p == len(d), (p, len(d))
    return objs


def world_verts(o, mode="row"):
    """mode=row: v' = v·M(3x3 行向量约定) + pos；mode=col: v' = M·v + pos"""
    m = o.mat
    out = []
    for x, y, z in o.verts:
        if mode == "none":
            wx, wy, wz = x, y, z
        elif mode == "row":
            wx = x * m[0] + y * m[4] + z * m[8]
            wy = x * m[1] + y * m[5] + z * m[9]
            wz = x * m[2] + y * m[6] + z * m[10]
        else:
            wx = m[0] * x + m[1] * y + m[2] * z
            wy = m[4] * x + m[5] * y + m[6] * z
            wz = m[8] * x + m[9] * y + m[10] * z
        out.append((wx + o.pos[0], wy + o.pos[1], wz + o.pos[2]))
    return out


if __name__ == "__main__":
    import collections
    d = open(sys.argv[1], "rb").read()
    objs = parse(d)
    print("objects:", len(objs), " verts:", sum(len(o.verts) for o in objs), " tris:", sum(len(o.idx) // 3 for o in objs))
    print("a values:", collections.Counter(o.a for o in objs).most_common(5))
    print("flags:", collections.Counter(hex(o.flags) for o in objs).most_common(10))
    print("c values:", collections.Counter(o.c for o in objs).most_common(5))
    print("tri flags:", collections.Counter(t for o in objs for t in o.tflags).most_common(10))
    print("mat[3,7,11,12..15]:", collections.Counter(tuple(round(o.mat[i], 3) for i in (3, 7, 11, 12, 13, 14, 15)) for o in objs).most_common(4))
    W = [v for o in objs for v in world_verts(o)]
    xs, ys, zs = zip(*W)
    print("world bounds x[%.1f,%.1f] y[%.1f,%.1f] z[%.1f,%.1f]" % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    if "--obj" in sys.argv:
        out = sys.argv[sys.argv.index("--obj") + 1]
        with open(out, "w") as f:
            base = 1
            for o in objs:
                wv = world_verts(o)
                for x, y, z in wv: f.write("v %.4f %.4f %.4f\n" % (x, y, z))
                for i in range(0, len(o.idx), 3):
                    f.write("f %d %d %d\n" % (o.idx[i] + base, o.idx[i + 1] + base, o.idx[i + 2] + base))
                base += len(wv)
        print("wrote", out)
