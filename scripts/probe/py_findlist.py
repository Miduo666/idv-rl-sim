# -*- coding: utf-8 -*-
r"""找持有一组对象的容器: 把指向它们的引用按地址聚类，同一簇里出现的不同对象越多越可能是列表/字典。

    python py_findlist.py 0x7C5B79CE20 0x7C5B75DC20 ...
"""
import sys, struct, collections
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap

MASK = 0x00FFFFFFFFFFFFFF
TAG = 0xB4 << 56
WINDOW = 0x400          # 同一容器内元素应彼此靠近

TARGETS = [int(a, 16) for a in sys.argv[1:]] or [
    0x7C5B79CE20, 0x7C5B75DC20, 0x7C5B7C3DE0, 0x7C5B73AC70,
    0x7C5B7C6BD0, 0x7C5B770FF0, 0x7C5B71E3E0]

h = Heap()
allrefs = []
for i, t in enumerate(TARGETS):
    rs = h.findall(struct.pack("<Q", t | TAG), align=8, limit=4000) + \
         h.findall(struct.pack("<Q", t), align=8, limit=4000)
    print("0x%X 被 %d 处引用" % (t, len(rs)))
    for r in rs:
        allrefs.append((r, i))
allrefs.sort()
print("\n引用总数 %d，开始聚类(窗口 0x%X)\n" % (len(allrefs), WINDOW))

clusters = []
cur = []
for r, i in allrefs:
    if cur and r - cur[-1][0] > WINDOW:
        clusters.append(cur)
        cur = []
    cur.append((r, i))
if cur:
    clusters.append(cur)

best = sorted(clusters, key=lambda c: -len({i for _, i in c}))
print("=== 覆盖目标最多的簇 ===")
for c in best[:12]:
    ids = sorted({i for _, i in c})
    if len(ids) < 2:
        continue
    lo, hi = c[0][0], c[-1][0]
    step = ""
    if len(c) > 2:
        d = sorted({c[k + 1][0] - c[k][0] for k in range(len(c) - 1)})
        step = " 间隔=%s" % ("均匀 0x%X" % d[0] if len(d) == 1 else str([hex(x) for x in d[:5]]))
    print("   0x%X-0x%X  元素 %d 个, 覆盖 %d/%d 个目标%s"
          % (lo, hi, len(c), len(ids), len(TARGETS), step))
    for r, i in c:
        print("        0x%X -> 目标#%d (0x%X)" % (r, i, TARGETS[i]))
