# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：准备阶段 天赋 <-> 座位号 对应，以及"我是不是监管"。
# 关键问题：c_skill_data 每行的 eid 对象，与 uid2pos 的键是不是**同一个 Python 对象**(id 相同)？
#   是 -> C++ 侧直接比指针就能配座位，不用解析 ObjectId。
ui = S(lambda: GK.g_ui_mgr.ui_dict, {}) or {}
panel = S(lambda: ui.get("UIRoomWait"))
if panel is None:
    P("没有 UIRoomWait"); raise SystemExit
d = S(lambda: idict(panel), {}) or {}
P("role(面板) = %r   copycat_camp_id = %r" % (d.get("role"), d.get("copycat_camp_id")))
pos = d.get("uid2pos") or {}
pid = d.get("uid2pid") or {}
bpos = d.get("b_uid2pos") or {}
bpid = d.get("b_uid2pid") or {}
P("uid2pos   = %s" % R(pos, 300))
P("uid2pid   = %s" % R(pid, 300))
P("b_uid2pos = %s   b_uid2pid = %s" % (R(bpos, 100), R(bpid, 100)))
P("uid2pos 键: %s" % [(R(k, 40), type(k).__name__, hex(id(k))) for k in pos.keys()])

P("\n== c_skill_data ==")
rows = d.get("c_skill_data") or []
for i, r in enumerate(rows):
    e = r[0]
    same_obj = [k for k in pos.keys() if k is e]
    eq = [k for k in pos.keys() if k == e]
    P("  #%d eid=%s(%s,id=%s) 名字=%r pid=%r 状态=%r 天赋=%r" % (i, R(e, 40), type(e).__name__, hex(id(e)),
                                                          r[1], r[2], r[3], r[4]))
    P("      -> 座位(==)=%s  同一对象=%s  uid2pid=%s" % (pos.get(e), bool(same_obj), pid.get(e)))

# 自己是哪条：g_avatar 本人 eid
av = S(lambda: GK.g_avatar)
my = None
for a in ("eid", "_id", "entity_id", "avatar_id", "id"):
    v = S(lambda a=a: idict(av).get(a))
    if v is not None: P("g_avatar.%s = %s(%s)" % (a, R(v, 40), type(v).__name__))
