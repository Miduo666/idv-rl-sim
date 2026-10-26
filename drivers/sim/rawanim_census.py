# -*- coding: utf-8 -*-
"""一个角色资源包里：全部 RAWANIMA(骨骼路径/源名/帧率/时长) + 全部 AnimationConfig(动画名→文件名/时长)，看两边怎么对应。
用法: rawanim_census.py <idx> <输出.json>"""
import sys, os, types, logging, struct, re, json
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.normpath(os.path.join(HERE, "..", "..", "tools", "NeoXtractor-IDXWPK"))
sys.path.insert(0, TOOL)
logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile


def chunks(d, o):
    while o + 8 <= len(d):
        tag = d[o:o + 4]; sz, = struct.unpack_from("<I", d, o + 4)
        yield tag, o + 8, sz
        o += 8 + sz


def rawanim_info(d):
    n, = struct.unpack_from("<I", d, 0x28)
    info = {"skeleton": d[0x2c:0x2c + n].decode("utf-8", "replace")}
    for tag, o, sz in chunks(d, 0x2c + n):
        if tag == b"HEAD":
            info["fps"], info["dur"] = struct.unpack_from("<2f", d, o)
            info["head"] = d[o:o + sz].hex()
        elif tag == b"DATA":
            info["data_size"] = sz
        elif tag == b"NAME":
            cnt, = struct.unpack_from("<I", d, o)
            l, = struct.unpack_from("<I", d, o + 4)
            info["src"] = d[o + 8:o + 8 + l].decode("utf-8", "replace")
            info["name_cnt"] = cnt
    return info


ANIM_RE = re.compile(rb'<Animation\s+Name="([^"]*)"\s+FileName="([^"]*)"(.*?)/>', re.S)


def main():
    f = IDXWPKFile(sys.argv[1])
    anims, cfgs = [], []
    for i in range(len(f.indices)):
        try:
            d = f.read_entry(i).data or b""
        except Exception:
            continue
        if d[:8] == b"RAWANIMA":
            x = rawanim_info(d); x["i"] = i; x["md5"] = f.indices[i].raw_hash_hex; anims.append(x)
        elif d[:17] == b"<AnimationConfig>":
            ents = []
            for m in ANIM_RE.finditer(d):
                attrs = dict(re.findall(rb'(\w+)="([^"]*)"', m.group(3)))
                ents.append({"name": m.group(1).decode("utf-8", "replace"), "file": m.group(2).decode("utf-8", "replace"),
                             "end": float(attrs.get(b"end_time", b"nan") or "nan"), "start": float(attrs.get(b"start_time", b"0") or 0)})
            cfgs.append({"i": i, "md5": f.indices[i].raw_hash_hex, "anims": ents})
    json.dump({"anims": anims, "cfgs": cfgs}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("RAWANIMA", len(anims), "AnimationConfig", len(cfgs), "条目", sum(len(c["anims"]) for c in cfgs))


if __name__ == "__main__":
    main()
