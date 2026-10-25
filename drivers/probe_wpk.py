# -*- coding: utf-8 -*-
"""无 GUI 驱动：用 NeoXtractor-IDXWPK 的 core.wpk 解 script.idx+wpk，验证能否解出 marshal。"""
import sys, os, marshal, logging

TOOL = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-Code-For-id5-IdentityV\9bb7127c-1569-42a0-8b5a-10fefea52810\scratchpad\tools\NeoXtractor-IDXWPK"
IDX  = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-Code-For-id5-IdentityV\9bb7127c-1569-42a0-8b5a-10fefea52810\scratchpad\apk_npk\script.idx"
sys.path.insert(0, TOOL)
logging.disable(logging.INFO)

# 桩掉 GUI 耦合的 core.logger，避免拉 PySide6
import types
_stub = types.ModuleType("core.logger")
_stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub

from core.wpk.wpk_file import IDXWPKFile

def try_marshal(d):
    for blob in (d, d[16:]):
        try:
            co = marshal.loads(blob)
            if hasattr(co, "co_filename"):
                return co
        except Exception:
            pass
    return None

def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    f = IDXWPKFile(IDX)
    print("total entries:", len(f.indices))
    ok = 0
    for i in range(min(N, len(f.indices))):
        try:
            e = f.read_entry(i)
        except Exception as ex:
            print(i, "READ-ERROR", repr(ex)[:120]); continue
        d = e.data or b""
        co = try_marshal(d)
        cof = getattr(co, "co_filename", None) if co else None
        if co:
            ok += 1
        print("%-5d pkg=%s len=%-7d ext=%-5s tag=%s unwrap=%s head=%s co_filename=%r" % (
            i, getattr(e, "pkg_id", "?"), len(d), e.extension,
            getattr(e, "stage1_tag", None), getattr(e, "unwrap_layers", None),
            d[:12].hex(), cof))
    print("marshal-decoded: %d / %d" % (ok, min(N, len(f.indices))))

if __name__ == "__main__":
    main()
