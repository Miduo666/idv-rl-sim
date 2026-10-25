# -*- coding: utf-8 -*-
"""全量把 script.idx+wpk 里的 17370 个脚本导出为 .pyc(标准头+marshal体)。
用法: python full_extract.py <输出目录>
注意: 操作码是乱序的, 本机 dis 不能直接反汇编; marshal.loads 可读 co_names/co_consts。"""
import sys, os, marshal, logging, types, time, importlib.util

TOOL = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-Code-For-id5-IdentityV\9bb7127c-1569-42a0-8b5a-10fefea52810\scratchpad\tools\NeoXtractor-IDXWPK"
IDX  = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-Code-For-id5-IdentityV\9bb7127c-1569-42a0-8b5a-10fefea52810\scratchpad\apk_npk\script.idx"
sys.path.insert(0, TOOL); logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile

PYC_HEADER = importlib.util.MAGIC_NUMBER + b"\x00" * 12  # 3.11 magic + flags/mtime/size=0

def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    f = IDXWPKFile(IDX)
    n = len(f.indices); ok = 0; skip = 0; t0 = time.time()
    for i in range(n):
        try:
            e = f.read_entry(i); d = e.data or b""
        except Exception:
            skip += 1; continue
        co = blob = None
        for b in (d, d[16:]):
            try:
                c = marshal.loads(b)
                if hasattr(c, "co_filename"):
                    co, blob = c, b; break
            except Exception:
                pass
        if not co:
            skip += 1; continue
        rel = (co.co_filename or ("blob_%d" % i)).replace("\\", "/")
        outp = os.path.join(out, rel + "c")  # .py -> .pyc
        os.makedirs(os.path.dirname(outp), exist_ok=True)
        with open(outp, "wb") as w:
            w.write(PYC_HEADER); w.write(blob)
        ok += 1
        if ok % 2000 == 0:
            print("...%d/%d (%.0fs)" % (ok, n, time.time()-t0), flush=True)
    print("DONE: %d written, %d skipped, %.0fs -> %s" % (ok, skip, time.time()-t0, out), flush=True)

if __name__ == "__main__":
    main()
