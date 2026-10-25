# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：一次性验证若辰拆解里的候选 + 天赋/准备阶段的更好来源。
# 任何阶段都能跑：局外只输出前三节，局内额外输出第四、五节。
gk = GK
t0 = time.time()

def short(v, n=110):
    return R(v, n)

# ---------- 一、阶段判定 ----------
P("== 一、阶段 ==")
P("  g_unit=%s  room=%s.%s" % (cname(me), S(lambda: type(me.room).__module__), cname(S(lambda: me.room))))
keys = sorted([k for k in (S(lambda: list(ubt().keys()), []) or []) if isinstance(k, int)])
P("  units_by_type 键 = %s" % keys)
in_battle = 1 in keys or 2 in keys
P("  局内 = %s" % in_battle)
wm = S(lambda: gk.g_world_mgr)
P("  g_world_mgr = %s" % cname(wm))
for a in ("battle_world", "cur_world", "world_type", "scene_id", "cur_world_type", "world_id"):
    v = S(lambda a=a: getattr(wm, a), "<无>")
    P("    .%-16s %s" % (a, short(v, 90)))
for wn in ("battle_world", "cur_world"):
    w = S(lambda wn=wn: getattr(wm, wn))
    if w is None: continue
    for a in ("world_type", "scene_id", "map_id", "is_battle", "battle_type", "game_mode", "mode", "play_type"):
        v = S(lambda a=a: getattr(w, a), "<无>")
        if v != "<无>": P("    %s.%-14s %s" % (wn, a, short(v, 80)))

# ---------- 二、准备界面 UIRoomWait ----------
P("\n== 二、UIRoomWait ==")
ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
P("  ui_dict 键(类型) = %s" % short([(k, type(k).__name__) for k in list(ui.keys())], 400))
panel = S(lambda: ui.get("UIRoomWait"))
if panel is None:
    P("  没有 UIRoomWait")
else:
    d = S(lambda: idict(panel), {}) or {}
    for a in ("waiting_for_process", "room_guuid", "seat_idx", "members", "role", "copycat_camp_id",
              "b_uid2pid", "b_uid2pos", "uid2pid", "uid2pos", "c_skill_data", "lack_role_1"):
        P("  .%-22s %s" % (a, short(d.get(a, "<无>"), 300)))
    info = d.get("eid_2_player_info")
    if isinstance(info, dict):
        for k, e in info.items():
            if isinstance(e, dict):
                P("  eid_2_player_info[%s] rt=%s pid=%s cloth=%s ss=%s fg=%s ready=%s name=%s" % (
                    short(k, 30), e.get("role_type"), e.get("pid"), e.get("cloth_id"), e.get("support_skill_id"),
                    e.get("final_genius"), e.get("is_ready"), short(e.get("player_name"), 16)))
    else:
        P("  eid_2_player_info = %s" % short(info, 200))
    pt = d.get("player_tips")
    P("  .player_tips = %s" % cname(pt))
    ptd = S(lambda: idict(pt).get("data"), "<无>") if pt is not None else "<无>"
    P("  .player_tips.data = %s" % short(ptd, 500))
    # 名字带 wait/predict/process 的全部列出来
    for a in sorted(d.keys()):
        low = a.lower()
        if any(w in low for w in ("wait", "predict", "process", "butcher", "hunter")):
            v = d.get(a)
            if callable(v): continue
            P("  ~%-22s %-10s %s" % (a, cname(v), short(v, 160)))

# ---------- 三、账号侧花名册 ----------
P("\n== 三、g_avatar ==")
av = S(lambda: gk.g_avatar)
fg = S(lambda: av.final_genius_dict)
P("  final_genius_dict = %s" % short(fg, 400))
pdl = S(lambda: av.player_data_list, []) or []
for i, e in enumerate(pdl):
    if not isinstance(e, dict): P("  #%d %s" % (i, short(e))); continue
    P("  #%d rt=%s pid=%s cloth=%s bot=%s uid=%s eid=%s fg=%s ss=%s ready=%s name=%s" % (
        i, e.get("role_type"), e.get("pid"), e.get("cloth_id"), e.get("bot"), short(e.get("uid"), 14),
        short(e.get("eid"), 40), e.get("final_genius"), e.get("support_skill_id"), e.get("is_ready"),
        short(e.get("player_name"), 16)))

# ---------- 四、局内：天赋三路对照 ----------
if in_battle:
    P("\n== 四、局内天赋对照 ==")
    eid_by_uid = {}
    for e in pdl:
        if isinstance(e, dict) and e.get("uid") is not None:
            eid_by_uid[str(e.get("uid"))] = e.get("eid")
    for ut in (1, 2):
        for u in units_of(ut):
            dd = S(lambda: idict(u), {}) or {}
            gl = dd.get("genius_id_lv_lst")
            term = sorted([g[0] for g in (gl or []) if isinstance(g, (list, tuple)) and g and g[0] in (8, 16, 24, 32)])
            uq = dd.get("unique_id")
            key = str(uq)
            if key not in (fg or {}) and key in eid_by_uid:
                key = str(eid_by_uid[key])
            fgv = (fg or {}).get(key, "<对不上>") if isinstance(fg, dict) else "<无>"
            P("  [%d] %-18s uid=%s unique_id=%r(%s) avatar_id=%s  lst终端=%s len=%s  fg=%s  ss=%s" % (
                ut, cname(u), dd.get("uid"), uq, type(uq).__name__, short(dd.get("avatar_id"), 40),
                term, len(gl) if isinstance(gl, list) else gl, fgv, dd.get("support_skill_id")))

# ---------- 五、局内：若辰候选属性名逐个查存在性 ----------
CAND = {
    "治疗": ["cured_process_client", "_cured_process_client", "cure_process_client", "_cure_process_client",
             "debug_record_cured_info", "_debug_record_cured_info", "cured_uid", "_cured_uid"],
    "动作": ["state", "_state", "status", "state_id", "action", "action_id", "direction", "dir", "forward",
             "cur_move_state"],
    "模型": ["model", "ext_model", "interactive_model", "model_in_scene", "ref_model", "world_model", "role_model",
             "avatar_model", "another_model", "clone_model", "server_model"],
    "身份": ["components", "_components", "identity_id", "role_type", "camp_type", "camp_id", "camp", "_camp",
             "is_ghost", "is_phantom_ghost", "copy_uid", "owner_uid", "mirror_uid", "cache_puppet_uid",
             "_cache_puppet_uid", "unit_hide", "server_hide", "handheld_id_lv", "held_item_id"],
}
ITEM_CAND = ["item_id", "weapon_id", "item_name", "_remain_lifespan", "cur_count", "durability", "amount",
             "remaining_count", "_init_lifespan", "total_power_num", "init_power", "_remain_use_times",
             "_init_use_times", "remain_cd", "item_cd_time", "_left_duration_time", "_b_in_use", "b_in_use",
             "is_using", "in_use", "b_using"]
if in_battle:
    P("\n== 五、若辰候选属性(实例 __dict__ 里有没有) ==")
    shown = set()
    for ut in (2, 1):
        for u in units_of(ut):
            cn = cname(u)
            if cn in shown: continue
            shown.add(cn)
            dd = S(lambda: idict(u), {}) or {}
            P("  --- [%d] %s (%d 条属性)" % (ut, cn, len(dd)))
            for grp, names in CAND.items():
                hit = []
                for nm in names:
                    if nm in dd:
                        v = dd[nm]
                        if grp == "模型":
                            hit.append("%s=%s" % (nm, "None" if v is None else short(S(lambda v=v: v.filename, cname(v)), 60)))
                        else:
                            hit.append("%s=%s" % (nm, short(v, 60)))
                miss = [nm for nm in names if nm not in dd]
                P("     %s 命中: %s" % (grp, "; ".join(hit) if hit else "无"))
                P("     %s 缺失: %s" % (grp, ",".join(miss)))
            # 名字里带 cure/heal 的全部列出来(候选名全错时靠它找真名)
            ch = [(a, short(dd[a], 50)) for a in sorted(dd.keys()) if isinstance(a, str) and
                  any(w in a.lower() for w in ("cure", "heal", "rescue"))]
            P("     *cure/heal* 相关 %d 条: %s" % (len(ch), short(ch, 700)))
            items = S(lambda: list(u.item_lst), []) or []
            for ii, it in enumerate(items[:3]):
                idd = S(lambda it=it: idict(it), {}) or {}
                hit = ["%s=%s" % (nm, short(idd[nm], 30)) for nm in ITEM_CAND if nm in idd]
                P("     item_lst[%d] %s: %s" % (ii, cname(it), "; ".join(hit) if hit else "无命中"))

P("\n# 用时 %.1f ms" % ((time.time() - t0) * 1000))
