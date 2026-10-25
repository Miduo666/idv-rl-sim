# -*- coding: utf-8 -*-
"""统计每个乱序操作码后面跟几个全零字(= 游戏版的 inline cache 长度)。"""
import sys, os, io, collections, opcode
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rawmarshal import load_pyc, iter_codes

root, names_path = sys.argv[1], sys.argv[2]
NAMES = open(names_path).read().split()
STOCK = opcode._inline_cache_entries

runs = collections.defaultdict(collections.Counter)   # 乱序字节 -> {后随零字数: 次数}
first = collections.Counter()
nfiles = nbad = ncodes = 0
for dp, _, fs in os.walk(root):
    for fn in fs:
        if not fn.endswith(".pyc"): continue
        try:
            top = load_pyc(os.path.join(dp, fn))
        except Exception as e:
            nbad += 1; continue
        nfiles += 1
        for c in iter_codes(top):
            ncodes += 1
            b = c.code
            words = [(b[i], b[i + 1]) for i in range(0, len(b), 2)]
            first[NAMES[words[0][0]]] += 1
            i = 0
            while i < len(words):
                op = words[i][0]
                if op == 0:
                    i += 1; continue          # 孤立零字(理论上不应出现)
                j = i + 1
                while j < len(words) and words[j][0] == 0 and words[j][1] == 0:
                    j += 1
                runs[op][j - i - 1] += 1
                i = j

print("files", nfiles, "bad", nbad, "codes", ncodes)
print("first instr:", first.most_common(8))
print("%-5s %-28s %-6s %s" % ("byte", "name(2024表)", "stock", "后随零字数分布"))
for op in sorted(runs, key=lambda o: -sum(runs[o].values())):
    nm = NAMES[op]
    st = STOCK[opcode.opmap[nm]] if nm in opcode.opmap else "-"
    dist = runs[op].most_common(5)
    flag = "" if (st != "-" and dist[0][0] == st) else "   <<<"
    print("%-5d %-28s %-6s %s  n=%d%s" % (op, nm, st, dist, sum(runs[op].values()), flag))
