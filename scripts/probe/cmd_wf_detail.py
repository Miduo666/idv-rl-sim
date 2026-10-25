# -*- coding: utf-8 -*-
# probe2 林中童话(WaterFight)详查：队友过滤字段 + 物资真伪(model_name) + 死人标志 + 位置字段对比。
# 单次快照，不 sleep。helper 由 probe2 提供。用法：.\send_cmd.ps1 cmd_wf_detail.py 详查

def vec(o):
    if o is None: return None
    return S(lambda: "(%.1f,%.2f,%.1f)" % (o.x, o.y, o.z), R(o, 30))

def getd(u):
    return S(lambda: idict(u), {}) or {}

P("========== 世界/自身 ==========")
cam = S(lambda: GK.g_cam_ctrl); camu = S(lambda: cam.unit)
d = getd(camu)
P("self: uid=%s is_self=%s team=%s identity=%s" % (
    R(d.get("uid"),20), R(d.get("is_self"),6), R(d.get("water_fight_team"),6), R(d.get("water_fight_identity"),6)))

t = ubt()
def lst(k): return units_of(k) or []

# ---------- 玩家 [1601]：队伍/阵营 + 4 个位置字段 + 死亡候选 ----------
P("\n========== 玩家 [1601] ==========")
POSF = ("position", "visual_position", "interp_pos", "logic_position")
STATUS = ("is_leave","surrenderring","surrender_end","force_invisible","total_visibility",
          "b_in_fear","is_watcher","anim_visible_check","_destroyed","in_xray")
for u in lst(1601):
    d = getd(u)
    P("uid=%s self=%s team=%s ident=%s" % (
        R(d.get("uid"),18), R(d.get("is_self"),6), R(d.get("water_fight_team"),5), R(d.get("water_fight_identity"),5)))
    for f in POSF:
        if f in d: P("    %-16s %s" % (f, vec(d[f])))
    st = " ".join("%s=%s" % (k, R(d[k],10)) for k in STATUS if k in d)
    P("    status: %s" % st)
    # combat_unit 里找血量/死亡/出局
    cu = d.get("combat_unit")
    if cu is not None:
        cd = getd(cu)
        kw = ("hp","blood","health","life","dead","die","alive","out","down","revive","respawn","knock","state","score","kill","rank","eliminat")
        hit = {k: cd[k] for k in cd if isinstance(k,str) and any(w in k.lower() for w in kw)}
        P("    combat_unit=%s  %s" % (cname(cu), {k:R(hit[k],16) for k in list(hit)[:16]}))

# ---------- 物资真伪：靠 model_name / model_path 分辨箱子 vs 草地 ----------
def loot_report(key, name):
    us = lst(key)
    P("\n========== %s [%d] n=%d ==========" % (name, key, len(us)))
    if not us: return
    # model_name / model_path 分布
    mn = {}; mp = {}
    for u in us:
        d = getd(u)
        a = str(S(lambda d=d: d.get("model_name"), None)); mn[a] = mn.get(a,0)+1
        b = str(S(lambda d=d: d.get("model_path"), None)); mp[b] = mp.get(b,0)+1
    P("  model_name 分布: %s" % dict(sorted(mn.items(), key=lambda x:-x[1])))
    P("  model_path 分布: %s" % dict(sorted(mp.items(), key=lambda x:-x[1])[:12]))
    # box_type / level 等分级/状态字段分布
    for field in ("box_type","level","light_sfx"):
        vals = {}
        for u in us:
            v = getd(u).get(field)
            if v is not None: vals[R(v,12)] = vals.get(R(v,12),0)+1
        if vals: P("  %s 分布: %s" % (field, vals))
    # 代表实例：所有"可能表示真伪/类型/是否已取"的字段
    u0 = us[0]; d0 = getd(u0)
    kw = ("type","level","id","item","prop","pick","open","empty","used","active","state","visible","can_","is_","grass","ground","grade","quality","rarity","valid")
    hit = sorted([k for k in d0 if isinstance(k,str) and any(w in k.lower() for w in kw)])
    P("  代表实例关键字段:")
    for k in hit:
        P("    %-26s %s" % (k, R(d0[k],40)))

loot_report(1602, "箱子")
loot_report(1606, "掉落")
P("\n[done]")
