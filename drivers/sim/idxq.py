# -*- coding: utf-8 -*-
"""查 idx.tsv：哪些脚本里出现某名字/字符串。用法: python idxq.py <正则> [前缀过滤]"""
import sys, os, re
pat = re.compile(sys.argv[1])
pre = sys.argv[2] if len(sys.argv) > 2 else ""
for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "idx.tsv"), encoding="utf-8"):
    f, _, rest = line.partition("\t")
    if not f.startswith(pre): continue
    hit = sorted({t for t in rest.rstrip("\n").split(" | ") if pat.search(t)})
    if hit: print("%-60s %s" % (f, " | ".join(hit)[:200]))
