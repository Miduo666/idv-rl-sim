# -*- coding: utf-8 -*-
"""恢复没写中央目录的 zip（ZIP_STORED）：扫本地文件头逐条取出，重新写成完整 zip，并与 manifest 对账。
用法: zip_recover.py <坏zip> <manifest.jsonl> <输出zip>"""
import sys, struct, zipfile, json, hashlib

src, man, dst = sys.argv[1:4]
d = open(src, "rb").read()
p = 0
ents = {}
bad = 0
while True:
    p = d.find(b"PK\x03\x04", p)
    if p < 0:
        break
    try:
        (_, ver, flag, meth, mt, md, crc, csz, usz, nl, xl) = struct.unpack_from("<IHHHHHIIIHH", d, p)
        name = d[p + 30:p + 30 + nl].decode("utf-8")
        off = p + 30 + nl + xl
        if xl and usz == 0xFFFFFFFF:            # zip64 扩展字段
            ex = d[p + 30 + nl:off]
            q = 0
            while q + 4 <= len(ex):
                hid, hsz = struct.unpack_from("<HH", ex, q)
                if hid == 1:
                    usz, csz = struct.unpack_from("<QQ", ex, q + 4)
                q += 4 + hsz
        if meth != 0 or off + csz > len(d):
            bad += 1; p += 4; continue
        ents[name] = d[off:off + csz]
        p = off + csz
    except Exception:
        bad += 1; p += 4
mf = [json.loads(l) for l in open(man, encoding="utf-8") if l.strip()]
want = {m["path"]: m for m in mf}
ok = sum(1 for n, b in ents.items() if n in want and hashlib.md5(b).hexdigest() == want[n]["md5"])
with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
    for n, b in ents.items():
        z.writestr(n, b)
print("recovered entries:", len(ents), " bad headers:", bad)
print("manifest lines:", len(mf), " md5-verified:", ok, " in zip but not manifest:", len(set(ents) - set(want)), " in manifest but not zip:", len(set(want) - set(ents)))
