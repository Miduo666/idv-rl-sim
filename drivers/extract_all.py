# -*- coding: utf-8 -*-
"""全量解包 script.idx+wpk，导出脚本清单，按关键词筛反作弊相关脚本并存盘。"""
import sys, os, marshal, logging, types, re, time

TOOL = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-Code-For-id5-IdentityV\9bb7127c-1569-42a0-8b5a-10fefea52810\scratchpad\tools\NeoXtractor-IDXWPK"
IDX  = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-Code-For-id5-IdentityV\9bb7127c-1569-42a0-8b5a-10fefea52810\scratchpad\apk_npk\script.idx"
OUT  = r"C:\Users\31297\AppData\Local\Temp\claude\C--Users-31297-Desktop-Code-For-id5-IdentityV\9bb7127c-1569-42a0-8b5a-10fefea52810\scratchpad\extracted_scripts"
sys.path.insert(0, TOOL)
logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile

# 文件名正则命中（反作弊/安全/检测相关）
NAME_RE = re.compile(rb"anti|cheat|secur|guard|detect|integrity|protect|tamper|mem_?modify|speed|hack|verify|sign|check", re.I)
# 原始 marshal 字节里的强特征（即使文件名不显眼也抓）
BYTE_KEYS = [b"AntiMemModify", b"anti_mem_modify", b"anti_move_speed_cheat", b"MemModify",
             b"/proc/", b"ptrace", b"TracerPid", b"\xe6\xa3\x80\xe6\xb5\x8b",  # “检测”
             b"\xe4\xbf\xae\xe6\x94\xb9\xe5\xae\xa2\xe6\x88\xb7\xe7\xab\xaf"]  # “修改客户端”

def try_marshal(d):
    for blob in (d, d[16:]):
        try:
            co = marshal.loads(blob)
            if hasattr(co, "co_filename"):
                return co, blob
        except Exception:
            pass
    return None, None

def main():
    f = IDXWPKFile(IDX)
    n = len(f.indices)
    names = []
    flagged = []
    t0 = time.time(); fail = 0
    for i in range(n):
        try:
            e = f.read_entry(i)
            d = e.data or b""
        except Exception:
            fail += 1; continue
        co, blob = try_marshal(d)
        if not co:
            # 非脚本资源，跳过（记名用 hash）
            continue
        cof = co.co_filename or ""
        names.append(cof)
        cb = cof.encode("utf-8", "replace")
        hit_name = NAME_RE.search(cb)
        hit_byte = next((k for k in BYTE_KEYS if k in blob), None)
        if hit_name or hit_byte:
            flagged.append((i, cof, len(blob), bool(hit_name), hit_byte))
            # 存盘（原始 marshal blob）
            safe = cof.replace("\\", "/")
            outp = os.path.join(OUT, safe)
            os.makedirs(os.path.dirname(outp), exist_ok=True)
            with open(outp + ".marshal", "wb") as w:
                w.write(blob)
        if (i+1) % 2000 == 0:
            print("...%d/%d  (%.0fs)" % (i+1, n, time.time()-t0), flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "_all_filenames.txt"), "w", encoding="utf-8") as w:
        w.write("\n".join(sorted(names)))
    print("\n=== 完成: %d 条目, 脚本 %d, 读失败 %d, 用时 %.0fs ===" % (n, len(names), fail, time.time()-t0))
    print("=== 反作弊/安全相关命中 %d 个 ===" % len(flagged))
    for i, cof, ln, hn, hb in sorted(flagged, key=lambda x: x[1]):
        print("  [%5d] %-70s len=%-7d name=%s byte=%s" % (i, cof, ln, hn, hb.decode('latin1') if hb else '-'))

if __name__ == "__main__":
    main()
