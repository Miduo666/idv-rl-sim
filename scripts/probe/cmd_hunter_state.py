# -*- coding: utf-8 -*-
# probe2 命令(2026-10-25)：自动盖板"游戏砸不晕/砸不中"判据的活体核对。
# 静态结论(auto-pallet.md 顶部)要在【求生者视角、看别人的监管】下确认这几个东西读得到、而且会变：
#   super_armor          霸体(iCommonPlayer.set_super_armor 客户端直接写这个属性)
#   exchange_move_info   传送/交换的客户端滑行(ButcherUnit.set_exchange_move_pos 写 dict，滑完清掉)；
#                        服务端在滑行开始前就已经 set_position 瞬移到终点，滑行只是表现
#   skill_mgr.current_skill  正在放的技能 id(台球手滚球 14714/14715/14716 等砸不晕的技能靠它判)
#   state_machine 的状态集合(_state)  StateMachine 继承 cython 的 StateMachineStatic，可能不在 __dict__ 里
#   _current_yidhra_puppet_uid(女巫) / 信徒 uid
# 叠加层是驱动裸读 __dict__，所以每项都打印"在不在实例字典里"，不在的话 C++ 那边读不到。
#
# 怎么跑：当求生者，在监管放技能的【那一刻】跑(台球手滚球、传送落地前后、兴奋/闪现时)。
#   一次只采一帧；要抓瞬间就在 PowerShell 里连发：
#   for ($i=0; $i -lt 8; $i++) { .\send_cmd.ps1 cmd_hunter_state.py hs }
gk = GK
P("==== TIME %.2f ====" % time.time())
me = S(lambda: gk.g_cam_ctrl.unit)
P("me=%s uid=%s" % (cname(me), S(lambda: me.uid)))

def indict(o, k):
    d = S(lambda: idict(o), None)
    if not isinstance(d, dict):
        return "无__dict__"
    return ("在dict=%s" % R(d[k], 90)) if k in d else "不在dict"

def dump_sm(u):
    sm = S(lambda: u.state_machine)
    if sm is None:
        P("    state_machine=None"); return
    d = S(lambda: idict(sm), None)
    P("    state_machine=%s  有__dict__=%s  _state:%s" % (cname(sm), isinstance(d, dict), indict(sm, "_state")))
    P("    sm.state=%s  get_all_states=%s" % (R(S(lambda: sm.state), 80), R(S(lambda: sm.get_all_states()), 80)))
    P("    super_armor_state=%s" % R(S(lambda: sm.super_armor_state), 40))

def dump_skill(u):
    m = S(lambda: u.skill_mgr)
    if m is None:
        P("    skill_mgr=None"); return
    cur = S(lambda: list(m.current_skill), None)
    P("    skill_mgr=%s current_skill:%s  current_skill_ex:%s" % (cname(m), indict(m, "current_skill"), indict(m, "current_skill_ex")))
    for sid in (cur or []):
        so = S(lambda sid=sid: m.skill_dict.get(sid))
        P("      cast %s -> %s skill_type=%s" % (sid, cname(so), S(lambda so=so: so.skill_type)))

for key in (1, 236):
    for u in (S(lambda key=key: units_of(key), []) or []):
        P("\n[%d] %s uid=%s self=%s" % (key, cname(u), S(lambda u=u: u.uid), S(lambda u=u: u is me)))
        for k in ("super_armor", "exchange_move_info", "_current_yidhra_puppet_uid", "broken_wheel", "carry_uid"):
            P("    %-27s %s" % (k, indict(u, k)))
        if key == 236:
            for k in ("_state", "is_self", "operating", "_master_uid"):
                P("    %-27s %s" % (k, indict(u, k)))
        dump_sm(u)
        dump_skill(u)
