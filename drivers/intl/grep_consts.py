# -*- coding: utf-8 -*-
"""在若干 marshal 的 co_consts(递归)里搜字符串正则，打印命中及其后一个常量。
用法: python -I grep_consts.py <正则> <file.marshal>..."""
import sys, re, marshal, types
sys.stdout.reconfigure(encoding="utf-8")
pat = re.compile(sys.argv[1])
def walk(c, fp):
    cs = c.co_consts
    for i, x in enumerate(cs):
        if isinstance(x, types.CodeType):
            walk(x, fp); continue
        items = x if isinstance(x, tuple) else (x,)
        for y in items:
            if isinstance(y, str) and pat.search(y):
                nxt = cs[i + 1] if i + 1 < len(cs) else None
                print("%s | %r -> %s" % (fp.split("pydata")[-1], y[:80], repr(nxt)[:120]))
for fp in sys.argv[2:]:
    walk(marshal.loads(open(fp, "rb").read()), fp)
