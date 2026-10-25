# -*- coding: utf-8 -*-
"""标准 1v4 模拟对局：WorldBattleClientBase(本地服务端) + 5 个角色，可逐个挂人机行为树或留给外部控制。
    core = SimCore(); import sim1v4; w = sim1v4.make_1v4(core, scene_id=1); core.run(300)
（本模块顶层就 import 游戏脚本，必须在 SimCore() 设好 sys.path/打桩之后再导入）
人机 AI(qaai_*) 原本跑在服务端房间里；服务端房间/单位的少量方法客户端脚本里没有，按调用处语义补在 ServerRoomShim。"""
import random
import game_kernel as GK
from common_cs import ComuKeys
from worlds.WorldBattleClientBase import WorldBattleClientBase


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

    def attach_ais(self):
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
    n = _world.register_scene_models(GK.DM.pos_info.get(scene_id, {}))
    core._log("[1v4] 场景具名模型 %d 个" % n)
    self_pid = world_cls.BUTCHER[0] if world_cls.SELF_ROLE == "butcher" else world_cls.CIVILIANS[0][0]
    core.on_start.append(lambda w: w.attach_ais())
    return core.make_world(world_cls, scene_id, self_pid)
