# -*- coding: utf-8 -*-
"""递归 dump marshal code object 的结构(名字/字符串常量/嵌套函数)，不依赖 dis。"""
import sys, marshal, io

def walk(co, depth, out):
    pad = "    " * depth
    qn = getattr(co, "co_qualname", co.co_name)
    out.append("%sdef %s(args=%d)  vars=%s" % (pad, qn, co.co_argcount, list(co.co_varnames)))
    if co.co_names:
        out.append("%s  .names/attrs: %s" % (pad, list(co.co_names)))
    strs = [c for c in co.co_consts if isinstance(c, str) and c.strip()]
    if strs:
        for s in strs:
            out.append("%s  str: %r" % (pad, s))
    nums = [c for c in co.co_consts if isinstance(c, (int, float, bytes)) and not isinstance(c, bool)]
    if nums:
        out.append("%s  nums/bytes: %s" % (pad, nums))
    for c in co.co_consts:
        if hasattr(c, "co_code"):
            walk(c, depth + 1, out)

def main():
    out = []
    for path in sys.argv[1:]:
        out.append("\n" + "=" * 90)
        out.append("FILE: " + path)
        out.append("=" * 90)
        blob = open(path, "rb").read()
        co = marshal.loads(blob)
        out.append("co_filename: %s" % co.co_filename)
        walk(co, 0, out)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("\n".join(out))

if __name__ == "__main__":
    main()
