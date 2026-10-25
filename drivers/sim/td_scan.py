# -*- coding: utf-8 -*-
"""扫 pydata 模块里对 TD(taggeddict) 的调用形态：TD(dict) 还是 TD(int, ...)，以及引用的模板号。"""
import sys, os, dis, marshal, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simenv
simenv.setup()

def scan(path):
    co = marshal.loads(open(path, "rb").read()[16:])
    seq = []   # 依次: ("dict", 键数) / ("ref", 模板号)
    ins = list(dis.get_instructions(co))
    for i, x in enumerate(ins):
        if x.opname == "LOAD_NAME" and x.argval == "TD":
            nx = ins[i + 1]
            if nx.opname == "BUILD_MAP":
                seq.append(("dict",))
            elif nx.opname == "LOAD_CONST" and isinstance(nx.argval, int):
                seq.append(("ref", nx.argval))
            else:
                seq.append(("other", nx.opname))
    return seq

root = os.path.join(simenv.ROOT, "pydata")
stats = collections.Counter()
shown = 0
for fn in sorted(os.listdir(root)):
    if not fn.endswith(".pyc"): continue
    seq = scan(os.path.join(root, fn))
    if not seq: continue
    nd = sum(1 for s in seq if s[0] == "dict")
    refs = sorted(set(s[1] for s in seq if s[0] == "ref"))
    stats["modules_with_TD"] += 1
    if nd > 1 and shown < 6:
        shown += 1
        # 打印前 40 个事件，看模板号与 dict 出现顺序的关系
        print(fn, "dicts=%d refs=%s" % (nd, refs[:20]))
        print("   ", seq[:40])
    if refs and max(refs) > nd:
        stats["ref_gt_ndict"] += 1
print(dict(stats))
