# -*- coding: utf-8 -*-
"""逐条解开 idx+wpk 资源包，按文件头分类，输出 TSV(序号 哈希 大小 头16字节hex 头部可打印串)。
用法: resclassify.py <idx> <out.tsv>"""
import sys, os, types, logging, collections, time
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.normpath(os.path.join(HERE, "..", "..", "tools", "NeoXtractor-IDXWPK"))
sys.path.insert(0, TOOL)
logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile


def printable(b):
    return "".join(chr(c) if 32 <= c < 127 else "." for c in b)


f = IDXWPKFile(sys.argv[1])
n = len(f.indices)
hist = collections.Counter()
t0 = time.time()
with open(sys.argv[2], "w", encoding="utf-8") as out:
    for i in range(n):
        ix = f.indices[i]
        try:
            d = f.read_entry(i).data or b""
        except Exception as e:
            out.write("%d\t%s\tERR\t%s\n" % (i, ix.raw_hash_hex, type(e).__name__))
            hist["ERR"] += 1
            continue
        head = d[:16]
        mg = printable(d[:4])
        hist[mg] += 1
        out.write("%d\t%s\t%d\t%s\t%s\n" % (i, ix.raw_hash_hex, len(d), head.hex(), printable(d[:48])))
        if i % 10000 == 0:
            print("..%d/%d %.0fs" % (i, n, time.time() - t0), flush=True)
print("done %d in %.0fs" % (n, time.time() - t0))
for k, v in hist.most_common(60):
    print("%7d  %r" % (v, k))
