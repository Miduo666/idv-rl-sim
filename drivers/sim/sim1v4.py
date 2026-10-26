# -*- coding: utf-8 -*-
"""标准 1v4 模拟对局：WorldBattleClientBase(本地服务端) + 5 个角色，可逐个挂人机行为树或留给外部控制。
    core = SimCore(); import sim1v4; w = sim1v4.make_1v4(core); core.run(300)     # 默认场景 6 = 正式对局军工厂
（本模块顶层就 import 游戏脚本，必须在 SimCore() 设好 sys.path/打桩之后再导入）
人机 AI(qaai_*) 原本跑在服务端房间里；服务端房间/单位的少量方法客户端脚本里没有，按调用处语义补在 ServerRoomShim。"""
import math, random, collections
import game_kernel as GK
import math3d
from common_cs import ComuKeys
from common_cs.h55_utils.utils_math import UtilsMath
from worlds.WorldBattleClientBase import WorldBattleClientBase

SHIM_STATS = collections.Counter()


class ServerGeneratorShim(object):
    """服务端密码机方法：AI 修机站位（SKILL §9.11）。客户端脚本里只有调用、没有定义：
    FoolSystem.set_position_gen 移机后 `gen.ai_fix_pos.clear(); gen.init_ai_fix_angle(); gen.precompute_pos_for_ai()`；
    AICommonTrigger._init_gen_fixdir 用 len(gen.ai_fix_angle) 当可修方位数；PatrolPolicy.patrol_move 用 gen.ai_fix_pos[gen.ai_fix_angle[0]] 当巡逻点。
    - 方位键：fix_pos 的键是 0/90/180/270（iLogicGenerator.init_logic_components）；给 AI 的站位 iLogicGenerator.get_pos_for_ai
      普通机只遍历 (90, 180, 270)、赛马场中心机遍历四个 —— 照此取。录像旁证：真人 12 次修机开始的 range_key 全是 90/180/270（§9.11）。
    - 站位 = 机位置 + 方位向量 × inter_dis × 0.5（get_pos_for_ai 原式；inter_dis = DM.ui_inter[FIX]，军工厂 30）。
    - 推断：站位点在导航上取不到高度的方位剔除（check_inter_pos_valid 第一步就是 get_detour_height，取不到判无效），计入 SHIM_STATS。"""

    def _ai_slot_keys(self):
        return (0, 90, 180, 270) if getattr(self, "racetrack_center_flag", False) else (90, 180, 270)

    def _ai_slot_pos(self, key, inter_dis):
        if getattr(self, "racetrack_center_flag", False):
            return self.get_racetrack_center_logic_pos(key, inter_dis * 0.5)
        dir2 = self.get_direction()
        if key == 90:
            dir2 = UtilsMath.get_anticlockwise_angle_vector2(-math.pi / 2, dir2)
        elif key == 180:
            dir2 = UtilsMath.get_anticlockwise_angle_vector2(math.pi, dir2)
        elif key == 270:
            dir2 = UtilsMath.get_anticlockwise_angle_vector2(math.pi / 2, dir2)
        return self.get_position3() + math3d.vector(dir2.x, 0, dir2.y) * inter_dis * 0.5

    def init_ai_fix_angle(self):
        self.ai_fix_angle = list(self._ai_slot_keys())

    def precompute_pos_for_ai(self):
        inter_dis = GK.DM.ui_inter[ComuKeys.BATTLE_INTER_UI_INDEX.FIX]["inter_dis"]
        if getattr(self, "ai_fix_pos", None) is None:
            self.ai_fix_pos = {}
        keep = []
        for key in self.ai_fix_angle:
            p = self._ai_slot_pos(key, inter_dis)
            if self.room.nav_mgr.get_detour_height(math3d.vector(p), ComuKeys.NAV_MESH_AI) is None:
                SHIM_STATS["修机站位不在导航上，剔除"] += 1
                continue
            self.ai_fix_pos[key] = p
            keep.append(key)
        self.ai_fix_angle = keep
        SHIM_STATS["密码机站位预计算"] += 1


class _NoScore(object):
    """"永不满足"的评分阈值：比较全为假、迭代为空、下标/属性取回自身。"""
    def __lt__(self, o): return False
    __le__ = __gt__ = __ge__ = __lt__
    def __eq__(self, o): return False
    def __ne__(self, o): return True
    __hash__ = object.__hash__
    def __iter__(self): return iter(())
    def __len__(self): return 0
    def __getitem__(self, k): return self
    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return self


class _NoScoreParams(object):
    """服务端 skada_mgr.action_param_cache：各角色"战绩表现"评分的阈值参数（39 个字段，如 lawyer_find_generator_time、dance_tease_p、
    paoku_dash_trigger_dis_lv1）。客户端脚本只读不写，配置在服务端。用途全是 add_civilian_score 加分或表现标志
    （dancer/gardener_tease_butcher_flag 只在初始化与评分里出现）；AI 只读 CURE/CURE_HANG/HOOK_KILL 三种评分（§9.11）→
    全部给"永不满足"的阈值 = 表现评分不触发，对局逻辑不受影响。按字段计数。"""
    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        SHIM_STATS["skada.action_param_cache.%s(不触发)" % n] += 1
        return _NoScore()


class SkadaMgrShim(object):
    """服务端 room.skada_mgr（战斗评分/统计）。
    - 读（AI，全部调用处）：civilian_action_score_recored / butcher_action_count，形状 {uid: {str(行为编号): 次数}}，
      只读 CIVILIAN_SCORE_ACTION.CURE / CURE_HANG、BUTCHER_SCORE_ACTION.HOOK_KILL（HangOutMgr 把 CURE_HANG 直接当 cure_hang_times）。
    - 写：游戏逻辑调 add_civilian_score(uid, 行为[, data])（如 ButcherFlashlight）。推断按"次数 +1"记（方法名 + 读取处当次数用）。
      监管侧的写入方法名在客户端脚本里没见到，出现时按 __getattr__ 记录方法名（SHIM_STATS），再补。
    - 其余方法（check_combat_performance、set_qianfeng_score_params 等，评分表现层）空操作并记录。"""

    def __init__(self):
        self.civilian_action_score_recored = collections.defaultdict(dict)
        self.butcher_action_count = collections.defaultdict(dict)
        self.action_param_cache = _NoScoreParams()

    def add_civilian_score(self, uid, action, *a, **k):
        d = self.civilian_action_score_recored[uid]
        d[str(action)] = d.get(str(action), 0) + 1
        SHIM_STATS["skada.add_civilian_score"] += 1

    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        SHIM_STATS["skada.%s(空操作)" % n] += 1
        return lambda *a, **k: None


class ServerUnitShim(object):
    def sync_pos_dir(self, *a, **k):
        # 服务端把位置/朝向推给客户端的网络同步：iLogicCivilian.leave_cured_range 里 `set_position(...)` 之后 `if SERVER_MODE: sync_pos_dir()`。
        # 本地服务端与客户端共用同一个单位对象，没有要同步的对象 → 空操作
        SHIM_STATS["sync_pos_dir(空操作)"] += 1


def _wood_oneway_tag(self):
    # 服务端窗的单向标志。读处（AICivilian.start_span_window/qaai_span_window/qaai_get_hiding_move_position_new、HidingCircle、
    # iCommonButcher/iCommonMove/iCommonPlayer）都当真值判断或原样传给 player_span_check(uid, 类型, 单向标志)。
    # 客户端同一概念是 InteractiveUnit.oneway_tag（建单位参数 oneway_tag，否则场景模型属性 window_oneway，否则 False）。
    # 模拟器里模型属性是假值桩 → 归一成 bool。
    v = getattr(self, "oneway_tag", False)
    return v if isinstance(v, (bool, int)) else False


def _unit_pos_get(self):
    return self.get_position3()


def _unit_pos_set(self, v):
    self.set_position(v)


def _door_pair_server(orig, mine, other_getter):
    """UnitManager.get_switch_from_door / get_door_from_switch 的服务端分支：按 door_idx 配对。
    AI 跑的是服务端逻辑（AICivilian 把开门目标设成电闸后再调 get_switch_from_door(电闸 uid)，服务端分支返回电闸自身；
    客户端分支去读电闸模型的 'door' 属性，模拟器里没有 → None → qaai_open_door 每帧崩）。两边都有 door_idx 时走服务端分支，否则原样。"""
    def f(self, uid):
        u = self.get_unit(uid)
        idx = getattr(u, "door_idx", None) if u is not None else None
        if idx is not None:
            for s in other_getter(self):
                if getattr(s, "door_idx", None) == idx:
                    return s
            return None
        return orig(self, uid)
    return f


def _door_pos_for_ai_no_overlap(self, civ_uid=None):
    # 服务端大门方法：AICivilian.qaai_set_action('move', DOOR) / AIBattleEvent.handle_escape_event 取逃生站位。
    # 共用层 iLogicDoor.get_pos_for_ai = get_feasible_position3()（门位置沿朝向往外退 run_away_area[1]+DETOUR_SEARCH_HALF，即逃生区里的点）。
    # "no_overlap" 按 uid 怎么错开没有依据 → 推断：取同一点（逃生判定只看是否进入逃生区）。
    SHIM_STATS["door.get_pos_for_ai_no_overlap(推断=get_pos_for_ai)"] += 1
    return self.get_pos_for_ai()


def _ability_has_skill_and_same_level(self, skill_id, level):
    # 服务端 Ability 方法：GlobalHookScoreCal.judge_genius_lv 对 level 0..3 逐个问"带了这个天赋且等级相同吗"，
    # EffectSkillInfoListComponent 同用。客户端 Ability.get_skill_level(id) = passive_skill_dct.get(id)（天赋 id → 等级）。
    d = getattr(self, "passive_skill_dct", None) or {}
    return d.get(skill_id) == level


def _wood_check_lawyer_span(self, uid, lawyer_map_span=False):
    # 服务端窗方法：全部脚本只有 LStateCivilian.enter_state（SPAN，律师 pid 15 翻非墙窗）一处调用，返回值不用（语句调用）。
    # 缺它时进翻窗状态做到一半抛 → SPAN 挂着永不退出 → 倒地后 CATCHED 状态检查不过，监管扛不起来、整局卡死（§9.16）。
    # 实现不在客户端 → 空操作计数（推断是服务端记律师翻窗相关的统计/表现）。
    SHIM_STATS["wood.check_lawyer_span_wood(律师翻窗,空操作)"] += 1


def _with_server_butcher_speed(fn):
    # 服务端单位的 .speed = 配表 move_speed（求生者 CivilianUnit.__init__ 就这么置）；但客户端"自己"(MyButcherUnit) 的 .speed 是
    # 摇杆当前速度：MoveUnit.set_speed/get_speed、BattlePlayerUnit.fix_hud_move_speed 每帧写，停下时 0/None。
    # 服务端 AI 里读 butcher.speed 的只有 AICivilian.qaai_black_cal_hiding（距离/速度比谁先到出口）→ 调用期间换成 move_speed、调完还原。§9.16
    def wrapped(self, *a, **k):
        saved = []
        for b in self.owner.room.unit_mgr.get_butcher_units():
            ms = (GK.DM.player.get(b.pid) or {}).get("move_speed")
            if ms:
                saved.append((b, b.__dict__.get("speed")))
                b.__dict__["speed"] = ms
        try:
            return fn(self, *a, **k)
        finally:
            for b, v in saved:
                b.__dict__["speed"] = v
    wrapped._sim_shim = True
    return wrapped


def install_unit_shims():
    from common_cs.ai.AICivilian import AICivilian
    if not getattr(AICivilian.qaai_black_cal_hiding, "_sim_shim", False):
        AICivilian.qaai_black_cal_hiding = _with_server_butcher_speed(AICivilian.qaai_black_cal_hiding)
    from ClientUnits.GeneratorUnit import GeneratorUnit
    from ClientUnits.BaseUnit import BaseUnit
    from ClientUnits.WoodUnit import WoodUnit
    from ClientUnits.BattlePlayerUnit import BattlePlayerUnit
    from ClientUnits.DoorUnit import DoorUnit
    from ClientUnits.Ability import Ability
    from common_cs.mgr.UnitManager import UnitManager
    if not hasattr(DoorUnit, "get_pos_for_ai_no_overlap"):
        DoorUnit.get_pos_for_ai_no_overlap = _door_pos_for_ai_no_overlap
    if not hasattr(Ability, "has_skill_and_same_level"):
        Ability.has_skill_and_same_level = _ability_has_skill_and_same_level
    # 服务端单位的 .pos = 位置向量（GlobalHookScoreCal.get_game_info 读 civi.pos / but_unit.pos 算距离；AICivilian.qaai_can_dig
    # 临时写 owner.pos = 目标点再写回）。只挂角色基类：CrossSFXUnit/FireworkVolleyBallUnit 自己有普通属性 self.pos。
    if "pos" not in BattlePlayerUnit.__dict__:
        BattlePlayerUnit.pos = property(_unit_pos_get, _unit_pos_set)
    if not getattr(UnitManager.get_switch_from_door, "_sim_shim", False):
        UnitManager.get_switch_from_door = _door_pair_server(UnitManager.get_switch_from_door, "door", lambda m: m.get_switch_units())
        UnitManager.get_door_from_switch = _door_pair_server(UnitManager.get_door_from_switch, "switch", lambda m: m.get_door_units())
        UnitManager.get_switch_from_door._sim_shim = UnitManager.get_door_from_switch._sim_shim = True
    for name in ("_ai_slot_keys", "_ai_slot_pos", "init_ai_fix_angle", "precompute_pos_for_ai"):
        if not hasattr(GeneratorUnit, name):
            setattr(GeneratorUnit, name, getattr(ServerGeneratorShim, name))
    if not hasattr(BaseUnit, "sync_pos_dir"):
        BaseUnit.sync_pos_dir = ServerUnitShim.sync_pos_dir
    if not hasattr(WoodUnit, "wood_oneway_tag"):
        WoodUnit.wood_oneway_tag = property(_wood_oneway_tag)
    if not hasattr(WoodUnit, "check_lawyer_span_wood"):
        WoodUnit.check_lawyer_span_wood = _wood_check_lawyer_span


class ServerRoomShim(object):
    """服务端房间方法/属性。每条注明调用处与推断依据。"""
    # QAAIButcher.set_level / AIEnvCombatLevel.table_data_analysis：room_type 为 CUSTOM/SINGLE_CUSTOM（自定义人机房）时难度取
    # player_set_ai_level=(监管, 求生者)，否则按真人段位均值(unit.avatar)算。模拟器对应"自定义房 + 手选难度"。
    # ⚠ WorldBase.__init__ 会写实例属性 self.room_type = None 盖掉类属性 → 在 WorldSim1v4.__init__ 里再赋一次（§9.16）。
    room_type = ComuKeys.ROOM_TYPE.CUSTOM
    player_set_ai_level = (ComuKeys.CUSTOM_AI_LEVEL.LV_4, ComuKeys.CUSTOM_AI_LEVEL.LV_4)   # LV_4 = 噩梦
    # iLogicGenerator.check_lawyer_fix_generator_score（律师开局找机评分）：先查 dict[uid]，否则取 end_camera_rot_time；
    # 为 None 时函数自己 return（不加分）。两者客户端只读不写（服务端在开局镜头转完时记）→ 取"没有记录"。
    end_camera_rot_time_dict = {}
    end_camera_rot_time = None

    class _NoviceTaskMgr(object):
        # 新手教程任务（worlds.BattleTask）：GeneratorUnit.complete_fixed 等在 world_type == NOVICE_BATTLE 时调 room.task_mgr.send_task_event。
        # 模拟器为了置 is_battle_client 借用了 NOVICE_BATTLE 类型，但不是教程局（task_mgr 只有 WorldBattleClientNovice 有）→ 空操作计数。
        def __getattr__(self, n):
            if n.startswith("__"):
                raise AttributeError(n)
            SHIM_STATS["task_mgr.%s(新手任务,空操作)" % n] += 1
            return lambda *a, **k: None
    task_mgr = _NoviceTaskMgr()
    # 新手局的胜负计数：iLogicCivilian.die / ResurrectionComponent.real_die 在 world_type == NOVICE_BATTLE 时先给
    # cur_world.already_die_num += 1 再调 _die（缺了它淘汰流程在这里中断、被淘汰者永不离场）；只有 WorldBattleClientNovice.game_tick 读。
    already_die_num = 0
    already_win_num = 0

    def get_detour_distance(self, start_pos, target_pos, nav_mesh_type, fast=False):
        # 服务端房间签名多一个 fast（GlobalHookScoreCal.get_game_info 算监管到椅子 fast=True；缺它时选椅子抛，杰克扛人原地不动）。
        # fast 的实现不在客户端 → 一律按精确寻路距离算（客户端 WorldBase 版），fast 调用计数。
        if fast:
            SHIM_STATS["get_detour_distance(fast=True → 按精确距离)"] += 1
        return super(ServerRoomShim, self).get_detour_distance(start_pos, target_pos, nav_mesh_type)

    def process_quick_speech_event(self, info):
        # 服务端房间方法：AICivilian.qaai_send_message 发 AI 快捷发言（{qsid, key, uid, ai[, extra_info]}）。
        # qaai 树里 qsp_history 只有发送方自己写；QuickSpeechComponent 是界面发言记录，没有 AI 读 → 空操作计数。
        # （新架构 novice_civilian_parent 的 ReceiveQuickSpeech 会读历史，换那套 AI 时要重看。）
        SHIM_STATS["process_quick_speech_event(快捷发言,空操作) qsid=%s" % info.get("qsid")] += 1

    def _get_all_generator_fix_rate(self, fast=False):
        # AICivilian.qaai_is_needed_save / AIEnvCombatUtility.cal_generator_score：
        # sum()>=400 判断修完 4 台、单值与 gen.get_cur_process_nosync() 比较 -> 每台机的破译进度列表
        return [g.get_cur_process_nosync() for g in self.unit_mgr.get_generator_units()]


# 监管角色专属行为树 → 控制器类。服务端给人机挂控制器的代码不在客户端（客户端 change_ai 一律给基类 AIButcher）；
# 依据是树里 `ac.*` 调用的方法只有这个类有：qaai_butcher_jack 调 shared_policy / jack_carry_policy / jack_hook_policy /
# jack_guard_policy，只在 AIButcherJack 上（QAAIFactory 的 QAAIButcherJack 一个都没有，是配 qaai_butcher_common 的）。§9.16
BUTCHER_TREE_CONTROLLER = {
    "qaai_butcher_jack": ("common_cs.ai.AIButcherJack", "AIButcherJack"),
}


# 人机天赋 / 辅助特质（§9.19）。服务端按 player_ai_conf[pid].ai_genius_id 查一张客户端没有的方案表，把结果放进建单位参数
# unit_info['genius_id_lvs'] / ['support_skill_id'] 下发；客户端 BattlePlayerUnit.init_passive_skills 再按天赋表展开成被动。
# 方案表拿不到 → 用户 2026-10-27 指定（双方都 130 点）：这里只写点名的天赋 {id: 等级}，前置按配表 pre_genius 补齐。
GENIUS_POINTS = 130
CIVILIAN_GENIUS = {
    # 双弹(膝跳反射 32) + 大心脏(回光返照 16) 两条主线、绝处逢生 26、巨力 31×3、结伴效应 34、宣泄效应 18、救世主情结 19
    "double_heart": {32: 1, 16: 1, 26: 1, 31: 3, 34: 1, 18: 1, 19: 1},
    # 化险为夷 24 + 回光返照 16、避难所 22×3、绝处逢生 26、宣泄效应 18、巨力 31×2
    "save_heart": {24: 1, 16: 1, 22: 3, 26: 1, 18: 1, 31: 2},
}
BUTCHER_GENIUS = {
    # 底牌 16 + 挽留(一刀) 24、破坏欲 5×3、狂暴 6×1、愤怒 7×1
    "card_knife": {16: 1, 24: 1, 5: 3, 6: 1, 7: 1},
}
SUPPORT_SKILL_FLASH = 7            # 辅助特质 7 = 闪现（杰克技能 711；AI 的 SupportSkillAdapter 专门处理 711/722）


def genius_loadout(table, want):
    """点名天赋 {id: 等级} → 补齐前置后的 [[id, 等级], ...]（按 id 排序）与总点数。table = DM.civilian/butcher_genius_data。"""
    need = dict(want)
    stack = list(want)
    while stack:
        row = table[stack.pop()]
        for p, plv in (row[min(row.keys())].get("pre_genius") or ()):
            if need.get(p, 0) < plv:
                need[p] = plv
                stack.append(p)
    points = sum(table[g][l]["genius_point"] for g, lv in need.items() for l in range(1, lv + 1))
    return [[g, need[g]] for g in sorted(need)], points


class WorldSim1v4(ServerRoomShim, WorldBattleClientBase):
    # (pid, 行为树)；行为树为 None = 不挂 AI（留给外部控制）
    # 噩梦难度的人机 = pydata.player_ai_conf[pid].nightmare_ai（§9.16）：杰克 qaai_butcher_jack，求生者 qaai_civilian_rank7。
    BUTCHER = (30, "qaai_butcher_jack")                        # 杰克 -> QAAIFactory 选 QAAIButcherJack
    CIVILIANS = ((14, "qaai_civilian_rank7"), (15, "qaai_civilian_rank7"),     # 医生、律师
                 (17, "qaai_civilian_rank7"), (32, "qaai_civilian_rank7"))     # 园丁、空军
    # 魔术师(21) 暂不用：LSkillCivilianMagicSubstitute 只在 SERVER_MODE 下导入 LogManager，建单位时 NameError（§9.16）
    SELF_ROLE = "butcher"                                       # 客户端必须有一个"自己"(GK.g_unit)
    # pid -> (天赋方案名, 辅助特质 id 或 None)；没列的角色不带天赋（§9.19）
    LOADOUT = {30: ("card_knife", SUPPORT_SKILL_FLASH),
               14: ("double_heart", None), 15: ("double_heart", None), 17: ("double_heart", None),
               32: ("save_heart", None)}

    def __init__(self):
        super(WorldSim1v4, self).__init__()
        self.room_type = ServerRoomShim.room_type      # WorldBase.__init__ 置了 None
        self.player_set_ai_level = ServerRoomShim.player_set_ai_level
        # 只有 NOVICE_BATTLE/STORY_BATTLE 等类型会置 is_battle_client（本地服务端）；BATTLE 会被当成联网对局
        self.world_type = ComuKeys.GAME_WORLD_TYPE.NOVICE_BATTLE
        self.rng = random.Random(0)
        self.roles = {}             # uid -> (role, pid, bt)
        self.skada_mgr = SkadaMgrShim()

    def _init_client_battle_info(self, info_dict):
        super(WorldSim1v4, self)._init_client_battle_info(info_dict)
        self.game_type = ComuKeys.GAME_TYPE.KILL

    def _apply_loadout(self, unit_info):
        """建单位参数里补服务端下发的 genius_id_lvs / support_skill_id（§9.19）。"""
        spec = self.LOADOUT.get(unit_info.get("pid"))
        if not spec:
            return
        plan, support = spec
        butcher = unit_info.get("unit_type") == ComuKeys.UNIT_TYPE_CONF.BUTCHER
        table = GK.DM.butcher_genius_data if butcher else GK.DM.civilian_genius_data
        lst, points = genius_loadout(table, (BUTCHER_GENIUS if butcher else CIVILIAN_GENIUS)[plan])
        if points != GENIUS_POINTS:
            raise ValueError("天赋方案 %s 补齐前置后是 %d 点，不是 %d" % (plan, points, GENIUS_POINTS))
        unit_info["genius_id_lvs"] = lst
        SHIM_STATS["人机天赋 %s（%d 项 %d 点）" % (plan, len(lst), points)] += 1
        if support is not None:
            unit_info["support_skill_id"] = [support]
            SHIM_STATS["人机辅助特质 %d" % support] += 1

    def _init_units(self, info_dict):
        # 两条建单位路径（基类建"自己"、add_units_in_scene 建其余人）都经 unit_mgr.create_add_unit_in_client(类型, unit_info, self_uid)，
        # 服务端的人机配装就在这份 unit_info 里 → 建单位期间包一层补上
        um = self.unit_mgr
        orig = um.create_add_unit_in_client

        def create_with_loadout(unit_type, unit_info, *a, **k):
            self._apply_loadout(unit_info)
            return orig(unit_type, unit_info, *a, **k)
        um.create_add_unit_in_client = create_with_loadout
        try:
            self._init_units_impl(info_dict)
        finally:
            del um.create_add_unit_in_client

    def _init_units_impl(self, info_dict):
        # 基类建"自己"（info_dict.player_id）和场景交互物
        super(WorldSim1v4, self)._init_units(info_dict)
        me = GK.g_unit
        sc = GK.DM.scene_config[self.scene_id]
        everyone = [("butcher",) + self.BUTCHER] + [("civilian", p, bt) for p, bt in self.CIVILIANS]
        mine = 0 if self.SELF_ROLE == "butcher" else 1
        self.roles[me.uid] = everyone.pop(mine)
        # 基类把"自己"放在 butcher_pos_id[0] / civilian_pos_id[0]，其余人从剩下的出生点里随机
        civ_pos = list(sc["civilian_pos_id"][1:] if mine else sc["civilian_pos_id"])
        self.rng.shuffle(civ_pos)
        for role, pid, bt in everyone:
            pos_id = self.rng.choice(sc["butcher_pos_id"][1:]) if role == "butcher" else civ_pos.pop()
            pr = utils_fixed_pos(GK.DM.pos_config[pos_id]["pos_and_rot"], self.scene_id)
            # pid_info_source=0：从 DM.player 取角色（1 才是 npc_data）
            u = self.add_units_in_scene(pid, (pr[0], pr[1], pr[2]), None, None, None, 0, None, False)
            self.roles[u.uid] = (role, pid, bt)
        for uid in self.roles:
            u = self.unit_mgr.get_unit(uid)
            if not hasattr(u, "avatar"):
                u.avatar = None     # 服务端单位上挂真人账号对象；人机为 None（AIHelper.cal_civilian_ave_part 按此跳过）
            if self.roles[uid][0] == "butcher" and not getattr(u, "speed", 0):
                # 求生者 CivilianUnit.__init__ 置 speed = 配表 move_speed（25）；监管单位类没有这一行，客户端一直是 0。
                # AICivilian.qaai_black_cal_hiding 用 距离/butcher.speed 比谁先到出口 → 0 除。按求生者同款规则取配表 move_speed（厂长 56 = speed_real）
                u.speed = GK.DM.player[self.roles[uid][1]].get("move_speed", 0)
            if self.roles[uid][0] == "civilian" and not hasattr(u, "escape_source_hook"):
                # 服务端求生者成员：AIEnvCombatUtility(New).cal_hangcivi_score 判 `u.escape_source_hook and u.escape_source_hook.during_hook_escape`
                # （正在从哪张椅子自救挣脱）。只在 AI 里读、客户端无写入；读前有真值判断 → 默认 None = 没有在挣脱。
                # 缺了它 AICommonTrigger.tick 每次算救人分都抛，整帧 game_tick 后半段被跳过。
                u.escape_source_hook = None
                u.escape_dest_hook = None    # 同上（cal_hangcivi_score 下一行，同样只读、带真值判断）
            if self.roles[uid][0] == "civilian" and not hasattr(u, "punish_start_timestamp"):
                # 服务端求生者成员。全部脚本只有一处读：QAAIButcher.get_in_butcher_sight_or_chase_civis 判 `civ.punish_start_timestamp > 0`
                # （>0 = 处罚已开始）。开局未受处罚 → 任何 ≤0 的值等价，取 0
                u.punish_start_timestamp = 0

    def attach_ais(self):
        """开局后给配置了行为树的角色挂 AI 之前，先做服务端开局时的密码机修机站位预计算（ServerGeneratorShim）。"""
        # AICommonTrigger 在 WorldBattleClientBase.__init__ 里构造，那时房间还没有 scene_id → trigger.scene_id = None，
        # AI 按图的预计算表（CirClePathInfo.CIRCLING_PATHS / PSYWAR_POS、HidingModel.HIDING_DATA，键 = SCENE_ID）全查不到，
        # 绕板转圈 CirCle.init_circling_params 拿不到环路 → 挨刀后 QAAI_HIDING 原地不动（§9.16）。按 __init__ 原样（含教堂映射）重算一次。
        act = self.ai_common_trigger
        sid = self.get_scene_id()
        act.scene_id = ComuKeys.SCENE_ID.CHURCH if sid in ComuKeys.SCENE_ID_GROUP.CHURCH_SCENE_IDS else sid
        # tilecache 导航资源缺（§9.10）：NavManager.load_scene_nav_with_tilecache 登记了 tc 网格名但载入失败 → tc_init_done=False，
        # 游戏自己把动态导航查询（get_detour_path_check_flag、poly 标志）换成 AI 网格。真机 tilecache 是载入的：开动态导航的求生者
        # 去板子中心等点（在真网格上、离 AI 网格 ~4）寻路，换成 AI 网格就失败 → 挨刀后躲藏 start_move_to_cs 每帧 False、原地不动（§9.16）。
        # 置 True 让游戏照真机走 tilecache 名，由 natives/detour 回退到 AI 网格 + 端点/高度边缘吸附（同 §9.14 依据）；动态障碍仍是计数空操作。
        nm = self.nav_mgr
        if nm is not None and not nm.tc_init_done and getattr(nm, "tc_nav_mesh_name", None):
            nm.tc_init_done = True
            SHIM_STATS["nav tc_init_done=True（tilecache 缺，由 AI 网格近似）"] += 1
        for g in self.unit_mgr.get_generator_units():
            g.ai_fix_pos = {}
            g.init_ai_fix_angle()
            g.precompute_pos_for_ai()
        # 服务端门/电闸的 door_idx（建单位参数，服务端填；日志代码按字符串 '1' 比较）= 场景模型属性 door / switch_l 的值（DM.pos_info 第 4 列）
        for kind, units in (("door", self.unit_mgr.get_door_units()), ("switch_l", self.unit_mgr.get_switch_units())):
            for u in units:
                if getattr(u, "door_idx", None) is None and u.model is not None:
                    v = u.model.get_attr(kind)
                    if isinstance(v, str):
                        u.door_idx = v
                        SHIM_STATS["door_idx 取场景属性 %s" % kind] += 1
        self._attach_bt_ais()

    def _attach_bt_ais(self):
        """开局后给配置了行为树的角色挂 AI。监管：角色专属树用对应的旧版控制器（BUTCHER_TREE_CONTROLLER），
        通用树走 QAAIFactory；求生者走 change_ai(AICivilian)。"""
        from common_cs.ai.qaai_butcher.QAAIFactory import QAAIFactory
        for uid, (role, pid, bt) in self.roles.items():
            u = self.unit_mgr.get_unit(uid)
            if u is None or not bt:
                continue
            if role == "butcher":
                if u.ai_controller:
                    u.ai_controller.destroy()
                spec = BUTCHER_TREE_CONTROLLER.get(bt)
                if spec:
                    mod, cls = spec
                    u.ai_controller = getattr(__import__(mod, fromlist=[cls]), cls)(u, bt)
                else:
                    u.ai_controller = QAAIFactory.create_qaai_controller(pid, u, bt)
                u.reset_ai_flag()
            else:
                u.change_ai(bt)


def utils_fixed_pos(pos_rot, scene_id):
    from common_tools import utils
    return utils.fixed_ow_scene_offset(pos_rot, scene_id)


def make_1v4(core, scene_id=None, world_cls=WorldSim1v4):
    # 默认 = 正式对局军工厂 scene_config[6]（ComuKeys.SCENE_ID.FACTORY）。scene_config[1] 是新手版军工厂（同一套资源、pos_info 相同），
    # 但 AI 的按图数据表只有 6 → 用 1 时绕板/心理战/躲藏数据全缺（§9.16）。
    if scene_id is None:
        scene_id = ComuKeys.SCENE_ID.FACTORY
    import world as _world
    install_unit_shims()
    n = _world.register_scene_models(GK.DM.pos_info.get(scene_id, {}))
    core._log("[1v4] 场景具名模型 %d 个" % n)
    self_pid = world_cls.BUTCHER[0] if world_cls.SELF_ROLE == "butcher" else world_cls.CIVILIANS[0][0]
    core.on_start.append(lambda w: w.attach_ais())
    return core.make_world(world_cls, scene_id, self_pid)
