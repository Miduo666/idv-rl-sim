# -*- coding: utf-8 -*-
"""国际服 script.idx 全量过一遍：记全部 co_filename，pydata/ 下的模块存 marshal blob。
用法: python -I gp_extract.py <script.idx> <输出目录>"""
import sys, os, marshal, logging, types
TOOL = r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\tools\NeoXtractor-IDXWPK"
sys.path.insert(0, TOOL); logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile

idx, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
f = IDXWPKFile(idx)
names, bad, saved = [], 0, 0
for i in range(len(f.indices)):
    try:
        d = f.read_entry(i).data or b""
    except Exception:
        bad += 1; continue
    co = None
    for blob in (d, d[16:]):
        try:
            co = marshal.loads(blob); break
        except Exception:
            co = None
    if co is None or not hasattr(co, "co_filename"):
        bad += 1; continue
    fn = co.co_filename.replace("\\", "/")
    names.append(fn)
    if fn.startswith("pydata/"):
        p = os.path.join(out, fn)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p + ".marshal", "wb").write(blob)
        saved += 1
    if i % 2000 == 0:
        print("progress %d/%d" % (i, len(f.indices)), flush=True)
open(os.path.join(out, "_all_filenames.txt"), "w", encoding="utf-8").write("\n".join(sorted(names)))
print("total=%d ok=%d bad=%d pydata_saved=%d" % (len(f.indices), len(names), bad, saved))
