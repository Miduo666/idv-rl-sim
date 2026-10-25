# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：模仿者「假面舞会」—— 所有人变成石像模型时，身份/本体配对为什么失效。
# 单次快照，舞会前跑一次、舞会中跑一次(各一次就够)，PC 侧对比：
#   1) 每个玩家单位上所有"模型对象"属性(值有 .filename 的)：属性名 / 文件名 / visible / id
#      -> 看石像是换进了 unit.model，还是挂在别的属性上
#   2) combat_unit.components[3](ModelRefComponent) 和它身上的 handler(MasqueradeModelRefHandler)的全部叶子字段
#   3) CopycatMasqueradeSystem 的全部叶子字段(舞会开始/结束/谁是谁可能在这里)
# 用法: .\send_cmd.ps1 cmd_copycat_masq.py 舞会前      .\send_cmd.ps1 cmd_copycat_masq.py 舞会中
gk = GK
t0 = time.time()
LEAF = (bool, int, float, str, bytes, type(None))


def one(v, n=140):
    return R(v, n).replace("\t", " ").replace("\n", " ")


def model_info(v):
    fn = S(lambda: v.filename)
    if fn is None:
        return None
    return "file=%s vis=%r id=0x%x" % (one(fn, 110), S(lambda: v.visible), id(v))


def dump_leaves(tag, o, depth=0, seen=None):
    seen = seen if seen is not None else set()
    if o is None or id(o) in seen or depth > 2:
        return
    seen.add(id(o))
    d = S(lambda: idict(o), {}) or {}
    P("%s\t<%s>\t%d 条" % (tag, cname(o), len(d)))
    for a in sorted([x for x in d.keys() if isinstance(x, str)]):
        v = d[a]
        mi = model_info(v)
        if mi:
            P("%s.%s\tMODEL\t%s" % (tag, a, mi))
        elif isinstance(v, LEAF) or (isinstance(v, (list, tuple, dict, set)) and S(lambda: len(v), 99) <= 16):
            P("%s.%s\t%s" % (tag, a, one(v)))
        elif "handler" in a.lower() or "masq" in a.lower() or "ref" in a.lower():
            dump_leaves(tag + "." + a, v, depth + 1, seen)
        else:
            P("%s.%s\t<%s>" % (tag, a, cname(v)))


P("TIME\t%.3f" % t0)
cw = S(lambda: gk.g_world_mgr.cur_world)
P("WORLD\t%s" % cname(cw))
ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
P("UI\t%s" % one(sorted([k for k in S(lambda: list(ui.keys()), []) if isinstance(k, str)]), 1500))

players = units_of(1088)
P("PLAYERS\t%d" % len(players))
masq_done = False
for u in players:
    d = S(lambda u=u: idict(u), {}) or {}
    uid = d.get("uid")
    P("\n== uid=%s seat=%s identity=%s cls=%s" % (uid, d.get("copycat_index"), d.get("identity_id"), cname(u)))
    # 1) 所有模型对象属性
    for a in sorted([x for x in d.keys() if isinstance(x, str)]):
        mi = model_info(d[a])
        if mi:
            P("  M\t%s\t%s" % (a, mi))
    # 名字可疑的其它属性
    for a in sorted([x for x in d.keys() if isinstance(x, str)]):
        low = a.lower()
        if any(w in low for w in ("masq", "mask", "statue", "dance", "disguise", "transform", "morph", "skin", "model_path")):
            P("  K\t%s\t%s" % (a, one(d[a])))
    # 2) ModelRefComponent
    comps = S(lambda: u.combat_unit.components, {}) or {}
    mr = comps.get(3) if isinstance(comps, dict) else None
    if mr is not None:
        dump_leaves("  C3", mr)
    # 3) 舞会系统(每个单位都挂同一个，只打一次)
    if not masq_done:
        si = S(lambda: u.combat_unit.core.system_instances, {}) or {}
        for k, v in (si.items() if isinstance(si, dict) else []):
            if "Masquerade" in str(k):
                dump_leaves("SYS", v)
                masq_done = True

P("\nEND\t%.1fms" % ((time.time() - t0) * 1000))
