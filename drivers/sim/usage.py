# -*- coding: utf-8 -*-
"""找某个调用的结果在调用方怎么被用：python usage.py <调用名正则> [文件前缀] [每处行数] [最多处数]
对 idx 里命中名字的每个脚本跑 pseudo，打印包含调用的语句及其后几行。"""
import sys, os, re, marshal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pseudo

pat = re.compile(sys.argv[1])
pre = sys.argv[2] if len(sys.argv) > 2 else ""
after = int(sys.argv[3]) if len(sys.argv) > 3 else 4
limit = int(sys.argv[4]) if len(sys.argv) > 4 else 20
name = re.findall(r"[A-Za-z_]\w+", sys.argv[1])[-1]     # idx 只有名字：用正则里最后一个标识符预筛
sys.stdout.reconfigure(encoding="utf-8")
n = 0
for line in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "idx.tsv"), encoding="utf-8"):
    f, _, rest = line.partition("\t")
    if not f.startswith(pre) or (" %s " % name) not in (" %s " % rest.replace(" | ", "  ")): continue
    co = marshal.loads(open(os.path.join(pseudo.ROOT, f), "rb").read()[16:])
    out = []
    pseudo.func(co, out)
    cur = ""
    for i, s in enumerate(out):
        if s.startswith("def "): cur = s
        if pat.search(s) and not s.startswith("def "):
            print("---- %s :: %s" % (f, cur[4:80]))
            print("\n".join(x for x in out[i:i + after + 1] if "# stack" not in x))
            n += 1
            if n >= limit: sys.exit()
