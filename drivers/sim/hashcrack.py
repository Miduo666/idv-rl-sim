# -*- coding: utf-8 -*-
"""用 (路径 -> 内容MD5) 样本 + thd 清单，反推路径哈希。
样本: manifest.jsonl 的 path/used/md5；清单: scene.thy(MD5->序号i) / scene.thh(i->指纹) / 前缀表 f0[i]。
对一批哈希函数 × 路径变体，统计与 指纹 / thy第2字段 / f0[i] / i 的命中数。"""
import sys, os, json, struct, zlib, hashlib, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thfb
import xxhash, mmh3

man_p, thh_p, thy_p = sys.argv[1:4]
raw_h = open(thh_p, "rb").read(); raw_y = open(thy_p, "rb").read()
dh = raw_h[8:]; dy = raw_y[8:]
T = 0x20
qv = T + 4 + thfb.u32(dh, T + 4); n = thfb.u32(dh, qv); sh = qv + 4
qy = T + 4 + thfb.u32(dy, T + 4); sy = qy + 4
fp = struct.unpack_from("<%dI" % n, dh, sh)
recs = [struct.unpack_from("<4I16s", dy, sy + 32 * i) for i in range(n)]
md5_to_i = {r[4]: i for i, r in enumerate(recs)}
# 前缀子表 f0
ps = 0x38
vt = ps - thfb.i32(dh, ps)
off0 = thfb.u16(dh, vt + 4)
q0 = ps + off0 + thfb.u32(dh, ps + off0)
f0 = struct.unpack_from("<%dI" % thfb.u32(dh, q0), dh, q0 + 4)
seeds = struct.unpack_from("<3I", dh, 0x58)

samples = []
for l in open(man_p, encoding="utf-8"):
    m = json.loads(l)
    k = bytes.fromhex(m["md5"])
    if k in md5_to_i:
        i = md5_to_i[k]
        samples.append((m["path"], m["used"], i))
print("samples in this package:", len(samples), " n =", n, " seeds", [hex(s) for s in seeds])
S = samples[:200]


def fnv1a32(b, h=2166136261):
    for c in b: h = ((h ^ c) * 16777619) & 0xFFFFFFFF
    return h
def fnv1_32(b, h=2166136261):
    for c in b: h = ((h * 16777619) & 0xFFFFFFFF) ^ c
    return h
def fnv1a64(b, h=14695981039346656037):
    for c in b: h = ((h ^ c) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h
def djb2(b, h=5381):
    for c in b: h = (h * 33 + c) & 0xFFFFFFFF
    return h
def sdbm(b, h=0):
    for c in b: h = (c + (h << 6) + (h << 16) - h) & 0xFFFFFFFF
    return h
def bkdr(b, s=131, h=0):
    for c in b: h = (h * s + c) & 0xFFFFFFFF
    return h
def java(b, h=0):
    for c in b: h = (31 * h + c) & 0xFFFFFFFF
    return h


def wide_parts(name, v, nbytes):
    bs = v.to_bytes(nbytes, "little")
    return {"%s[%d]" % (name, j): struct.unpack_from("<I", bs, j)[0] for j in range(0, nbytes, 4)}


def all_hashes(s):
    b = s.encode("utf-8")
    out = {"fnv1a32": fnv1a32(b), "fnv1_32": fnv1_32(b), "djb2": djb2(b), "sdbm": sdbm(b), "bkdr131": bkdr(b),
           "java": java(b), "crc32": zlib.crc32(b), "adler32": zlib.adler32(b),
           "xxh32": xxhash.xxh32_intdigest(b, 0), "mmh3": mmh3.hash(b, 0, signed=False),
           "mmh3_9747": mmh3.hash(b, 0x9747b28c, signed=False)}
    out.update(wide_parts("fnv1a64", fnv1a64(b), 8))
    out.update(wide_parts("xxh64", xxhash.xxh64_intdigest(b, 0), 8))
    out.update(wide_parts("xxh3_64", xxhash.xxh3_64_intdigest(b, 0), 8))
    out.update(wide_parts("xxh3_128", xxhash.xxh3_128_intdigest(b, 0), 16))
    out.update(wide_parts("md5", int.from_bytes(hashlib.md5(b).digest(), "little"), 16))
    out.update(wide_parts("sha1", int.from_bytes(hashlib.sha1(b).digest()[:16], "little"), 16))
    out.update(wide_parts("mmh3_128", int.from_bytes(mmh3.hash_bytes(b, 0), "little"), 16))
    for sd in seeds:
        out["xxh32_s%x" % sd] = xxhash.xxh32_intdigest(b, sd)
        out["mmh3_s%x" % sd] = mmh3.hash(b, sd, signed=False)
        out.update(wide_parts("xxh64_s%x" % sd, xxhash.xxh64_intdigest(b, sd), 8))
        out.update(wide_parts("xxh3_64_s%x" % sd, xxhash.xxh3_64_intdigest(b, sd), 8))
    return out


def variants(path, used):
    a = path
    parts = a.split("/")
    base = {a, used, "/".join(parts[1:]), "res/" + a, "/" + a, a.rsplit(".", 1)[0], "/".join(parts[1:]).rsplit(".", 1)[0]}
    out = {}
    for b in base:
        for tag, s in (("", b), ("L", b.lower()), ("U", b.upper())):
            out[tag + "/:" + s] = s
            out[tag + "\\:" + s.replace("/", "\\")] = s.replace("/", "\\")
    return out


targets = {"fp": lambda i: fp[i], "thy1": lambda i: recs[i][1], "f0": lambda i: f0[i] if i < len(f0) else None,
           "i": lambda i: i}
hits = {}
for path, used, i in S:
    tv = {k: f(i) for k, f in targets.items()}
    for vname, s in variants(path, used).items():
        vk = vname.split(":")[0]
        for hn, hv in all_hashes(s).items():
            for tn, tval in tv.items():
                if hv == tval or (tn == "i" and hv % n == i):
                    key = (vk, hn, tn)
                    hits[key] = hits.get(key, 0) + 1
print("top hits (variant, hash, target) / %d samples:" % len(S))
for k, c in sorted(hits.items(), key=lambda x: -x[1])[:15]:
    print("  %4d  %s" % (c, k))
