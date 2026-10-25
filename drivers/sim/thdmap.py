# -*- coding: utf-8 -*-
"""thd 清单：.thh/.thy = b"THFB"+u32+FlatBuffers。
根表.f1 -> 表T: T.f0 = 主向量(每条资源一个元素: thh 是 u32, thy 是 32 字节记录[4×u32 + MD5]),
               T.f1 = 共用前缀子表(两文件相同)。本脚本把三处 u32 收集起来, 用候选 32 位哈希匹配路径。"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thfb


def main_vector(raw, elem):
    d = raw[8:]
    T = 0x20
    p = T + 4
    q = p + thfb.u32(d, p)
    n = thfb.u32(d, q)
    return d, q + 4, n


def u32vec(d, start, n): return list(struct.unpack_from("<%dI" % n, d, start))


def fnv1a32(bs):
    h = 2166136261
    for c in bs: h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return h


def cand_hashes(s):
    import xxhash, mmh3
    import hashlib
    bs = s.encode("utf-8")
    out = {"fnv1a": fnv1a32(bs), "xxh32": xxhash.xxh32_intdigest(bs, 0),
           "mmh3_9747": mmh3.hash(bs, 0x9747b28c, signed=False), "mmh3_0": mmh3.hash(bs, 0, signed=False)}
    wide = {"xxh3_128": xxhash.xxh3_128_intdigest(bs, 0).to_bytes(16, "little"),
            "xxh3_64": xxhash.xxh3_64_intdigest(bs, 0).to_bytes(8, "little"),
            "xxh64": xxhash.xxh64_intdigest(bs, 0).to_bytes(8, "little"),
            "md5": hashlib.md5(bs).digest(),
            "mmh3_128": mmh3.hash_bytes(bs, 0)}
    for seed in SEEDS:
        out["xxh32_s%x" % seed] = xxhash.xxh32_intdigest(bs, seed)
        out["mmh3_s%x" % seed] = mmh3.hash(bs, seed, signed=False)
        wide["xxh64_s%x" % seed] = xxhash.xxh64_intdigest(bs, seed).to_bytes(8, "little")
        wide["xxh3_64_s%x" % seed] = xxhash.xxh3_64_intdigest(bs, seed).to_bytes(8, "little")
        wide["xxh3_128_s%x" % seed] = xxhash.xxh3_128_intdigest(bs, seed).to_bytes(16, "little")
        wide["mmh3_128_s%x" % seed] = mmh3.hash_bytes(bs, seed)
    for nm, b in wide.items():
        for j in range(0, len(b), 4):
            out["%s[%d]" % (nm, j)] = struct.unpack_from("<I", b, j)[0]
    return out


SEEDS = (0x1eb62c88, 0x22c43571, 0x0b6807cd, 163, 123, 3, 2)


def variants(p):
    a = p.replace("\\", "/")
    parts = a.split("/")
    out = set()
    for b in {a, "/".join(parts[1:]), "res/" + a}:
        for s in (b, b.lower()):
            out.add(s); out.add(s.replace("/", "\\"))
    return out


if __name__ == "__main__":
    thh = open(sys.argv[1], "rb").read(); thy = open(sys.argv[2], "rb").read()
    dh, sh, n = main_vector(thh, 4)
    dy, sy, n2 = main_vector(thy, 32)
    assert n == n2, (n, n2)
    hv = u32vec(dh, sh, n)
    recs = [struct.unpack_from("<4I16s", dy, sy + 32 * i) for i in range(n)]
    # 前缀子表: T.f1 -> 子表, 找其中长度为 n 的 u32 向量
    print("n =", n, " thh sorted:", hv == sorted(hv), " thh distinct:", len(set(hv)))
    pools = {"thh": {v: i for i, v in enumerate(hv)},
             "thy_f1": {r[1]: i for i, r in enumerate(recs)}}
    for path in sys.argv[3:]:
        hit = False
        for v in variants(path):
            for hn, hval in cand_hashes(v).items():
                for pn, pool in pools.items():
                    if hval in pool:
                        i = pool[hval]
                        print("HIT %s %s %r -> #%d md5=%s rawlen=%d" % (pn, hn, v, i, recs[i][4].hex(), recs[i][3]))
                        hit = True
        if not hit: print("miss", path)
