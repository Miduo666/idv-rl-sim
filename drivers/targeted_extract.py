# -*- coding: utf-8 -*-
"""按 co_filename 精确提取若干脚本的 marshal blob，找齐即停。"""
import sys, os, marshal, logging, types
TOOL = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-Code-For-id5-IdentityV\9bb7127c-1569-42a0-8b5a-10fefea52810\scratchpad\tools\NeoXtractor-IDXWPK"
IDX  = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-Code-For-id5-IdentityV\9bb7127c-1569-42a0-8b5a-10fefea52810\scratchpad\apk_npk\script.idx"
OUT  = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-Code-For-id5-IdentityV\9bb7127c-1569-42a0-8b5a-10fefea52810\scratchpad\extracted_scripts"
sys.path.insert(0, TOOL); logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile

targets = set(sys.argv[1:])
pending = set(targets)
f = IDXWPKFile(IDX)
for i in range(len(f.indices)):
    if not pending: break
    try:
        e = f.read_entry(i); d = e.data or b""
    except Exception:
        continue
    for blob in (d, d[16:]):
        try:
            co = marshal.loads(blob)
        except Exception:
            continue
        if hasattr(co, "co_filename") and co.co_filename in pending:
            outp = os.path.join(OUT, co.co_filename.replace("\\", "/"))
            os.makedirs(os.path.dirname(outp), exist_ok=True)
            open(outp + ".marshal", "wb").write(blob)
            print("saved[%d]: %s (%d bytes)" % (i, co.co_filename, len(blob)))
            pending.discard(co.co_filename)
        break
if pending:
    print("NOT FOUND:", pending)
