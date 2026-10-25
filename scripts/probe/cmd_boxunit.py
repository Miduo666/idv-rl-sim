# -*- coding: utf-8 -*-
# probe2: dump BoxUnit(宝箱, type5) 的字段, 找"箱子里是什么/是否开过/掉出什么"。
# 顺带看 CivilianUnit 上与箱子/拾取/地上道具相关的字段。
KW = ("item", "box", "chest", "content", "open", "reward", "state", "has", "empty",
      "used", "give", "drop", "spawn", "pick", "carry", "inside", "treasure", "prop", "gift")

boxes = units_of(5) or []
P("== BoxUnit 数量=%d ==" % len(boxes))
if boxes:
    b = boxes[0]
    P("样本 BoxUnit uid=%s cls=%s" % (R(S(lambda: b.uid), 12), cname(b)))
    names = sorted(S(lambda: list(idict(b).keys()), []))
    P("  -- 属性名含关键字的(带值) --")
    for a in names:
        if not isinstance(a, str) or a.startswith("__"):
            continue
        if any(w in a.lower() for w in KW):
            v = S(lambda a=a: idict(b)[a])
            P("    %-30s %-18s %s" % (a, cname(v), R(v, 70)))
    P("  -- 全部属性名(%d, 找漏网的) --" % len(names))
    line = ""
    for a in names:
        if isinstance(a, str) and not a.startswith("__"):
            line += a + " "
            if len(line) > 110:
                P("    " + line); line = ""
    if line:
        P("    " + line)

P("\n== CivilianUnit 上与箱子/拾取/地上道具相关字段 ==")
for u in (units_of(2) or [])[:2]:
    uid = S(lambda: u.uid)
    P("  civ uid=%s" % R(uid, 12))
    for a in sorted(S(lambda u=u: list(idict(u).keys()), [])):
        if not isinstance(a, str) or a.startswith("__"):
            continue
        if any(w in a.lower() for w in ("box", "chest", "pick", "carry", "interact", "ground", "drop", "nearby", "cur_item", "open")):
            v = S(lambda u=u, a=a: idict(u)[a])
            P("    %-30s %-18s %s" % (a, cname(v), R(v, 60)))
