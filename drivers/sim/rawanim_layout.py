# -*- coding: utf-8 -*-
"""验证 RAWANIMA DATA 块布局假设：逐骨骼 T(half3)/R(u32) 关键帧轨道，看每个文件是否恰好解析到 DATA 结尾。
用法: rawanim_layout.py <idx> [最多文件数]"""
import sys, os, types, logging, struct, collections
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.normpath(os.path.join(HERE, "..", "..", "tools", "NeoXtractor-IDXWPK"))
sys.path.insert(0, TOOL)
logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile


def chunks(d):
    n, = struct.unpack_from("<I", d, 0x28)
    o = 0x2c + n
    out = {}
    while o + 8 <= len(d):
        tag = d[o:o + 4]; sz, = struct.unpack_from("<I", d, o + 4)
        out[tag] = (o + 8, sz)
        o += 8 + sz
    return out


def bone_count(d, name):
    o, sz = name
    cnt, = struct.unpack_from("<I", d, o)
    return cnt - 1  # 第一个串是源动画名


def parse_tracks(d, o, end, nb):
    """按假设布局解析 nb 根骨骼，返回 (结束偏移, 每骨骼(nT,nR))；越界抛异常。"""
    tracks = []
    for b in range(nb):
        ns = []
        for w in (6, 6, 4):  # T(half3) S(half3) R(4 字节)：u16 计数 + 计数×(u16 帧号, 值)
            n, = struct.unpack_from("<H", d, o); o += 2
            o += n * (2 + w)
            ns.append(n)
        if o > end:
            raise ValueError("bone %d 越界" % b)
        tracks.append(tuple(ns))
    return o, tracks


def main():
    f = IDXWPKFile(sys.argv[1])
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9
    stat = collections.Counter()
    first = collections.Counter()
    samples = collections.defaultdict(list)
    k = 0
    for i in range(len(f.indices)):
        try:
            d = f.read_entry(i).data or b""
        except Exception:
            continue
        if d[:8] != b"RAWANIMA":
            continue
        c = chunks(d)
        fmt = d[c[b"HEAD"][0] + 16]
        stat["格式%d" % fmt] += 1
        if fmt != 2:
            continue
        k += 1
        if k > lim:
            break
        o, sz = c[b"DATA"]
        nb = bone_count(d, c[b"NAME"])
        first[d[o]] += 1
        try:
            e, tr = parse_tracks(d, o + 1, o + sz, nb)
            tail = d[e:o + sz]
            r = "恰好" if not tail else ("剩 %d" % len(tail) if tail.strip(b"\0") or len(tail) >= 16 else "恰好(补零%d)" % len(tail))
        except Exception as ex:
            r = "失败"
            samples[r].append((i, str(ex)))
        stat["失败" if r == "失败" else ("恰好" if r.startswith("恰好") else "有剩余")] += 1
        if r.startswith("剩"):
            samples["有剩余"].append((i, r, nb))
    print("文件", k, dict(stat))
    print("DATA 首字节", first.most_common(10))
    for kk, v in samples.items():
        print(kk, v[:8])


if __name__ == "__main__":
    main()
