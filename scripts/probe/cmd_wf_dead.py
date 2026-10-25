# -*- coding: utf-8 -*-
# probe2 林中童话：深挖每个玩家的死亡/存活状态。重点钻进 combat_unit 的
# health_attr_set(血量) 和 ref_game_state_comp(游戏状态)，找"被淘汰/旁观"到底挂哪。
# 看到"空有框没有人"时采一下。单次快照。用法：.\send_cmd.ps1 cmd_wf_dead.py 空框

def getd(o):
    return (S(lambda: idict(o), {}) or {}) if o is not None else {}

def vec(o):
    return S(lambda: "(%.1f,%.2f,%.1f)" % (o.x, o.y, o.z), None) if o is not None else None

# 把一个组件对象里"像状态/血量"的字段挖出来（钻一层）
def dig(obj, tag):
    if obj is None:
        P("    %s = None" % tag); return
    d = getd(obj)
    kw = ("hp","blood","health","life","cur","max","value","attr",
          "dead","die","alive","out","down","revive","respawn","knock","faint",
          "state","phase","spectat","watch","leave","eliminat","fly","defeat","result","over")
    hit = sorted([k for k in d if isinstance(k, str) and any(w in k.lower() for w in kw)])
    P("    %s = %s  字段: %s" % (tag, cname(obj), hit if hit else "(无命中,全字段数=%d)" % len(d)))
    for k in hit:
        v = d[k]
        # 数值直接印；对象再钻一层看里面有没有数值
        if isinstance(v, (int, float)) or v is None:
            P("        %-22s %s" % (k, R(v, 30)))
        else:
            sub = getd(v)
            nums = {kk: sub[kk] for kk in sub if isinstance(sub.get(kk), (int, float))}
            P("        %-22s %s  (内含数值:%s)" % (k, cname(v), {kk: R(nums[kk],10) for kk in list(nums)[:10]}))

t = ubt()
us = units_of(1601) or []
P("========== [1601] 玩家 %d 个 ==========" % len(us))
for u in us:
    d = getd(u)
    P("\nuid=%s self=%s team=%s ident=%s is_leave=%s pos=%s" % (
        R(d.get("uid"),12), R(d.get("is_self"),6), R(d.get("water_fight_team"),4),
        R(d.get("water_fight_identity"),4), R(d.get("is_leave"),6), vec(d.get("position"))))
    cu = d.get("combat_unit")
    if cu is None:
        P("    combat_unit = None"); continue
    cud = getd(cu)
    # combat_unit 顶层里所有名字含关键字的
    kw = ("health","hp","dead","alive","state","die","out","down","revive","leave","result","over","game","spectat","watch")
    tops = sorted([k for k in cud if isinstance(k,str) and any(w in k.lower() for w in kw)])
    P("    combat_unit=%s 顶层状态键: %s" % (cname(cu), tops))
    dig(cud.get("health_attr_set"), "health_attr_set")
    dig(cud.get("ref_game_state_comp"), "ref_game_state_comp")
P("\n[done]")
