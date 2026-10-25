# -*- coding: utf-8 -*-
"""从 std_pyc 重建 idx.tsv（idxq.py / usage.py 用）。每行: 相对路径 \t 名字 | def:限定名 | s:字符串常量 ...（去重排序）
用法: python make_idx.py [输出路径]"""
import os, sys, marshal
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "std_pyc"))


def tokens(co, out):
    out.update(co.co_names)
    out.add("def:" + co.co_qualname)
    for k in co.co_consts:
        if hasattr(k, "co_code"):
            tokens(k, out)
        elif isinstance(k, str) and k.strip():
            out.add("s:" + k.replace("\t", " ").replace("\n", " ").replace("\r", " "))


def main(dst):
    n = 0
    # 少数字符串常量含孤立代理字符（\ud800），utf-8 写不出，转义保留
    with open(dst, "w", encoding="utf-8", errors="backslashreplace", newline="") as f:
        for dp, dn, fn in os.walk(ROOT):
            dn.sort()
            for name in sorted(fn):
                if not name.endswith(".pyc"): continue
                p = os.path.join(dp, name)
                try:
                    co = marshal.loads(open(p, "rb").read()[16:])
                except Exception:
                    continue
                t = set(); tokens(co, t)
                f.write("%s\t%s\n" % (os.path.relpath(p, ROOT).replace(os.sep, "/"), " | ".join(sorted(t))))
                n += 1
    print("写入 %d 行 -> %s" % (n, dst))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "idx.tsv"))
