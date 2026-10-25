# -*- coding: utf-8 -*-
# probe2 命令：梦之女巫本体 + 信徒的技能冷却采样。
# 要回答：信徒有没有自己的 skill_mgr / skill_dict；各形态的辅助特质冷却是否独立；
#         本体上有没有汇总各信徒冷却的字段。建议：各形态各放一次技能后再跑，跑两次看递减。

SK = ("_cd_delta", "cd_time", "csv_cd_time", "game_start_cd", "power_num",
      "_cur_power_num", "is_leader_skill", "start_cast_time")

cam_u = S(lambda: GK.g_cam_ctrl.unit)
P("now=%.1f  cam.unit=%s uid=%s" % (time.time(), cname(cam_u), R(S(lambda: cam_u.uid), 20)))

def dump_unit(k, u):
    sm = S(lambda: u.skill_mgr)
    P("\n[%s] %s uid=%s is_self=%s owner_uid=%s support=%s model=%s vis=%s" % (
        k, cname(u), R(S(lambda: u.uid), 20), R(S(lambda: u.is_self), 6),
        R(S(lambda: u.owner_uid), 20), R(S(lambda: u.support_skill_id), 20),
        R(S(lambda: u.model.filename), 70), R(S(lambda: u.model.visible), 6)))
    P("   model id=0x%X  skill_mgr id=0x%X" % (id(S(lambda: u.model)) if S(lambda: u.model) is not None else 0,
                                             id(sm) if sm is not None else 0))
    # 名字带 yidhra/puppet/skill/cd 的非技能属性
    for a in attr_names(u):
        la = a.lower()
        if any(w in la for w in ("yidhra", "puppet", "owner", "operat", "cd")) and a != "skill_mgr":
            P("   .%-36s %s" % (a, R(S(lambda a=a: idict(u)[a]), 110)))
    if sm is None:
        P("   (无 skill_mgr)"); return
    P("   leader_skills=%s" % R(S(lambda: sm.leader_skills), 150))
    P("   share_cd_skills=%s" % R(S(lambda: sm.share_cd_skills), 200))
    for sid, s in sorted(S(lambda: list(sm.skill_dict.items()), []), key=lambda x: str(x[0])):
        vals = " ".join("%s=%s" % (f.strip("_"), R(S(lambda f=f: getattr(s, f)), 14)) for f in SK)
        P("   %-6s %-32s id=0x%X %s" % (sid, cname(s), id(s), vals))

seen = set()
for k, u in all_units():
    n = cname(u)
    if k in (1, 236) or "Yidhra" in n or "Butcher" in n:
        if id(u) in seen: continue
        seen.add(id(u)); dump_unit(k, u)
