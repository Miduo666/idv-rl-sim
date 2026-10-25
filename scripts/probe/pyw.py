# -*- coding: utf-8 -*-
r"""CPython 活体行走的公共工具: 批量预取 + 容忍换出页的 dict/str 读取。

devread 的 fetch 是"一次调用批量取页"，所以所有遍历都必须先收集地址再一次性 fetch，
逐地址读会退化成成百上千次 adb 往返。整块 m.get 又会因为中间有换出页而整体失败，
所以这里一律按条目粒度读、坏的跳过。
"""
import struct
import sys
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
from devread import Mem, PAGE

MASK = 0x00FFFFFFFFFFFFFF


class Py:
    def __init__(self, pid, libbase):
        self.m = Mem(pid)
        self.m.quiet = True
        self.libbase = libbase

    def fetch(self, addrs, span=0x40):
        pgs = set()
        for a in addrs:
            if a:
                for k in range(0, span + PAGE, PAGE):
                    pgs.add((a + k) // PAGE * PAGE)
        self.m.fetch(sorted(pgs), "")

    def get(self, va, n):
        return self.m.get(va, n)

    def q(self, va):
        b = self.m.get(va, 8)
        return (struct.unpack("<Q", b)[0] & MASK) if b else None

    def qf(self, va):
        self.fetch([va], 8)
        return self.q(va)

    def pystr(self, va, maxlen=200):
        b = self.m.get(va, 0x30)
        if not b:
            return None
        ln = struct.unpack_from("<q", b, 0x10)[0]
        if not (0 < ln < maxlen):
            return None
        s = self.m.get(va + 0x30, ln)
        if not s:
            return None
        try:
            return s.decode("ascii")
        except Exception:
            return None

    def dict_raw(self, D):
        """返回 (entries起始, step, nentries)"""
        self.fetch([D], 0x40)
        b = self.m.get(D, 48)
        if not b:
            return None
        if (struct.unpack_from("<Q", b, 8)[0] & MASK) == 0:
            return None
        K = struct.unpack_from("<Q", b, 0x20)[0] & MASK
        self.fetch([K], 0x40)
        hdr = self.m.get(K, 32)
        if not hdr:
            return None
        idxb, kind = hdr[9], hdr[10]
        nent = struct.unpack_from("<q", hdr, 24)[0]
        if not (0 <= nent < 1 << 22):
            return None
        return K + 32 + (1 << idxb), (24 if kind == 0 else 16), nent

    def dict_pairs(self, D, limit=None):
        """产出 (序号, key指针, value指针)，中间读不到的条目跳过"""
        r = self.dict_raw(D)
        if not r:
            return []
        ent0, step, nent = r
        if limit:
            nent = min(nent, limit)
        self.fetch([ent0], nent * step)
        out = []
        for i in range(nent):
            e = self.m.get(ent0 + i * step, step)
            if not e:
                continue
            if step == 24:
                k = struct.unpack_from("<Q", e, 8)[0] & MASK
                v = struct.unpack_from("<Q", e, 16)[0] & MASK
            else:
                k = struct.unpack_from("<Q", e, 0)[0] & MASK
                v = struct.unpack_from("<Q", e, 8)[0] & MASK
            if k and v:
                out.append((i, k, v))
        return out

    def dict_names(self, D, limit=None):
        """产出 (序号, 名字, value)，名字读不出的跳过"""
        pairs = self.dict_pairs(D, limit)
        self.fetch([k for _, k, _ in pairs], 0x60)
        out = []
        for i, k, v in pairs:
            nm = self.pystr(k)
            if nm:
                out.append((i, nm, v))
        return out

    def dict_entry(self, D, i):
        """只读第 i 条，不碰整个 entries 数组 —— 走缓存序号时全靠它省往返"""
        r = self.dict_raw(D)
        if not r:
            return None, None
        ent0, step, nent = r
        if not (0 <= i < nent):
            return None, None
        e = ent0 + i * step
        self.fetch([e], step)
        b = self.m.get(e, step)
        if not b:
            return None, None
        if step == 24:
            return (struct.unpack_from("<Q", b, 8)[0] & MASK,
                    struct.unpack_from("<Q", b, 16)[0] & MASK)
        return (struct.unpack_from("<Q", b, 0)[0] & MASK,
                struct.unpack_from("<Q", b, 8)[0] & MASK)

    def value_slot(self, D, idx):
        """第 idx 条的 value 字段地址。

        必须**逐实例**算: entries 起始 = keys + 32 + (1<<dk_log2_index_bytes)，
        而同一个类的不同实例，dict 大小(进而 log2_index_bytes)可以不同。
        把一个实例上算出的偏移套到别的实例上，会读到完全无关的属性。
        """
        r = self.dict_raw(D)
        if not r:
            return None
        ent0, step, nent = r
        if not (0 <= idx < nent):
            return None
        return ent0 + idx * step + (8 if step == 16 else 16)

    def dget(self, D, name, hint=None):
        """按名字取。给了 hint 就先试那一条并用名字校验，命中就省掉整表扫描。"""
        if hint is not None:
            k, v = self.dict_entry(D, hint)
            if k and v:
                self.fetch([k], 0x60)
                if self.pystr(k) == name:
                    return hint, v
        for i, nm, v in self.dict_names(D):
            if nm == name:
                return i, v
        return None, None

    def inst_dict(self, obj):
        """managed-dict 实例: dict 指针在对象前 0x18"""
        return self.qf(obj - 0x18)

    def longval(self, va):
        self.fetch([va], 0x20)
        b = self.m.get(va, 32)
        if not b:
            return None
        sz = struct.unpack_from("<q", b, 16)[0]
        if sz == 0:
            return 0
        d = struct.unpack_from("<I", b, 24)[0]
        return d if sz > 0 else -d

    def floatval(self, va):
        self.fetch([va], 0x20)
        b = self.m.get(va, 24)
        return struct.unpack_from("<d", b, 16)[0] if b else None

    def list_items(self, L):
        self.fetch([L], 0x20)
        b = self.m.get(L, 0x20)
        if not b:
            return []
        n = struct.unpack_from("<q", b, 0x10)[0]
        it = struct.unpack_from("<Q", b, 0x18)[0] & MASK
        if not (0 <= n < 100000) or not it:
            return []
        self.fetch([it], n * 8)
        out = []
        for i in range(n):
            e = self.m.get(it + i * 8, 8)
            if e:
                out.append(struct.unpack("<Q", e)[0] & MASK)
        return out
