# -*- coding: utf-8 -*-
"""按 TID 前缀/正则列出 chs+en。用法: python -I tid_grep.py <tid_chs_en.json> <TID正则> [中文子串正则]"""
import sys, json, re
d = json.load(open(sys.argv[1], encoding="utf-8"))
chs, en = d["chs"], d["en"]
kp = re.compile(sys.argv[2])
vp = re.compile(sys.argv[3]) if len(sys.argv) > 3 else None
for k in sorted(chs):
    if kp.search(k) and (vp is None or vp.search(chs[k])):
        print("%s\t%s\t%s" % (k, chs[k].replace("\n", " ")[:40], (en.get(k) or "").replace("\n", " ")[:60]))
