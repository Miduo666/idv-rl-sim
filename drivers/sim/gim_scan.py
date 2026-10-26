# -*- coding: utf-8 -*-
"""扫一个资源包里所有 .gim（二进制 NeoX 模型描述，含 SkeletonFile/AnimationConfigFile 字段名），
提取引用的 .skeleton / .animconfig 文件名和子网格名，供"模型路径 → 骨骼/动画配置"对应。
另外收集 AnimationConfig 文件的内容 MD5 → 其中动画文件目录。用法: gim_scan.py <idx> <out.json>"""
import sys, os, types, logging, re, json
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.normpath(os.path.join(HERE, "..", "..", "tools", "NeoXtractor-IDXWPK"))
sys.path.insert(0, TOOL)
logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile

STR = re.compile(rb"[\x20-\x7e]{3,}")


def main():
    f = IDXWPKFile(sys.argv[1])
    out = []
    for i in range(len(f.indices)):
        try:
            d = f.read_entry(i).data or b""
        except Exception:
            continue
        if b"SkeletonFile" not in d[:4096] or b"AnimationConfigFile" not in d[:4096]:
            continue
        ss = [m.group().decode() for m in STR.finditer(d)]
        out.append({"i": i, "md5": f.indices[i].raw_hash_hex,
                    "skeleton": [s for s in ss if s.endswith(".skeleton")],
                    "animconfig": [s for s in ss if s.endswith(".animconfig")],
                    "names": [s for s in ss if len(s) < 80][:60]})
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("gim", len(out))


if __name__ == "__main__":
    main()
