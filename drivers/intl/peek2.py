# -*- coding: utf-8 -*-
"""完整打印一个 pydata marshal 的 co_consts（递归进嵌套 code）。用法: python -I peek2.py <file.marshal> [最多条数]"""
import sys, marshal, types
sys.stdout.reconfigure(encoding="utf-8")
co = marshal.loads(open(sys.argv[1], "rb").read())
lim = int(sys.argv[2]) if len(sys.argv) > 2 else 400
n = [0]
def walk(c, depth):
    print("  " * depth + "<code %s> names=%s" % (c.co_name, c.co_names[:30]))
    for i, x in enumerate(c.co_consts):
        if isinstance(x, types.CodeType):
            walk(x, depth + 1); continue
        n[0] += 1
        if n[0] > lim: return
        print("  " * depth + "%d %s %s" % (i, type(x).__name__, repr(x)[:200]))
walk(co, 0)
