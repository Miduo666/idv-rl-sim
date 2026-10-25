# -*- coding: utf-8 -*-
"""把游戏 pyc(乱序操作码) 还原成标准 CPython 3.11 code object。
做法: 纯 Python 解 marshal 定位每段 co_code -> 原地把乱序字节换成标准操作码 -> 标准 marshal.loads。
cache 布局与标准 3.11 完全一致(全量 35 万函数实测), 所以跳转/异常表/行号表都不用动。"""
import os, sys, marshal, opcode
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rawmarshal import Reader

_NAMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "opcode_names.txt")
_TABLE = None


def table():
    global _TABLE
    if _TABLE is None:
        names = open(_NAMES).read().split()
        t = bytearray(256)
        for b, nm in enumerate(names):
            t[b] = opcode.opmap.get(nm, 0) if nm != "UNKNOWN" else 0xFF
        _TABLE = bytes(t)
    return _TABLE


def fix_stream(body):
    """body = pyc 去掉 16 字节头后的 marshal 流; 返回操作码已还原的流。"""
    r = Reader(body)
    r.obj()
    out = bytearray(body)
    tb = table()
    for start, n in r.code_spans:
        for i in range(start, start + n, 2):
            op = out[i]
            if op == 0:
                continue               # CACHE
            m = tb[op]
            if m == 0xFF:
                raise ValueError("unknown scrambled opcode %d" % op)
            out[i] = m
    return bytes(out)


def load(path):
    return marshal.loads(fix_stream(open(path, "rb").read()[16:]))


def to_std_pyc(src, dst):
    """写成标准 3.11 pyc(magic 用本机的), 可被 import / dis / 反编译器读取。"""
    import importlib.util
    data = open(src, "rb").read()
    body = fix_stream(data[16:])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(importlib.util.MAGIC_NUMBER + data[4:16] + body)
