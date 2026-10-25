# -*- coding: utf-8 -*-
# probe2 命令：局内找 "账号uid字符串 <-> ObjectId(eid)" 的映射。
# 背景：final_genius_dict 用 eid(人机是 '1000'，真人是 ObjectId 十六进制)做键，
# 而单位上的 unique_id 真人是账号 uid 字符串 —— 少了这层映射，真人的天赋就配不上。
# 准备阶段这层映射在 UIRoomWait.uid_2_eid 上，进局后面板销毁，得另找。
gk = GK
me = S(lambda: gk.g_unit)
MY_UID = str(S(lambda: idict(me).get("unique_id")))
P("本机 unique_id = %r" % MY_UID)

seen = set(); queue = []
for k in (S(lambda: sorted(vars(gk).keys()), []) or []):
    if not isinstance(k, str) or k.startswith("__"): continue
    v = S(lambda k=k: getattr(gk, k))
    if v is None or callable(v) or isinstance(v, (int, float, str, bool)): continue
    queue.append((v, "GK." + k, 0))

def looks_oid(x):
    s = str(x)
    return ("ObjectId" in s) or (len(s) == 24 and all(c in "0123456789abcdef" for c in s))

hits = 0
while queue and len(seen) < 3000:
    obj, path, depth = queue.pop(0)
    if id(obj) in seen: continue
    seen.add(id(obj))
    d = S(lambda: idict(obj))
    if not isinstance(d, dict): continue
    for a in sorted(d.keys()):
        if not isinstance(a, str) or a.startswith("__"): continue
        v = S(lambda a=a: d.get(a))
        if v is None or callable(v): continue
        # 命中条件：dict 的键或值里出现 本机uid 或 ObjectId 形态
        if isinstance(v, dict) and v:
            ks = S(lambda: list(v.keys())[:8], []) or []
            vs = S(lambda: list(v.values())[:8], []) or []
            if any(str(x) == MY_UID for x in ks + vs) or any(looks_oid(x) for x in ks + vs):
                P("★ %s.%s = %s" % (path, a, R(v, 150)))
                hits += 1
        elif looks_oid(v) and not isinstance(v, (int, float)):
            P("  %s.%s = %r (%s)" % (path, a, v, cname(v)))
            hits += 1
        if depth < 1 and not isinstance(v, (int, float, str, bool, bytes)):
            if isinstance(v, dict):
                for vv in (S(lambda: list(v.values())[:4], []) or []):
                    if vv is not None and not isinstance(vv, (int, float, str, bool)):
                        queue.append((vv, "%s.%s[]" % (path, a), depth + 1))
            elif isinstance(v, (list, tuple, set)):
                for vv in (S(lambda: list(v)[:4], []) or []):
                    if vv is not None and not isinstance(vv, (int, float, str, bool)):
                        queue.append((vv, "%s.%s[]" % (path, a), depth + 1))
            else:
                queue.append((v, "%s.%s" % (path, a), depth + 1))

P("\n扫过 %d 个对象，命中 %d 条" % (len(seen), hits))
