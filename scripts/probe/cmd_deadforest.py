# -*- coding: utf-8 -*-
# probe2 命令：林中童话(疑似 DeadForest/Voxel)模式发现型快照。
# 目标：确认世界 + 枚举 units_by_type 全键 + 找出玩家挂在哪个键 + dump 玩家身上的信息字段。
# 在游戏进程内 exec，helper(GK/me/mgr/P/S/R/cname/ubt/units_of/all_units/idict/attr_names/json)由 probe2 提供。
# 单次快照，不 sleep。用法：  .\send_cmd.ps1 cmd_deadforest.py 林中童话

# 判定"是人"的类名特征 & "是人"的信息字段候选名（后面按存在性探）
PLAYER_PAT = ("player", "civilian", "butcher", "hunter", "survivor", "wild", "explore", "boat")
INFO_CANDS = ("uid", "unique_id", "player_name", "name", "nick_name", "pid", "dk_camp_type",
              "unit_type", "is_self", "is_butcher", "is_civilian", "camp",
              "hp", "cur_hp", "max_hp", "blood", "health", "life", "hp_count",
              "is_dead", "is_alive", "alive", "dead", "dying", "down", "is_down", "is_out",
              "position", "pos", "rank", "score", "kill", "team", "team_id", "group",
              "backpack", "bag", "items", "item_lst", "prop", "props", "weapon",
              "model", "model_path", "visible")

def irepr(v, n=48):
    return R(v, n)

def names_of(o):
    ks = S(lambda: list(idict(o).keys()), None)
    if ks is None:
        ks = S(lambda: list(attr_names(o)), [])
    return sorted([k for k in ks if isinstance(k, str) and not k.startswith("__")])

# ---------- 1. 阶段 / 世界确认 ----------
P("========== 1. 阶段 / 世界 ==========")
gk = GK
uimgr = S(lambda: gk.g_ui_mgr)
ud = S(lambda: uimgr.ui_dict, None)
P("ui_dict keys = %s" % S(lambda: sorted([k for k in ud.keys()]), "?"))

wm = S(lambda: gk.g_world_mgr)
for wattr in ("cur_world", "battle_world"):
    w = S(lambda wattr=wattr: getattr(wm, wattr))
    if w is None:
        P("%s = None" % wattr); continue
    P("%s = %s.%s  world_type=%s scene_id=%s" % (
        wattr, S(lambda: type(w).__module__), cname(w),
        R(S(lambda: w.world_type), 8), R(S(lambda: w.scene_id), 12)))

room = S(lambda: me.room)
P("me = %s  me.room = %s.%s" % (cname(me),
    S(lambda: type(room).__module__ if room else None), cname(room) if room else None))
cam = S(lambda: gk.g_cam_ctrl)
camu = S(lambda: cam.unit)
P("g_cam_ctrl.unit = %s uid=%s is_self=%s camp=%s unit_type=%s" % (
    cname(camu), R(S(lambda: camu.uid), 20), R(S(lambda: camu.is_self), 6),
    R(S(lambda: camu.dk_camp_type), 6), R(S(lambda: camu.unit_type), 8)))

# ---------- 2. GK 顶层：模式相关管理器（可能藏玩家名册/物资/分区） ----------
P("\n========== 2. GK 顶层(模式相关) ==========")
MODEKW = ("voxel", "backpack", "deadforest", "forest", "wild", "explore", "bag",
          "prop", "survival", "region", "zone", "safe", "air", "loot", "team",
          "roster", "player", "rank", "battle", "mgr", "manager")
seen_mgr = 0
for k in S(lambda: sorted(set(list(vars(gk).keys()) + names_of(gk))), []):
    if not isinstance(k, str) or k.startswith("__"):
        continue
    if any(w in k.lower() for w in MODEKW):
        v = S(lambda k=k: getattr(gk, k))
        if callable(v) and not hasattr(v, "__dict__"):
            continue
        P("  %-34s %-26s %s" % (k, cname(v), irepr(v, 70)))
        seen_mgr += 1
P("  (共 %d 项)" % seen_mgr)

# ---------- 3. units_by_type 全键 ----------
P("\n========== 3. units_by_type 全键 ==========")
t = ubt()
keys = S(lambda: sorted([x for x in t.keys() if isinstance(x, int)]), [])
P("全部键 = %s" % keys)
player_keys = []
for k in keys:
    us = units_of(k) or []
    hist = {}
    for u in us:
        hist[cname(u)] = hist.get(cname(u), 0) + 1
    # 判据1：类名特征
    by_name = any(any(p in cn.lower() for p in PLAYER_PAT) for cn in hist.keys())
    # 判据2：结构性——代表实例有 is_self，或同时有 position 和 unit_type（不靠类名，扛新模式）
    by_struct = False
    if us:
        nm0 = set(names_of(us[0]))
        by_struct = ("is_self" in nm0) or ("position" in nm0 and "unit_type" in nm0)
    is_player = by_name or by_struct
    if is_player:
        player_keys.append(k)
    tag = ""
    if is_player:
        tag = "   <== 疑似玩家(%s%s)" % ("名" if by_name else "", "构" if by_struct else "")
    P("  [%s] n=%-3d %s%s" % (k, len(us), hist, tag))

# ---------- 4. 每个"玩家候选"类：代表实例全属性 + 值 ----------
P("\n========== 4. 玩家候选类 代表实例(全属性+值) ==========")
dumped_cls = set()
for k in player_keys:
    for u in (units_of(k) or []):
        cn = cname(u)
        if cn in dumped_cls:
            continue
        dumped_cls.add(cn)
        P("--- [键%s] %s  uid=%s ---" % (k, cn, R(S(lambda u=u: u.uid), 20)))
        nm = names_of(u)
        P("    属性名(%d): %s" % (len(nm), nm))
        d = S(lambda u=u: idict(u), {})
        for a in nm:
            v = d.get(a) if isinstance(d, dict) else S(lambda u=u, a=a: getattr(u, a))
            if v is None:
                continue
            P("      %-26s %s" % (a, irepr(v, 60)))

# ---------- 5. 所有"人"紧凑表：按 INFO 候选字段逐个探存在性 ----------
P("\n========== 5. 玩家紧凑表(逐人) ==========")
def first_present(u, cands):
    out = []
    d = S(lambda u=u: idict(u), {})
    for c in cands:
        if isinstance(d, dict) and c in d:
            out.append("%s=%s" % (c, R(d[c], 24)))
    return out
cnt = 0
for k in player_keys:
    for u in (units_of(k) or []):
        cnt += 1
        P("  [%s] %-22s %s" % (k, cname(u), " ".join(first_present(u, INFO_CANDS))))
P("  (共 %d 人)" % cnt)

# ---------- 6. 非玩家键：各取一个代表，只列属性名(找物资/陷阱结构) ----------
P("\n========== 6. 非玩家键 代表(仅属性名) ==========")
for k in keys:
    if k in player_keys:
        continue
    us = units_of(k) or []
    if not us:
        continue
    u = us[0]
    nm = names_of(u)
    P("  [%s] %s (%d属性): %s" % (k, cname(u), len(nm), nm[:60]))

P("\n[done]")
