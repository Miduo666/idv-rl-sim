# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：模仿者模式轻量快照，给 copycat300.ps1 反复投递，PC 侧 copycat_report.py 出时间线。
# 目的：找隐藏身份(identity_id 101~118/201~209/301~308)挂在哪、别人的身份客户端有没有、阵营字段怎么表示。
# 不猜字段名：每个玩家单位上名字命中关键字的属性全打出来(A)，值落在身份号段里的整数也打出来(V)。
# 不 sleep(命令在游戏线程里 exec)，时间序列由 PC 侧连续投递。
import re
gk = GK
t0 = time.time()
RX = re.compile(r"ident|camp|role|copycat|detect|mimic|imitat|faction|team|reveal|secret|hidden|disguise"
                r"|career|job|neutral|spy|vote|meet|dead|die|alive|elim|kill|suspect|clue|component")
IDR = set(range(101, 119)) | set(range(201, 210)) | set(range(301, 309))
PLAYERISH = re.compile(r"civilian|butcher|player|copycat|detect|mimic|survivor|hunter", re.I)
# 模仿者局里 Copycat*Unit 还包括场景物件(CopycatSceneUnit/ElectricUnit/GeneratorUnit/RavenGateUnit)，排除掉
NOTPLAYER = re.compile(r"scene|electric|generator|gate", re.I)
CONT = (dict, list, tuple, set, frozenset)
LEAF = (bool, int, float, str, bytes, type(None))


def one(v, n=100):
    return R(v, n).replace("\t", " ").replace("\n", " ")


def brief(v, n=100):
    ln = S(lambda: len(v), 0) if isinstance(v, CONT) else 0
    if ln > 30:
        head = list(v.items())[:5] if isinstance(v, dict) else list(v)[:5]
        return "<%s len=%d> %s" % (type(v).__name__, ln, one(head, n))
    return one(v, n)


def is_obj(v):
    return not isinstance(v, LEAF + CONT) and not callable(v)


def dump_attrs(tag, owner, d, sub_depth=1):
    """d 里名字命中关键字的打 A，值在身份号段的整数打 V；命中关键字且是普通实例的，再展开一层叶子(AO)"""
    for a in sorted([x for x in d.keys() if isinstance(x, str)]):
        v = d[a]
        if RX.search(a.lower()):
            if callable(v) and not isinstance(v, CONT):
                continue
            P("%s\t%s\t%s\t%s" % (tag, owner, a, brief(v)))
            if sub_depth > 0 and is_obj(v):
                P("%sC\t%s\t%s\t%s" % (tag, owner, a, cname(v)))
                sd = idict(v)
                n = 0
                for b in sorted([x for x in sd.keys() if isinstance(x, str)]):
                    w = sd[b]
                    if isinstance(w, LEAF) or (isinstance(w, CONT) and S(lambda: len(w), 99) <= 12):
                        P("%sO\t%s\t%s.%s\t%s" % (tag, owner, a, b, one(w, 80)))
                        n += 1
                        if n >= 60:
                            break
        elif type(v) is int and v in IDR:
            P("%sV\t%s\t%s\t%d" % (tag, owner, a, v))


P("TIME\t%.3f" % t0)
wm = S(lambda: gk.g_world_mgr)
cw = S(lambda: wm.cur_world)
bw = S(lambda: wm.battle_world)
P("WORLD\t%s\twt=%r\tscene=%r\tbattle=%s" % (cname(cw), S(lambda: cw.world_type), S(lambda: cw.scene_id), cname(bw)))
ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
P("UI\t%s" % one(sorted([k for k in S(lambda: list(ui.keys()), []) if isinstance(k, str)]), 2000))
cam = S(lambda: gk.g_cam_ctrl.unit)
P("CAM\t%s\tuid=%r\tme=%s\tme_uid=%r" % (cname(cam), S(lambda: idict(cam).get("uid")),
                                         cname(me), S(lambda: idict(me).get("uid"))))

# 世界对象上命中关键字的属性(身份表可能挂在世界/管理器上而不是单位上)
seen_w = set()
for tag, w in (("cur", cw), ("battle", bw)):
    if w is None or id(w) in seen_w:
        continue
    seen_w.add(id(w))
    dump_attrs("W", tag, S(lambda w=w: idict(w), {}) or {})

# game_kernel 顶层名字命中关键字的对象
for name in sorted([x for x in S(lambda: list(vars(gk).keys()), []) if isinstance(x, str)]):
    if name.startswith("__") or not RX.search(name.lower()):
        continue
    v = S(lambda name=name: getattr(gk, name))
    if callable(v) and not isinstance(v, CONT) and not is_obj(v):
        continue
    P("GK\t%s\t%s\t%s" % (name, cname(v), brief(v)))
    if is_obj(v):
        dump_attrs("G", name, S(lambda v=v: idict(v), {}) or {}, 0)

keys = sorted([k for k in (S(lambda: list(ubt().keys()), []) or []) if isinstance(k, int)])
kinfo = []
picked = []
seen_u = set()
for k in keys:
    us = units_of(k)
    cs = sorted(set(cname(u) for u in us))
    kinfo.append("%d:%d:%s" % (k, len(us), "/".join(cs)))
    for u in us:
        if id(u) in seen_u:
            continue
        if k in (1, 2) or (PLAYERISH.search(cname(u)) and not NOTPLAYER.search(cname(u))):
            seen_u.add(id(u))
            picked.append((k, u))
P("KEYS\t%s" % " ".join(kinfo))

for k, u in picked[:24]:
    d = S(lambda u=u: idict(u), {}) or {}
    uid = d.get("uid")
    nm = d.get("player_name", d.get("_player_name", d.get("name")))
    mdl = d.get("model")
    P("U\t%s\tk=%d\t%s\tname=%s\tuq=%s\tself=%r\tcam=%s\tmodel=%s\tvis=%r\tnattr=%d" % (
        uid, k, cname(u), one(nm, 30), one(d.get("unique_id"), 30), d.get("is_self"), cam is u,
        one(S(lambda: mdl.filename), 70), S(lambda: mdl.visible), len(d)))
    dump_attrs("A", uid, d)
    comps = d.get("components", d.get("_components"))
    if comps is not None:
        items = list(comps.items())[:40] if isinstance(comps, dict) else list(enumerate(S(lambda: list(comps), [])))[:40]
        for ck, c in items:
            P("C\t%s\t%s\t%s" % (uid, one(ck, 40), cname(c)))
            cd = S(lambda c=c: idict(c), {}) or {}
            for b in sorted([x for x in cd.keys() if isinstance(x, str)]):
                w = cd[b]
                if RX.search(b.lower()) or (type(w) is int and w in IDR):
                    P("CA\t%s\t%s.%s\t%s" % (uid, one(ck, 40), b, brief(w, 80)))

P("END\t%.1fms\tunits=%d" % ((time.time() - t0) * 1000, len(picked)))
