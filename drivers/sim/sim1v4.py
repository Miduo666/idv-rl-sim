# -*- coding: utf-8 -*-
"""标准 1v4 模拟对局：WorldBattleClientBase(本地服务端) + 5 个角色，可逐个挂人机行为树或留给外部控制。
    core = SimCore(); import sim1v4; w = sim1v4.make_1v4(core, scene_id=1); core.run(300)
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


def install_unit_shims():
    from ClientUnits.GeneratorUnit import GeneratorUnit
    from ClientUnits.BaseUnit import BaseUnit
    for name in ("_ai_slot_keys", "_ai_slot_pos", "init_ai_fix_angle", "precompute_pos_for_ai"):
        if not hasattr(GeneratorUnit, name):
            setattr(GeneratorUnit, name, getattr(ServerGeneratorShim, name))
    if not hasattr(BaseUnit, "sync_pos_dir"):
        BaseUnit.sync_pos_dir = ServerUnitShim.sync_pos_dir


class ServerRoomShim(object):
    """服务端房间方法/属性。每条注明调用处与推断依据。"""
    # QAAIButcher.set_level：room_type 为 CUSTOM/SINGLE_CUSTOM（自定义人机房）时难度取 player_set_ai_level=(监管, 求生者)，
    # 否则按真人求生者段位均值(unit.avatar)算。模拟器对应"自定义房 + 手选难度"。
    room_type = ComuKeys.ROOM_TYPE.CUSTOM
    player_set_ai_level = (ComuKeys.CUSTOM_AI_LEVEL.LV_3, ComuKeys.CUSTOM_AI_LEVEL.LV_3)

    def _get_all_generator_fix_rate(self, fast=False):
        # AICivilian.qaai_is_needed_save / AIEnvCombatUtility.cal_generator_score：
        # sum()>=400 判断修完 4 台、单值与 gen.get_cur_process_nosync() 比较 -> 每台机的破译进度列表
        return [g.get_cur_process_nosync() for g in self.unit_mgr.get_generator_units()]


class WorldSim1v4(ServerRoomShim, WorldBattleClientBase):
    # (pid, 行为树)；行为树为 None = 不挂 AI（留给外部控制）
    BUTCHER = (1, "qaai_butcher_common")                       # 厂长 -> QAAIFactory 选 QAAIButcher
    CIVILIANS = ((14, "qaai_civilian_hard"), (15, "qaai_civilian_hard"),
                 (16, "qaai_civilian_hard"), (17, "qaai_civilian_hard"))
    SELF_ROLE = "butcher"                                       # 客户端必须有一个"自己"(GK.g_unit)

    def __init__(self):
        super(WorldSim1v4, self).__init__()
        # 只有 NOVICE_BATTLE/STORY_BATTLE 等类型会置 is_battle_client（本地服务端）；BATTLE 会被当成联网对局
        self.world_type = ComuKeys.GAME_WORLD_TYPE.NOVICE_BATTLE
        self.rng = random.Random(0)
        self.roles = {}             # uid -> (role, pid, bt)
        self.skada_mgr = SkadaMgrShim()

    def _init_client_battle_info(self, info_dict):
        super(WorldSim1v4, self)._init_client_battle_info(info_dict)
        self.game_type = ComuKeys.GAME_TYPE.KILL

    def _init_units(self, info_dict):
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
            if self.roles[uid][0] == "civilian" and not hasattr(u, "punish_start_timestamp"):
                # 服务端求生者成员。全部脚本只有一处读：QAAIButcher.get_in_butcher_sight_or_chase_civis 判 `civ.punish_start_timestamp > 0`
                # （>0 = 处罚已开始）。开局未受处罚 → 任何 ≤0 的值等价，取 0
                u.punish_start_timestamp = 0

    def attach_ais(self):
        """开局后给配置了行为树的角色挂 AI 之前，先做服务端开局时的密码机修机站位预计算（ServerGeneratorShim）。"""
        for g in self.unit_mgr.get_generator_units():
            g.ai_fix_pos = {}
            g.init_ai_fix_angle()
            g.precompute_pos_for_ai()
        self._attach_bt_ais()

    def _attach_bt_ais(self):
        """开局后给配置了行为树的角色挂 AI。按服务端做法：监管走 QAAIFactory，求生者走 change_ai(AICivilian)。"""
        from common_cs.ai.qaai_butcher.QAAIFactory import QAAIFactory
        for uid, (role, pid, bt) in self.roles.items():
            u = self.unit_mgr.get_unit(uid)
            if u is None or not bt:
                continue
            if role == "butcher":
                if u.ai_controller:
                    u.ai_controller.destroy()
                u.ai_controller = QAAIFactory.create_qaai_controller(pid, u, bt)
                u.reset_ai_flag()
            else:
                u.change_ai(bt)


def utils_fixed_pos(pos_rot, scene_id):
    from common_tools import utils
    return utils.fixed_ow_scene_offset(pos_rot, scene_id)


def make_1v4(core, scene_id=1, world_cls=WorldSim1v4):
    import world as _world
    install_unit_shims()
    n = _world.register_scene_models(GK.DM.pos_info.get(scene_id, {}))
    core._log("[1v4] 场景具名模型 %d 个" % n)
    self_pid = world_cls.BUTCHER[0] if world_cls.SELF_ROLE == "butcher" else world_cls.CIVILIANS[0][0]
    core.on_start.append(lambda w: w.attach_ais())
    return core.make_world(world_cls, scene_id, self_pid)
