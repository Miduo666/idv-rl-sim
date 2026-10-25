# -*- coding: utf-8 -*-
"""纯 Python 的 CPython 3.11 marshal 读取器。
不构造真实 code object（游戏的乱序字节码会让 CPython 堆崩溃），code 读成 RawCode。"""
import struct


class RawCode:
    __slots__ = ("argcount", "posonlyargcount", "kwonlyargcount", "stacksize", "flags",
                 "code", "consts", "names", "localsplusnames", "localspluskinds",
                 "filename", "name", "qualname", "firstlineno", "linetable", "exceptiontable")

    def __repr__(self):
        return "<RawCode %s>" % self.qualname


class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0
        self.refs = []
        self.code_spans = []   # 每个 code object 的 co_code 字节在流里的 (起点, 长度)

    def byte(self):
        b = self.d[self.p]
        self.p += 1
        return b

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def raw(self, n):
        v = self.d[self.p:self.p + n]
        self.p += n
        return v

    def obj(self):
        code = self.byte()
        flag = code & 0x80
        t = chr(code & 0x7F)
        idx = None
        if flag:
            idx = len(self.refs)
            self.refs.append(None)
        v = self._read(t)
        if flag:
            self.refs[idx] = v
        return v

    def _read(self, t):
        if t == "0": return None          # NULL
        if t == "N": return None
        if t == "F": return False
        if t == "T": return True
        if t == "S": return StopIteration
        if t == ".": return Ellipsis
        if t == "i": return self.i32()
        if t == "g": return struct.unpack("<d", self.raw(8))[0]
        if t == "y": return complex(*struct.unpack("<dd", self.raw(16)))
        if t == "l":
            n = self.i32()
            sign = -1 if n < 0 else 1
            v = 0
            for k in range(abs(n)):
                d = struct.unpack("<H", self.raw(2))[0]
                v |= d << (15 * k)
            return sign * v
        if t == "s": return bytes(self.raw(self.i32()))
        if t in "tu": return self.raw(self.i32()).decode("utf-8", "surrogatepass")
        if t in "aA": return self.raw(self.i32()).decode("latin1")
        if t in "zZ": return self.raw(self.byte()).decode("latin1")
        if t == "r": return self.refs[self.i32()]
        if t == ")": return tuple(self.obj() for _ in range(self.byte()))
        if t == "(": return tuple(self.obj() for _ in range(self.i32()))
        if t == "[": return [self.obj() for _ in range(self.i32())]
        if t in "<>":
            items = [self.obj() for _ in range(self.i32())]
            return frozenset(items) if t == ">" else set(items)
        if t == "{":
            dct = {}
            while True:
                k = self.obj()
                if k is None and self.d[self.p - 1] == ord("0"):
                    break
                dct[k] = self.obj()
            return dct
        if t == "c":
            c = RawCode()
            c.argcount = self.i32(); c.posonlyargcount = self.i32()
            c.kwonlyargcount = self.i32(); c.stacksize = self.i32(); c.flags = self.i32()
            t0 = self.d[self.p] & 0x7F
            if t0 == ord("s"):
                n = struct.unpack_from("<i", self.d, self.p + 1)[0]
                self.code_spans.append((self.p + 5, n))
            c.code = self.obj(); c.consts = self.obj(); c.names = self.obj()
            c.localsplusnames = self.obj(); c.localspluskinds = self.obj()
            c.filename = self.obj(); c.name = self.obj(); c.qualname = self.obj()
            c.firstlineno = self.i32(); c.linetable = self.obj(); c.exceptiontable = self.obj()
            return c
        raise ValueError("unknown marshal type %r at %d" % (t, self.p - 1))


def load_pyc(path):
    data = open(path, "rb").read()
    return Reader(data[16:]).obj()


def iter_codes(c):
    yield c
    for k in c.consts:
        if isinstance(k, RawCode):
            yield from iter_codes(k)
