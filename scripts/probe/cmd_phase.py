# -*- coding: utf-8 -*-
# probe2 命令：阶段判定采样(大厅 / 准备 / 局内)。在游戏进程内 exec，环境变量见 probe2.run_cmd
# 输出末尾 ###MODELS### 之后一行是 models.json，给 label_scene.py 用

KW = ("room", "match", "prepare", "ready", "lobby", "select", "battle", "stage",
      "scene", "world", "state", "phase", "mode", "loading", "game_")

gk = GK
P("== game_kernel 顶层(名字含阶段关键字) ==")
for k in sorted(S(lambda: list(vars(gk).keys()), [])):
    if not isinstance(k, str) or k.startswith("__"): continue
    if any(w in k.lower() for w in KW):
        v = S(lambda k=k: getattr(gk, k))
        if callable(v) and not hasattr(v, "__dict__"): continue
        P("  %-32s %-28s %s" % (k, cname(v), R(v, 120)))

def unit_brief(u, tag):
    if u is None:
        P("%s = None" % tag); return
    P("%s = %s uid=%s unit_type=%s is_self=%s camp=%s" % (
        tag, cname(u), R(S(lambda: u.uid), 20), R(S(lambda: u.unit_type), 8),
        R(S(lambda: u.is_self), 8), R(S(lambda: u.dk_camp_type), 8)))
    P("   room=%s" % R(S(lambda: u.room), 90))

P("\n== 本机 ==")
unit_brief(me, "g_unit")
cam = S(lambda: gk.g_cam_ctrl)
P("g_cam_ctrl = %s" % R(cam, 90))
unit_brief(S(lambda: cam.unit), "cam.unit")
room = S(lambda: me.room)
if room is not None:
    P("room 类 = %s.%s" % (S(lambda: type(room).__module__), cname(room)))
    for k in sorted(attr_names(room)):
        if any(w in k.lower() for w in KW + ("butcher", "civilian", "player", "time", "count")):
            P("  room.%-30s %s" % (k, R(S(lambda k=k: idict(room)[k]), 100)))

P("\n== units_by_type ==")
P("mgr = %s" % R(mgr, 80))
t = ubt()
for k in S(lambda: sorted([x for x in t.keys() if isinstance(x, int)]), []):
    us = units_of(k); c = {}
    for u in us: c[cname(u)] = c.get(cname(u), 0) + 1
    P("  [%s] n=%d %s" % (k, len(us), c))

# 每个单位上所有"像模型"的属性(有 visible 和 filename 的对象)
rows = []
P("\n== 单位模型属性 ==")
for k, u in all_units():
    uid = S(lambda: u.uid)
    for a, v in list(idict(u).items()):
        if not isinstance(a, str) or v is None: continue
        vis = S(lambda v=v: v.visible, "?")
        fn = S(lambda v=v: v.filename, None)
        if vis == "?" or fn is None: continue
        rows.append([k, uid, a, id(v), bool(vis), str(fn)])
    for it_i, it in enumerate(S(lambda: list(u.item_lst), []) or []):
        mo = S(lambda: it.model)
        if mo is not None and S(lambda: mo.filename) is not None:
            rows.append([k, uid, "item_lst[%d].model" % it_i, id(mo), bool(S(lambda: mo.visible)), str(mo.filename)])
for r in rows:
    P("  [%s] uid=%s %-24s vis=%-5s %s" % (r[0], r[1], r[2], r[4], r[5]))
P("\n###MODELS###")
P(json.dumps(rows))
