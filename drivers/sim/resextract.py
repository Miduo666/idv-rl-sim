# -*- coding: utf-8 -*-
"""按序号从 idx+wpk 资源包里解出条目。用法: resextract.py <idx> <输出目录> <序号...>"""
import sys, os, types, logging
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.normpath(os.path.join(HERE, "..", "..", "tools", "NeoXtractor-IDXWPK"))
sys.path.insert(0, TOOL)
logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile

f = IDXWPKFile(sys.argv[1])
os.makedirs(sys.argv[2], exist_ok=True)
for s in sys.argv[3:]:
    i = int(s)
    d = f.read_entry(i).data
    p = os.path.join(sys.argv[2], "%d_%s.bin" % (i, f.indices[i].raw_hash_hex))
    open(p, "wb").write(d)
    print(i, len(d), p)
