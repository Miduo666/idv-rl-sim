# -*- coding: utf-8 -*-
# probe2 命令：宽搜辅助特质。不限定下钻路径，凡是实例都进队列(上限 3000 个对象，深度 2)，
# 打印名字含 skill/support/handheld/hold/equip/choose 且有值的属性。
KW = ("skill", "support", "handheld", "equip", "choose", "select_", "loadout")
SKIP_CLS = ("Unit", "Model", "Vector", "Quaternion", "Transform")

gk = GK
seen = set(); queue = []
for k in (S(lambda: sorted(vars(gk).keys()), []) or []):
    if not isinstance(k, str) or k.startswith("__"): continue
    v = S(lambda k=k: getattr(gk, k))
    if v is None or callable(v) or isinstance(v, (int, float, str, bool)): continue
    queue.append((v, "GK." + k, 0))

hits = 0
while queue and len(seen) < 3000:
    obj, path, depth = queue.pop(0)
    if id(obj) in seen: continue
    seen.add(id(obj))
    cn = cname(obj)
    if any(w in cn for w in SKIP_CLS): continue
    d = S(lambda: idict(obj))
    if not isinstance(d, dict): continue
    for a in sorted(d.keys()):
        if not isinstance(a, str) or a.startswith("__"): continue
        v = S(lambda a=a: d.get(a))
        if v is None or callable(v): continue
        low = a.lower()
        if any(w in low for w in KW) and v not in ({}, [], set(), "", 0, False):
            P("★ %-58s %-9s %s" % (path + "." + a, cname(v), R(v, 110)))
            hits += 1
        if depth < 1 and not isinstance(v, (int, float, str, bool, bytes)):
            if isinstance(v, dict):
                for kk, vv in list(v.items())[:4]:
                    if vv is not None and not isinstance(vv, (int, float, str, bool)):
                        queue.append((vv, "%s.%s[%s]" % (path, a, kk), depth + 1))
            elif isinstance(v, (list, tuple, set)):
                for vv in list(v)[:4]:
                    if vv is not None and not isinstance(vv, (int, float, str, bool)):
                        queue.append((vv, "%s.%s[]" % (path, a), depth + 1))
            else:
                queue.append((v, "%s.%s" % (path, a), depth + 1))

P("\n扫过 %d 个对象，命中 %d 条" % (len(seen), hits))
