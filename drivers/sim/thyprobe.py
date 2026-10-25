# -*- coding: utf-8 -*-
"""thy 记录 = MD5(16) + 4×u32。把索引里每个条目在 thy 里的记录找出来，拿候选路径的 32 位哈希去匹配第 2 个 u32。"""
import sys, os, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from residx import read_idx
import xxhash, mmh3

thy = open(sys.argv[1], "rb").read()
idx = read_idx(sys.argv[2], 0x20, 0x24)
pos = {}
for k in idx:
    p = thy.find(k)
    if p >= 0:
        pos[k] = p
print("idx keys found in thy: %d / %d" % (len(pos), len(idx)))
mods = collections.Counter(p % 32 for p in pos.values())
print("pos %% 32:", mods.most_common(4))
rec = {}
for k, p in pos.items():
    f = struct.unpack_from("<4I", thy, p - 16)
    for j in range(4):
        rec.setdefault(j, {})[f[j]] = (k, f)
print("distinct per field:", {j: len(rec[j]) for j in rec})
ks = list(pos)[:3]
for k in ks:
    print("  sample", thy[pos[k]-16:pos[k]].hex(), k.hex(), idx[k]["payload"])

def fnv1a32(bs):
    h = 2166136261
    for c in bs:
        h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return h


def fnv1_32(bs):
    h = 2166136261
    for c in bs:
        h = ((h * 16777619) & 0xFFFFFFFF) ^ c
    return h


def hashes(s):
    bs = s.encode("utf-8")
    yield "fnv1a32", fnv1a32(bs)
    yield "fnv1_32", fnv1_32(bs)
    yield "xxh32_0", xxhash.xxh32_intdigest(bs, 0)
    yield "mmh3_9747b28c", mmh3.hash(bs, 0x9747b28c, signed=False)
    yield "mmh3_0", mmh3.hash(bs, 0, signed=False)

def variants(p):
    a = p.replace("\\", "/")
    parts = a.split("/")
    bases = {a, "/".join(parts[1:]), "/".join(parts[2:]), "res/" + a, "/" + a, "./" + a}
    out = set()
    for b in bases:
        for s in (b, b.lower(), b.upper()):
            out.add(s); out.add(s.replace("/", "\\"))
    return out

for p in sys.argv[3:]:
    hit = False
    for v in variants(p):
        for n, h in hashes(v):
            for j in rec:
                if h in rec[j]:
                    k, f = rec[j][h]
                    print("HIT field%d %s %r -> md5 %s fields=%s payload=%d" % (j, n, v, k.hex(), [hex(x) for x in f], idx[k]["payload"]))
                    hit = True
    if not hit:
        print("miss", p)
