# -*- coding: utf-8 -*-
"""把 NeoX 乱序操作码还原成规范 3.11 操作码并反汇编指定函数。
用法: python deobf.py <file.pyc|.marshal> <函数qualname子串>
映射表来自 denpk2 src/opcode/mapping.rs (opcode_names.txt)。"""
import sys, os, marshal, dis, opcode, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = open(os.path.join(HERE, "opcode_names.txt")).read().split()
assert len(NAMES) == 256, len(NAMES)
OPMAP = opcode.opmap
CACHE = getattr(opcode, "_inline_cache_entries", [0] * 256)

def canon(b):
    """乱序字节 b -> (规范操作码号 or None, 规范名)"""
    name = NAMES[b]
    return OPMAP.get(name), name

def remap(co):
    code = bytearray(co.co_code)
    i = 0
    n = len(code)
    while i < n:
        op, name = canon(code[i])
        if op is not None:
            code[i] = op
            ncache = CACHE[op] if op < len(CACHE) else 0
        else:
            ncache = 0  # 特化/未知: 不应出现在磁盘码里
        i += 2 + 2 * ncache
    new_consts = tuple(remap(c) if hasattr(c, "co_code") else c for c in co.co_consts)
    return co.replace(co_code=bytes(code), co_consts=new_consts)

def load(path):
    data = open(path, "rb").read()
    for blob in (data, data[16:]):
        try:
            co = marshal.loads(blob)
            if hasattr(co, "co_filename"):
                return co
        except Exception:
            pass
    raise SystemExit("not a code object")

def find(co, sub, out):
    qn = getattr(co, "co_qualname", co.co_name)
    if sub.lower() in qn.lower():
        out.append(co)
    for c in co.co_consts:
        if hasattr(c, "co_code"):
            find(c, sub, out)

def main():
    path, sub = sys.argv[1], sys.argv[2]
    root = remap(load(path))
    hits = []
    find(root, sub, hits)
    if not hits:
        print("no function matching:", sub); return
    for co in hits:
        print("\n" + "=" * 80)
        print("## %s   (consts=%s)" % (getattr(co, "co_qualname", co.co_name),
                                       [repr(c) for c in co.co_consts if not hasattr(c, "co_code")]))
        print("=" * 80)
        try:
            dis.dis(co, depth=0)
        except Exception as e:
            print("dis failed:", repr(e))

if __name__ == "__main__":
    main()
