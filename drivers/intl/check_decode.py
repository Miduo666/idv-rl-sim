# -*- coding: utf-8 -*-
"""校验字节码解码：单片对比相邻配对；全量统计；再出 40 天赋 + 求生终端 + 特质 + 模仿者的中英表。"""
import sys, os, re, json, marshal
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tiddict import decode_refs, load_dir
root, outdir = sys.argv[1], sys.argv[2]

co = marshal.loads(open(os.path.join(root, "pydata", "tid_data", "all_tid_en_0.py.marshal"), "rb").read())
pairs, bad, odd = decode_refs(co)
print("en_0: pairs=%d bad_keys=%d odd=%d sample=%s" % (len(pairs), bad, odd, pairs[:2]))

chs, schs, ich = load_dir(root, "chs"); en, sen, ien = load_dir(root, "en")
print("对齐问题(文件,坏键,剩余未配对) chs %d 个:" % len(ich), ich[:8], "\n  en %d 个:" % len(ien), ien[:8])
print("chs=%d en=%d  chs_diff覆盖=%d en_diff覆盖=%d" % (len(chs), len(en),
      sum(1 for v in schs.values() if v == "diff"), sum(1 for v in sen.values() if v == "diff")))
json.dump({"chs": chs, "en": en, "src_chs": schs, "src_en": sen},
          open(os.path.join(outdir, "tid_chs_en_v2.json"), "w", encoding="utf-8"), ensure_ascii=False)

def show(t):
    return "%s\t%s\t%s\t(%s/%s)" % (t, chs.get(t, "?"), en.get(t, "?"), schs.get(t, "-"), sen.get(t, "-"))

cs = marshal.loads(open(os.path.join(root, "pydata", "butcher_genius.py.marshal"), "rb").read()).co_consts
ns = [int(m.group(1)) for c in cs if isinstance(c, str) for m in [re.match(r"^TID_TALENT_BACKGROUND_KILLER_(\d+)$", c)] if m]
print("\n##### 监管天赋 (国际服 butcher_genius 顺序)")
for gid, n in enumerate(ns, 1):
    print("%2d\t%s" % (gid, show("TID_BUTCHER_NAME_%d_LV1" % n)))
print("\n##### 求生终端/绝处逢生")
for t in ("TID_HUMAN_NAME_150_LV1", "TID_HUMAN_NAME_127_LV1", "TID_HUMAN_NAME_110_LV1", "TID_HUMAN_NAME_123_LV1", "TID_HUMAN_NAME_102_LV1"):
    print(show(t))
print("\n##### 辅助特质")
for t in ("TID_NAME_LISTEN", "TID_NAME_RECOVERY", "TID_NAME_STOTIC", "TID_NAME_PATROL_PUPPET", "TID_NAME_TRANSFER", "TID_NAME_EYE", "TID_NAME_BLINK", "TID_NAME_YIXING"):
    print(show(t))
print("\n##### 模仿者身份")
for pre, n in (("TID_COPYCAT_DETECTIVE_NAME_", 30), ("TID_COPYCAT_COPYCAT_NAME_", 20), ("TID_COPYCAT_MYSTERIOUS_NAME_", 20)):
    for i in range(1, n + 1):
        t = pre + str(i)
        if t in chs or t in en:
            print(show(t))
