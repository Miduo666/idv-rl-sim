# -*- coding: utf-8 -*-
r"""在 heap_dump.py 拉下来的堆快照里离线搜索。

    python heap_find.py str fix_process hack_process        # 找字符串
    python heap_find.py ptr 0x73cdfcab50 ...                # 找指向某地址的指针(含0xB4标签)
    python heap_find.py f32 -513.35 -520.03                 # 找浮点值(带容差)
    python heap_find.py f64 100.0 25.0

不碰活体内存，纯本地文件操作，想搜几次搜几次。
"""
import sys, os, struct, bisect

sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
from devread import TMP


class _Image:
    """一个 (blob, 索引) 对。多次 heap_dump（不同 --tag）产生多个镜像，合起来用。"""

    def __init__(self, base):
        self.blob = open(base + ".bin", "rb").read()
        self.segs = []          # (vaddr, file_off, length)
        for ln in open(base + ".idx"):
            v, o, n = ln.split()
            self.segs.append((int(v, 16), int(o), int(n)))
        self.segs.sort()
        self.vs = [s[0] for s in self.segs]
        self.offs = sorted((o, v, n) for v, o, n in self.segs)
        self.ostarts = [x[0] for x in self.offs]
        self.name = os.path.basename(base)

    def off2va(self, off):
        i = bisect.bisect_right(self.ostarts, off) - 1
        if i < 0:
            return None
        o, v, n = self.offs[i]
        return v + (off - o) if off < o + n else None

    def va2off(self, va):
        i = bisect.bisect_right(self.vs, va) - 1
        if i < 0:
            return None
        v, o, n = self.segs[i]
        return o + (va - v) if va < v + n else None


class Heap:
    def __init__(self, pid=None):
        idxs = sorted(f for f in os.listdir(TMP) if f.startswith("heap_") and f.endswith(".idx")
                      and (pid is None or f.startswith("heap_%s" % pid)))
        if not idxs:
            sys.exit("没有堆快照，先跑 heap_dump.py")
        self.imgs = [_Image(os.path.join(TMP, f[:-4])) for f in idxs]
        for im in self.imgs:
            print("镜像 %-22s %7.1f MB, %5d 段, 0x%X-0x%X"
                  % (im.name, len(im.blob) / 1048576.0, len(im.segs),
                     im.vs[0], im.segs[-1][0] + im.segs[-1][2]))

    def read(self, va, n):
        for im in self.imgs:
            o = im.va2off(va)
            if o is not None and o + n <= len(im.blob):
                return im.blob[o:o + n]
        return None

    def findall(self, pat, align=1, limit=200):
        out = []
        for im in self.imgs:
            o = im.blob.find(pat)
            while o != -1 and len(out) < limit:
                va = im.off2va(o)
                if va is not None and va % align == 0:
                    out.append(va)
                o = im.blob.find(pat, o + 1)
        return sorted(set(out))

    def region_of(self, va):
        for im in self.imgs:
            if im.va2off(va) is not None:
                return im.name
        return None


if __name__ == "__main__":
    h = Heap()
    mode = sys.argv[1] if len(sys.argv) > 1 else "str"
    args = sys.argv[2:]
    if mode == "str":
        for s in args:
            pat = s.encode() + b"\0"
            hits = h.findall(pat)
            print("\n'%s' : %d 处" % (s, len(hits)))
            for va in hits[:40]:
                print("    0x%X" % va)
    elif mode == "ptr":
        for a in args:
            anc = int(a, 16)
            for tag, val in (("裸", anc), ("0xB4标签", anc | 0xB4 << 56)):
                hits = h.findall(struct.pack("<Q", val), align=8)
                if hits:
                    print("\n0x%X (%s) 被 %d 处引用:" % (anc, tag, len(hits)))
                    for va in hits[:40]:
                        print("    0x%X" % va)
    elif mode in ("f32", "f64"):
        fmt, sz, tol = ("<f", 4, 0.02) if mode == "f32" else ("<d", 8, 1e-9)
        for a in args:
            t = float(a)
            found = []
            for o in range(0, len(h.blob) - sz, 4):
                v = struct.unpack_from(fmt, h.blob, o)[0]
                if v == v and abs(v - t) <= max(tol, abs(t) * 1e-6):
                    va = h.off2va(o)
                    if va is not None:
                        found.append((va, v))
                    if len(found) > 200:
                        break
            print("\n%s == %s : %d 处" % (mode, a, len(found)))
            for va, v in found[:40]:
                print("    0x%X = %r" % (va, v))
