# -*- coding: utf-8 -*-
"""用脚本包的(条目哈希, co_filename)对，反推资源路径 -> 16 字节哈希的算法。"""
import sys, os, types, logging, hashlib, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.normpath(os.path.join(HERE, "..", "..", "tools", "NeoXtractor-IDXWPK"))
sys.path.insert(0, TOOL); sys.path.insert(0, HERE)
logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile
from rawmarshal import Reader


def pairs(idx, limit):
    f = IDXWPKFile(idx)
    out = []
    for i in range(len(f.indices)):
        ix = f.indices[i]
        try:
            d = f.read_entry(i).data or b""
        except Exception:
            continue
        for b in (d, d[16:]):
            try:
                co = Reader(b).obj()
                fn = co.filename
                break
            except Exception:
                fn = None
        if fn:
            out.append((bytes.fromhex(ix.raw_hash_hex), fn))
            if len(out) >= limit: break
    return out


def candidates(fn):
    base = fn.replace("\\", "/")
    nopy = base[:-3] if base.endswith(".py") else base
    stems = {base, base + "c", nopy, nopy.replace("/", "."), nopy.replace("/", ".") + ".py",
             nopy.replace("/", ".") + ".pyc", nopy + ".pyo", nopy + ".nxs"}
    pres = ["", "script/", "res/", "script\\", "/", "./", "scripts/", "python/", "lib/", "res/script/",
            "assets/res/script/", "packages/python3/"]
    for s, p in itertools.product(stems, pres):
        for v in (p + s, (p + s).replace("/", "\\")):
            for vv in (v, v.lower()):
                yield vv


if __name__ == "__main__":
    ps = pairs(sys.argv[1], 30)
    print("pairs:", len(ps))
    for h, fn in ps[:5]:
        print("  ", h.hex(), fn)
    algos = {
        "md5": lambda b: hashlib.md5(b).digest(),
        "md5r": lambda b: hashlib.md5(b).digest()[::-1],
        "sha1_16": lambda b: hashlib.sha1(b).digest()[:16],
        "sha256_16": lambda b: hashlib.sha256(b).digest()[:16],
        "blake2b16": lambda b: hashlib.blake2b(b, digest_size=16).digest(),
    }
    try:
        import mmh3
        for seed in (0, 1, 0x9747b28c, 0xC58F1A7B, 0x12345678):
            algos["mmh3x64_%x" % seed] = (lambda s: lambda b: mmh3.hash_bytes(b, s, True))(seed)
            algos["mmh3x86_%x" % seed] = (lambda s: lambda b: mmh3.hash_bytes(b, s, False))(seed)
    except ImportError:
        pass
    try:
        import xxhash
        for seed in (0, 1):
            algos["xxh128_%d" % seed] = (lambda s: lambda b: xxhash.xxh128_digest(b, s))(seed)
            algos["xxh128r_%d" % seed] = (lambda s: lambda b: xxhash.xxh128_digest(b, s)[::-1])(seed)
            algos["xxh3_128_%d" % seed] = (lambda s: lambda b: xxhash.xxh3_128_digest(b, s))(seed)
    except ImportError:
        pass
    try:
        import cityhash
        algos["city128"] = lambda b: cityhash.CityHash128(b).to_bytes(16, "little")
        algos["city128be"] = lambda b: cityhash.CityHash128(b).to_bytes(16, "big")
    except ImportError:
        pass
    # 两个 64 位拼起来的情况：分别比前 8/后 8 字节
    half = {}
    for an, af in list(algos.items()):
        pass
    found = 0
    for h, fn in ps:
        for c in candidates(fn):
            for enc in ("utf-8", "utf-16-le"):
                for an, af in algos.items():
                    if af(c.encode(enc)) == h:
                        print("HIT", an, enc, repr(c)); found += 1
    print("hits", found)
