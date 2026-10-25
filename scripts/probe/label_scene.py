# -*- coding: utf-8 -*-
# 把探针给出的 Python 模型对象(id)映射到场景对象(+0x20)，再给场景数组里每个 chr 对象打标签
import json, struct, sys, os
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem
from idv_probe import discover
M = 0x00FFFFFFFFFFFFFF
HERE = os.path.dirname(os.path.abspath(__file__))
rows = json.loads(open(os.path.join(HERE, "models.json"), encoding="utf-8-sig").read().strip())
pid, libbase, bss, maps = discover()
m = Mem(pid)
def ok(x): return 0x5000000000 < x < 0x8000000000

m.fetch([(r[3] & M) + 0x20 for r in rows])
标签 = {}
for t, uid, k, pyid, vis, fn in rows:
    sp = m.q((pyid & M) + 0x20)
    sp = (sp & M) if sp is not None else 0
    标签.setdefault(sp, []).append("%s.%s" % (uid, k))
    print("uid=%s %-14s vis=%-5s scene=0x%X  %s" % (uid, k, vis, sp, fn))

HEAD = libbase + 0xB40A638
m.fetch([HEAD]); arr, end = m.q(HEAD) & M, m.q(HEAD + 8) & M
m.fetch(list(range(arr, end, 0x1000)) + [end])
objs = [m.q(arr + i * 8) & M for i in range((end - arr) // 8)]
objs = [o for o in objs if ok(o)]
m.fetch(sum([[o, o + 0x100, o + 0x200] for o in objs], []))
def name(o):
    p = o + 0xf8
    for off in (0, 0x0, 0x8, 0x20, 0x20):
        m.fetch([p + off]); v = m.q(p + off)
        if v is None: return None
        p = v & M
        if not ok(p): return None
    m.fetch([p]); sp, ln = m.q(p + 8), m.d(p + 0x10)
    if sp is None or ln is None or not (0 < ln < 256): return None
    sp &= M; m.fetch([sp, sp + ln]); b = m.get(sp, ln)
    return b.decode("latin1", "replace") if b else None
print("\n场景数组 count=%d" % len(objs))
print("%-12s %-4s %-4s %-4s %-30s %s" % ("obj", "240", "6D", "73", "Python 侧身份", "类名"))
未命中 = 0
for o in objs:
    nm = name(o)
    tag = ",".join(标签.get(o, []))
    if not tag and not (nm and nm.startswith("chr")): continue
    if not tag: 未命中 += 1
    b6d, b73 = m.get(o + 0x6D, 1), m.get(o + 0x73, 1)
    print("%-12X %-4s %-4s %-4s %-30s %s" % (o, m.d(o + 0x240), b6d.hex() if b6d else "?", b73.hex() if b73 else "?", tag or "--(无宿主)", nm or "?"))
print("\n数组里不在 Python 侧任何属性上的 chr 对象: %d 个" % 未命中)
print("Python 侧场景指针在数组里找不到的:", [("0x%X" % k, v) for k, v in 标签.items() if k not in set(objs)])
