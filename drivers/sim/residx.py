# -*- coding: utf-8 -*-
"""资源索引(.idx, SKPW)读取 + 按路径找条目。条目只存 16 字节哈希，路径→哈希的算法用候选法试出来。"""
import sys, struct, hashlib, zlib

IDX_HEAD_SIZE = None
IDX_REC_SIZE = None


def read_idx(path, head, rec):
    d = open(path, "rb").read()
    assert d[:4] == b"SKPW", d[:4]
    n = struct.unpack_from("<I", d, 0x0C)[0]
    out = {}
    for i in range(n):
        r = d[head + i * rec: head + (i + 1) * rec]
        out[r[0:16]] = dict(pkg=r[0x14], off=struct.unpack_from("<I", r, 0x18)[0],
                            payload=struct.unpack_from("<I", r, 0x1C)[0],
                            hdr=struct.unpack_from("<H", r, 0x20)[0], raw=r)
    return out


def variants(p):
    a = p.replace("\\", "/")
    b = p.replace("/", "\\")
    for s in {a, b, a.lower(), b.lower(), a.upper(), b.upper()}:
        yield s


def xxh128key(s):
    """引擎 neox::XXH3_128(path, len, seed=0)，结果按 (low64, high64) 小端写入 16 字节。"""
    import xxhash
    v = xxhash.xxh3_128_intdigest(s.encode("utf-8"), 0)
    return v.to_bytes(16, "little")


def hashes(s):
    for enc in ("utf-8", "utf-16-le"):
        bs = s.encode(enc)
        yield "md5/" + enc, hashlib.md5(bs).digest()
        yield "md5rev/" + enc, hashlib.md5(bs).digest()[::-1]
    yield "xxh3_128", xxh128key(s)


if __name__ == "__main__":
    idx, head, rec = sys.argv[1], int(sys.argv[2], 0), int(sys.argv[3], 0)
    tab = read_idx(idx, head, rec)
    print("entries", len(tab))
    for p in sys.argv[4:]:
        hit = False
        for v in variants(p):
            for name, h in hashes(v):
                if h in tab:
                    print("HIT", name, repr(v), tab[h]["pkg"], hex(tab[h]["off"]), tab[h]["payload"])
                    hit = True
        if not hit:
            print("miss", p)
