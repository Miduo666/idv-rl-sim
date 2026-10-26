# -*- coding: utf-8 -*-
"""RAWANIMA(.animation) 结构探查：文件头 + 块表 + NAME 块。用法: rawanim_probe.py <文件或目录> [数量]"""
import sys, os, struct, glob, binascii


def hexs(b):
    return binascii.hexlify(b, " ").decode()


def probe(path):
    d = open(path, "rb").read()
    assert d[:8] == b"RAWANIMA", d[:8]
    fsize, = struct.unpack_from("<I", d, 8)
    print("==", os.path.basename(path), "len", len(d), "hdr_size", fsize)
    print("  hdr 0x0c..0x2c:", hexs(d[0x0c:0x2c]))
    n, = struct.unpack_from("<I", d, 0x28)
    skel = d[0x2c:0x2c + n].decode("utf-8", "replace")
    print("  skeleton:", skel)
    o = 0x2c + n
    while o + 8 <= len(d):
        tag = d[o:o + 4]
        sz, = struct.unpack_from("<I", d, o + 4)
        body = d[o + 8:o + 8 + sz]
        print("  [%s] @0x%x size %d" % (tag.decode("latin1"), o, sz))
        if tag == b"HEAD":
            print("     ", hexs(body))
            print("      f32:", [round(x, 4) for x in struct.unpack_from("<%df" % (sz // 4), body)])
        elif tag == b"NAME":
            print("     ", hexs(body[:48]))
            print("     ", body[:400])
        else:
            print("     ", hexs(body[:64]))
        o += 8 + sz
    if o != len(d):
        print("  !! 尾部剩余", len(d) - o)


if __name__ == "__main__":
    a = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    files = sorted(glob.glob(os.path.join(a, "*"))) if os.path.isdir(a) else [a]
    files = [f for f in files if open(f, "rb").read(8) == b"RAWANIMA"][:k]
    for f in files:
        probe(f)
