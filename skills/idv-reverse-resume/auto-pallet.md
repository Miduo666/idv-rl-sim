# 自动盖板 —— 逆向参考

> **★★ 2026-10-26 调研：延迟 → 防"小幅进区骗板"（纯静态，std_pyc 反汇编；工具 `逆向\第五人格_脚本解包_反作弊\tools\cdis.py <路径子串> <函数名,…>` 按源码行压缩反汇编）**
> **移动同步链（坐实）**：
> - 监管客户端 `iSync.hud_move`：摇杆方向/速度**一变就发**(否则每 `player_isync_move_inv` 帧一发)，包里 `speed_dir/speed/pos/current_delay`(=自己的 `cur_delay_time[BATTLE]`)。
> - 服务端 `JoystickMoveComponent.process_joystick_move_event` → `iLogicPlayer.hud_move`：`check_server_pos(客户端pos)` 只用来调 `speed_ratio`/`server_speed_ratio`(差距 <10 单位 1.0，越大越慢)，
>   `cache_speed_dir = 客户端方向` **立即生效(掉头瞬时)**，然后**服务端自己按方向模拟走**(`move_logic` → `calculate_next_position`，`pos = now + dir·speed·Δt·server_speed_ratio`)。
>   ⇒ **服务端的监管位置 ≈ 监管客户端轨迹整体延后 u_h(他的上行)**，不是"包里位置+外推"。
> - 服务端 `send_client_pos`：给监管本人发 `client_pos`(多走 `delay_time/1000·speed`，补他自己的延迟)，**给其他人发服务端 `pos`**，每次服务端走一步都广播。
> - 我方客户端 `JoystickMoveComponent.handle_joystick_move_event` → `MoveUnit.handle_hud_move` → `start_move_to(服务端pos)`：路径 [当前, 目标]，`_cal_tractive_force` = 朝目标×speed，
>   **追到就停，不外推**。⇒ **我们画面上的远端监管 = 服务端位置落后 (下行 + 半个服务端 tick)**，掉头时画面不会冲过头，只会比服务端浅。
> - **你贴的那个 `predict_pos = pos + dir·speed·(我的延迟/2 + net_delay)` 只在 `TransformComponent._handle_dir_sync_event` 且包里带 `predict_params` 时生效，
>   `predict_params` 全库只有 `VSkillCivilianSprintRun`(前锋冲刺) 发**。监管正常移动不走这条，对监管的延迟"补偿"不存在。
> **放板链（坐实）**：点按钮 → `MyCivilianUnit.handle_putdown_panel`(当场重跑 `find_putdown_panel_uid`，不吃按钮节流) → `iSync.panel_putdown` 立即发(带 `client_pos` + `near_butcher`=我方画面里最近监管的 pos/dir)
> → 服务端 `PanelInteractComponent.process_panel_event` → `iLogicCivilian.panel_putdown`(校验) → `change_state(PUT_PANEL)` → `LStateCivilianPutPanel.enter_state` → `iLogicPanel.on_putdown_start`
> → `addTimer(hit_check_time_data[0]/rate = 0, check_hit_butcher_wrapper)`，之后每 `hit_check_interval` 一次直到累计 `hit_check_time_data[1]`。
> **没有任何回溯/延迟补偿**：判定用的是服务端此刻的监管位置；`near_butcher` 只进 `check_auto_put`(记录)。
> **推论（W = 我们读到场景坐标 → 服务端第一次判定 的总时间）**：
> - W = 下行(画面落后服务端) + 追赶滞后 + 我们 10ms 轮询 + 注入→游戏帧处理 + 上行 + 服务端处理 tick + 首次判定定时器 ≈ **我方 RTT + 本地/服务端开销(估 ~100ms，未测)**。
>   **监管自己的延迟 u_h 两头抵消，不进 W**(服务端看他和判他用的是同一份延迟后的轨迹)。⇒ 对方 `net_delay` 对这件事没用。
> - 掉头是瞬时的 ⇒ 最坏情况：监管在我们读到之后立刻反走。设 s = 监管沿自身运动方向在判定区里的坐标(入口 −10 … 出口 +10，区宽 y<10 两侧共 20 单位)，v = 实测速度(常态 ≤56)：
>   **保证砸中 ⇔ s_obs − v·W > −10(骗不了) 且 s_obs + v·W < 10(冲不出去)**，两者同时可能 ⇔ **v·W < 10 ⇔ W < ~0.18s**(v=56)。旧笔记按 16 算的 0.29s 作废。
> - 现版本触发点：哪条轴是纵深未核对。若辰三档"暴力 12/演戏 8"改的是 perp ⇒ **大概率「触发宽度」(perp，半宽 6+0.38)才是纵深**，along(固定 8.63)是沿板长。
>   按 perp=纵深：监管进区 3.6 单位就点 ⇒ 进深 p < (v·W + 3.6)/2 的假动作能骗到。开「显示判定范围」看矩形哪条边垂直于通道即可确认。
> - **"缩小触发纵深"就是这个方案本身**(2026-10-26 和用户对齐)：条件对称，等价于 |s_obs| ≤ h 才点，**不被骗 ⇔ h ≤ 10 − v·W**；
>   冲过去的监管不受 h 影响(−h + v·W < 10 在 v·W<10 时恒成立)。h 缩过头的代价只有：边缘站着出刀/停住的监管不触发、采样点变少。
>   延迟的边际价值 = 把 h 定在"刚好骗不到"的最大值并随 RTT/监管速度变；ping 稳的话固定值拿到大部分收益；v·W ≥ 10 时任何 h 都骗得到，延迟能告诉你这一点。
> - 本地人机局(MODE_CS)`get_cur_delay_time` 恒 16 ⇒ **人机局测不出线上延迟下的效果**。
> **方案草案（未定、未写代码）**：触发深度 k = v·W(随实时 RTT 变)，只在 s_obs ∈ [−10+k, 10−k] 时点；区间为空(网差)时按用户设的"防骗↔保砸中"倾向在两端之间取；
> 快速预判的 `lead_ms` 改成 W(替代写死 350)。RTT 读 `ui_dict['UIBattle'].cur_net_delay`(与 `cbtn_alpha_st` 同 dict)。
> **待测**：本地开销常数。每次自动点击的「板子状态已变化 用时」≈ 注入+上行+服务端+下行 ≈ W 的主体，旁边打一行 `cur_net_delay` 即可标定 W ≈ 用时 + ~30~50ms(追赶+首检定时器)。
> 未核：服务端 move tick / timer tick 频率(按 0.033 常量推 30Hz)、`addTimer(0)` 是否同 tick 触发、`hit_check_time_data` 单位换算(沿用旧结论 1.1s)。

> **★ 2026-10-25 调研：人机(求生者 AI)怎么放板 —— 不瞄准砸晕，是提前防守放**(工具 `逆向\第五人格_脚本解包_反作弊\tools\bttree.py <bt名>` 打印行为树)
> 两套 AI，都在服务端跑、读的是逻辑层数据(不经网络延迟)：
> - **qaai 系(13 个 `qaai_civilian_*`，easy~hard、rank0~2 参数完全相同)**：躲藏策略里"躲藏目标是板"那支：
>   我在板 20 单位内(`IsInHidingTargetInteractionRange 20`) + 板在我和监管之间(`SideOfHidingTargetBetweenButcherCivi`) + 板没倒没毁
>   + 板和监管之间没别的求生者 + 难度随机(`rank0_random(1, civilian_param['invalid_inter_param']) <= 2` 时当板无效) 之后：
>   **监管三维距离 45~160 单位(3.8~13.5m)→ 直接放**；**< 45 单位且监管处于 `SKILL_ATTACK`(正在出刀)→ 放**；< 45 但没出刀 → 不放。
>   放的动作 `AICivilian.qaai_put_down_panel` → `AIHelper.c_try_to_putdown_panel` → `owner.panel_putdown(uid, 自身朝向, 板朝向, cos)`，不看砸中区。
> - **老 AI(`ai_pingmin_health_new*` 等 10 个)**：`AICivilian.should_putdown_panel(maxTriggerRange)`：监管到我的**寻路绕行距离**
>   (`room.get_detour_distance(..., NAV_MESH_AI)`)≤ 100 单位(多数；929 版 300/600，测试树 150) + 我和监管**不在**板的同一侧(`on_same_side_2d`，80°)→ 放。
>   之前 `AvoidButcherByWood` 先跑到板的另一侧。
> - **结论**：网易自己的 AI 没有"等监管进砸中区再放"的逻辑，砸晕全靠"近身出刀时放"(`SKILL_ATTACK` 是出刀后摇，不可能是假动作)。
>   对我们唯一可借鉴的是"监管在出刀就放"这个**防假动作信号**——但要读状态机(cython 基类，读法未验)，没做。
>
> **★★★★★ 2026-10-25：女巫/信徒/约瑟夫已落地 + 技能表更正 + 霸体/传送/台球手判据（产物 `jzpwbfse.sh` md5 `a709c7af…`，已推 `/data/`，未上机）**
> 用户定：1 女巫本体忽略、2 信徒只算正在被操控的、4 约瑟夫同世界 → 做；3 传送、5 霸体、6 台球巡逻等技能 → 只查。翻窗/翻板/踩板/跳/楼梯用户说没价值，别做。
> - **落地(只改 `PySelf.h`，AutoPallet 只改注释)**：collect_units 对 [1] 读 `_current_yidhra_puppet_uid`(ButcherUnit.__init__ 必设，非女巫=None→read_int 失败)，
>   读出 int = 女巫 → 本体不进 `hunters`、uid 记进 `yidhra_ops`；[236] 在 [1] 之后扫，`uid ∈ yidhra_ops` 的信徒进 `hunters`(当普通监管处理，测速/预判同一套)。
>   `hunter_in_photo[]` 与 hunters 对齐(= uid ∈ PhotoUnit._players，已有的 unit_in_photo)；`hunter_bodies()` 只返回 `hunter_in_photo == in_mirror` 的。
>   依据：`PhotoUnit.initial` 对 `get_butcher_units()` 也按 `in_photo(uid)` enter/leave ⇒ 约瑟夫进相中世界时他的 uid 也在 `_players` 里。
>   服务端 `room.check_in_same_world` 不在客户端脚本里(客户端 `check_in_same_world_general` 恒 True)，同世界判据是按 _players 推的。`hunter_body`(预知)不变。
> - **★ 技能表更正**：`SkillBase.init_skill_state`：`skill.skill_state_fix = state_table_data.get(params['skill_state_fix'])`，没有就退回 `butcher_state[state_id]`；
>   `params = DM.get_skill_state_fix_data(skill_id)` = `pydata/skill_state_fix.data[skill_id][阶段]`(含 `skill_state_fix`/`state_id`/`unit_type`)。
>   ⇒ `skill_state_table` 的键是 **skill_state_fix 编号**，不是 SKILL_TYPE。上一版按 SKILL_TYPE 名字对是巧合重叠，结论作废。
>   正确算法见脚本(`逆向\第五人格_脚本解包_反作弊\tools\skill_hit.py` + `loadpd.py`，输出存同目录 `skill_hit_blocked_20261025.txt`；
>   同目录 `fdis.py` = 按函数名反汇编 std_pyc、`pyc_grep.py`/`pyc_names.py`/`sa_ctx.py` = 搜名字/看上下文；配表行压缩格式补全：`(基准, n, k1,v1…kn,vn, 删除键…)`，尾部多出的是**从基准行删掉的键**；
>   技能中文名 = `pydata/skill.name_tid` 查 `intl_tid/tid_chs_en.json['chs']`)：
>   监管技能阶段 1696 个，**砸不晕只有 40 个**：小丑 `SAW_STOP`(冲刺撞墙/撞板收尾)、`MOUTH_*`(1613~1619 雾隐/离魄移魂)、`SWORDMAN_CHANGE_HOLE`、
>   `BELLOWS_CHANGE_WIND_SPEED`(风域掌控)、迷宫鬼 `MAZEGOST_*`(飞/附身/浇筑/传送)、`SP_ACROBAT_CIRCLE_CHANGE`/`CANCEL`、`GROCER_ABILITY_SWITCH`、
>   **台球手(pid 147「台球手」马库斯·索恩)**：14710 假想妖上杆开始、14712 上杆结束、**14714 滚主球(state 200 BILLIARDS_PATROL，anim billy_myball_run)**、14715/14716 xball_run；
>   `SP_INSECT_TELEPORT*`(15118~15122)。**传送(741-744 等)、闪现、女巫寄生/传道、小丑抬锯/蓄力/冲刺、移形 全部可以砸晕**。
> - **传送**：服务端 `LSkillSpellTeleporting.finish_skill` 直接 `room.set_position(终点, force)` 瞬移；客户端 `VSkillSpellTeleporting.finish_skill`
>   才 `set_exchange_move_pos(终点, 0.5, …)` 演 0.5s 直线滑行 ⇒ **滑行时服务端人已在终点，滑过板子不可能砸中，落点在区里才可能**。
>   判据：`ButcherUnit.exchange_move_info`(dict，滑行中非 None，`exchange_move_ongoing` 就看它)。厂长交换/守卫/幻影传送也走它。
> - **霸体**：客户端 `iCommonPlayer.set_super_armor` 直接写 `unit.super_armor = tag`(SuperArmorComponent.sync_super_armor_event 下发)。
>   来源：兴奋(LSkillSpellClarify，`add_armor_timer(clarify_dur)`)、卡牌闪现霸体、破轮轮形态(`broken_wheel_super_armor`)、swordman/fog/spinsect 部分技能、磁铁推拉/缚刃等状态。
>   游戏在几何判定前就排除霸体 ⇒ **不置 has_hit**，霸体在 1.1s 窗口内结束仍可能砸晕，代价比传送小。
> - **台球手球形态 = 霸体(静态坐实，2026-10-25 追查)**：`BilliardComponent.billiard_change_model(unit, online)`(客户端)把 `unit.model ↔ another_model` 对调
>   (球模型存在 unit 属性 `BilliardOnlineModel`)，并 `unit.broken_wheel_super_armor(online, from_skill=SuperArmorID.BILLIARD_BALL)` ⇒ **`unit.super_armor = True`**；
>   服务端 `billiard_change_property` 同样开霸体、`special_pid = HERO_ID_MAP.BILLIARD_BALL`。破轮轮形态也是 `broken_wheel_super_armor` ⇒ 同一个字段。
>   ⇒ 游戏 `is_butcher_can_hit` 里 `not bt.super_armor` 就把球形态台球手排除了(连几何都不算)。**读 `super_armor` 一个 bool 就覆盖：台球手球形态 + 破轮轮形态 + 兴奋等**。
>   游戏自己判滚球用 `state_machine.has_state_ex(BUTCHER_STATE.BILLIARDS_PATROL)`(iLogicPanel.check_units_in_panel、客户端 util_prophet.find_in_sight_butcher)，
>   但状态是 set、且 StateMachine 有 cython 基类 → 不如 super_armor 好读。各单位类都有 `XxxStatic` cython 基类(BaseUnit/PlayerUnit/ButcherUnit/iCommonPlayer…)，
>   但 model/uid/b_catch/out_photo_uid 照样在 __dict__ 里能读 ⇒ super_armor 大概率也在，探针确认。上杆开始/结束(14710/14712)是过渡段，未必有霸体。
> - **还差活体**：`逆向存档\_scripts\cmd_hunter_state.py`(求生者视角看别人的监管)核对 super_armor / exchange_move_info / skill_mgr.current_skill / state_machine._state
>   是否在实例字典里、会不会变。`StateMachine` 继承 cython `StateMachineStatic`，`_state` 可能不在 __dict__ ⇒ 台球手优先走 `skill_mgr.current_skill`。
>
> **★★★★ 2026-10-24：游戏"板子砸中监管"的完整过滤逻辑（标准字节码反汇编坐实，`std_pyc` 见 `逆向\第五人格_脚本解包_反作弊\SKILL.md` §9）**
> 链：`iLogicPanel.on_putdown_start` → 定时器 `check_hit_butcher_wrapper`(每 `hit_check_interval`，累计到 `hit_check_time_data[1]`，按放板速率缩放)
> → `check_hit_butcher` → 命中的监管逐个 `process_*` → `process_panel_hit_butcher` → 状态机 `change_state(HIT_BY_PANEL=18)`。
> 1. **只在板子 `state==USEING` 且本板 `has_hit==False` 时检测**；同一 tick 里命中的全部算，之后 `has_hit=True` 不再检测。
> 2. **候选** = `get_butcher_units()`(units_by_type[1] 里 `is_puppet is False and not is_patrol_puppet`，巡视者不算) + `get_yidhra_puppet_units()`(信徒)。
> 3. **`is_butcher_can_hit`**：`if bt.is_yidhra_puppet and not bt.is_alive(): False`；否则 `not bt.super_armor and check_in_same_world(板, bt) and not bt.is_yidhra()`。
>    `ButcherUnit.is_yidhra()` = `_current_yidhra_puppet_uid is not None` ⇒ **女巫本体永远砸不中**；**信徒活着就能砸(不管有没有被操控)**；霸体不砸；不同世界(约瑟夫相中世界)不砸。
>    `_current_yidhra_puppet_uid` = 女巫当前操控单位 uid(操控自己=本体 uid)，`YidhraComponent.broadcast` 同步到所有客户端。
> 4. **几何 `iCommonPanel.is_unit_in_hit_range`**：`cos=get_cos_angle_of_unit(unit, 板)`、`dist=三维距离`、`y=|dist·cos|`(沿板朝向)、`x²=dist²−y²`；
>    USEING 时 `y_max = panel_hit_range[0] − panel_hit_range[2]`，**命中 = y < y_max 且 x² < range[1]²**。配表 (13,12,3) ⇒ **检测时恒为 y<10、|x|<12(含高度)**。
>    ⚠ **更正**：下面旧笔记写的"USEING 时 13+3=16"是错的，是**减** 3，等于 10。高度进 x²，离地约 1m 砸不中(孽蜥空中)。
> 5. **遮挡不参与判定**：`check_hit_butcher` 里 `is_unit_covered_between`(高度 5/15 各测一次)只拼进日志 `extra_info`，结果不用于判断。
> 6. **特殊监管处理**(命中后)：①黑暗侦探 `HERO_ID_MAP.DARK_DETECTIVE`(技能 3601 飞扑攻击中、有 `dark_target_uid`)：带 buff `DARK_DESTROY_PANEL_HIT` 时**板被毁、不晕**并去 buff，否则加 buff 后照常走下去；
>    ②小丑 `SAW_SPRINT` 中：放板人在冲刺朝向一侧(夹角 <0.6π 且不是 slide_man_steal)时冲刺技能对放板人结算命中，然后照常砸晕小丑；
>    ③孽蜥 `WILDMAN_HIT_DURING`(落地扑击)中：`must_hit_unit(放板人)` 再照常砸晕。
> 7. **`process_panel_hit_butcher`**：`SAW_STOP` 中先结束它；扛人中(`CATCHING/CATCH` 且 `carry_uid`)→ `set_state_in_catch_panel`(走 HIT_BY_PANEL_CARRY 那套)；
>    否则 `state_machine.check_state(HIT_BY_PANEL)` 通过才 `change_state` 晕；**不通过什么都不做，但 `has_hit` 已置位(这块板浪费了)**。
> 8. **状态机**(`StateMachine.check_state`)：普通状态查 `pydata/butcher_state.data[当前状态][新状态]`(结果码 INVALID0/CMD_VALID1/LOGIC_VALID2/VALID3/COEXIST4/AFTER_PLAY5，缺省=INVALID)；
>    行压缩格式 `(基准行, 覆盖条数, 状态, 值, …)`。**切不进 18(砸不晕)的当前状态 35 个**，主要有：SPAN 翻窗 / SPAN_PANEL 翻板 / BREAK_PANEL 踩板 /
>    JUMP、JUMP_END 跳(下高台) / CATCHING、CATCH 扛人(另走 carry 分支) / ON_STAIRS 楼梯 / **WHEEL_MOVING 破轮轮形态** / SKILL_CHANNEL_B / HIT_BY_PANEL_CARRY /
>    接电话三态 / 开关杯 / RIDE_CARRIER、RIDE_HORSE / TRAMCAR_* / REVIVE_HOOK / LOOP_TP / MAZEGHOST_* / POSSESS_IDLE / BILLIARDS_PATROL 等。
>    IDLE/MOVE/攻击(SKILL_ATTACK、SKILL_END)/HIT_STUN/SKILL_CHANNEL(47)/FLASHED 等 72 个可以。
>    (这 35 个 2026-10-25 用补全后的解压逻辑重算过，一致。)
>    ~~技能状态另查 `skill_state_table[skill_type][18]`：传送滑行/女巫技能砸不晕~~ **← 错了，更正见上面 ★★★★★ 一节**(表的键不是技能类型)。

> **★★★ 2026-10-24：孽蜥飞天 / 破轮轮形态 不放板 + 联合狩猎多监管（产物 `ghtfpcre.sh` md5 `1d22b1d2…`，已推 `/data/`，未上机）**
> 用户定的范围：**只做这三项**。同轮写过的传送/霸体/梦之信徒/防假动作一版(`wgksljiq.sh`)被用户否决("逻辑奇怪、不优雅、乱")，已整体还原，
> 别再原样加回。改动(`AutoPallet.h` + `PySelf.h`)：
> - **孽蜥飞天**：孽蜥脚本代号 `wildman`(`common_cs/skills/wildman/jump/LSkillWildmanJump{Before,During,…}`、`WILDMAN_MULTI_JUMP`)，模型 `lizard`。
>   游戏砸中用三维距离(`is_unit_in_hit_range`：x²=dist²−y²<12²)⇒ 离地约 1m 以上砸不中。实现 = `hit_test` 加一行：
>   **监管与自身脚底高度差 > 15 单位(≈1.26m)不判**(对所有监管生效，同样挡住楼上楼下)。删掉了原 `TODO(孽蜥)`。
>   注：`check_hit_butcher` 对 `WILDMAN_HIT_DURING`(落地扑击)走 `process_wildman_hit_butcher_hitted`(must_hit)，落地那下照常可砸。
> - **破轮轮形态**：`ButcherUnit._recover_broken_wheel` 在 `broken_wheel` 真时 `visual._change_another_model` ⇒ 当前 model = `xxx_wheel.gim`
>   (cloth 表里每款皮肤都有一个；`polun_e_pzz_wheel_dingzi` 是钉子)。判据：场景类名含 `polun`+`wheel`、不含 `dingzi` ⇒ 这个监管整轮不参与。
>   只剩轮形态破轮时状态行显示「破轮轮形态(不放板)」。
> - **联合狩猎(2v8)**：旧版只看 `PySelf::hunter_body`(units_by_type[1] 第一个)⇒ 第二个监管冲过来不触发。
>   新增 `PySelf::hunter_bodies()`(Snapshot.hunters[]，[1] 里全部非巡视者非镜像，上限 4)；盖板对每块板逐个监管判，任一命中(或预判命中)就算。
>   测速历史改成每个监管一份(`Track`，按场景对象找，满了顶掉最久没见的)——共用一份会被两个监管轮流清空。状态行 `监管N 最近…`。
>   `hunter_body` 不变(预知仍用第一个)。**梦之女巫没动**：仍只算本体，信徒(236)不算。
> - **配置**(draw_Gui.cpp)：启动第一帧 `config_snapshot_defaults()` + `config_load(true)` 自动读 `/data/IdentityV_config.txt`(不存在静默)；
>   「读取配置」按钮 → 「恢复默认配置」(`config_restore_defaults()`，从快照还原、只改内存，写回需再点保存)。
> - **上机看**：孽蜥起跳/滞空不放板；破轮变轮后不放板；联合狩猎两个监管都能触发；配置启动即生效(提示「已读取 N 项」)。
>
> **同轮调研、未采用的结论(备查，不是待办)**：
> - 游戏判砸中目标 `iLogicPanel.check_hit_butcher` = `get_butcher_units` + `get_yidhra_puppet_units`(信徒能被砸)，`is_butcher_can_hit` 查 `super_armor`(霸体砸不晕)。
> - 传送 `VSkillSpellTeleporting.finish_skill` 客户端 `set_exchange_move_pos(…)` 直线滑行(常量里有 0.5，推测 0.5s，未验)；按速度判短传送会漏，
>   更好的判据是 `PyGenius` 已读的辅助特质 + 冷却刚重置。
> - 假动作的理论界：设 D = 我看到监管位置 → 服务端开始倒板的总延迟、v≈56 单位/s、倒板中砸中区 |纵深|<16。
>   防骗需 d<16−vD，保砸中需 d>vD−16，两者兼得当且仅当 vD<16(D<≈0.29s)。先从日志「板子状态已变化 用时」量 D 再谈方案。

> **★★★ 2026-10-23 游戏脚本静态调研(国服 all_pyc，国际服热更同值)：游戏自己的判据 + 服务端"自动放板"检测**
> - **砸中判据** `common_cs/iCommonPanel.is_unit_in_hit_range` + 配表 `DM.global_data['panel_hit_range'] = (13, 12, 3)`(游戏单位)：
>   `cos=get_cos_angle_of_unit(unit, panel)`、`dist=get_space_dis(panel, unit)`、`y=|dist·cos|`(沿板子倒下方向)、`x²=dist²−y²`(沿板长)；
>   板子状态 `USEING`(正在倒)时另取 `y_max`。具体哪个下标比哪个量被抹零的操作码挡住(国服字节码也有操作码字节=0 的指令，
>   `CACHE/N` 其实是真指令)，**静态没读准，需注入或差分验**。`check_auto_put` 里 `y_rate`/`x_rate` 疑为 y/13、x/12。
> - **判定时机**：不是点下那一刻。`iLogicPanel.on_putdown_start` 起定时器 `check_hit_butcher_wrapper`，按场景配置 `panel_hit_time`
>   (`hit_check_time_data`)在倒板过程中多次检测，监管要在**倒板窗口内**进入范围才算砸中。
> - **能否放板**：交互盒 `DM.box_bounding[BOX_BOUNDING_NAME.PANEL]`(`is_unit_start_move_in_panel` 也用常量 15)，与监管位置无关；
>   PANEL 对应的 id 还没查。
> - ⚠️ **服务端检测**：`iLogicPanel.check_auto_put(client_info)`(SERVER_MODE，倒板开始时调用)算 监管/求生者/板子 相对位置、
>   监管朝向与板向夹角(>90°)、板-监管方向夹角(>70°)、y_rate/x_rate，满足条件时记进 `room.auto_put_panel_dict[key][uid]`；
>   **`LSkillFlywheelSprint.record_auto_flywheel` 也往同一个 dict 记飞轮**(键 'fly_wheel'，记"开飞轮后多久被打中"，没被打中记 -1)，
>   **飞轮这条有 `room.is_top_battle` 门槛，放板 `check_auto_put` 没有(每局都跑)**。消费方不在客户端脚本里(服务端)。
>   客户端放板 RPC(`PanelInteractComponent.process_panel_event`)自带 `client_pos`、`near_butcher`，后者一路传进 `check_auto_put`。
> - **高端局 `is_top_battle`**：`RoleLogic._match_prepare`(匹配成功时)：天梯 `check_top_battle_ladder` / 其它 `check_top_battle`，
>   遍历 `info['players']`，(跳过监管那条)任一玩家段位在 `DM.part_data` 里带 `limited_num` 即 True；服务端 info 自带 `is_top_battle` 时以它为准。
>   `limited_num`：part_data 五阶=4、六阶=4、七阶=2(一~四阶无)；ladder_part_data 四阶=1。⇒ 排位**有五阶及以上求生者**即高端局。
>   高端局另外门控：`LSkillSpellFlash.shanxian_zuobi`(闪现位置作弊校验)、`TransformComponent.process_dir_sync_event`(位置/方向同步作弊计数，含 flywheel_tag)、
>   `LSkillSawSprint._collect_abnormal_move_data`(小丑拉锯异常位移采集)；`UtilsLog.log_battle_*` 赛事日志带 `top_battle` 字段。
> - **能不能放板(按钮出不出来)= 客户端 `ClientUnits/BattlePlayerUnit.find_putdown_panel_uid`**(遍历 `unit_mgr.get_panel_units_ex`)：
>   `get_space_dis(自己, 板)`(**三维**，含高度)≤ `wood_put_dis + get_inter_distance_bonus(self,'board')`；板 `state==IDLE`、`not can_not_put_down`；
>   自己不在 panic / 不在 PUT_PANEL / fear_state≠CRASH / 没被蜡封；`is_unit_covered_between` 两者之间无遮挡；单向板(`oneway_tag`)要在 −90°~90° 那侧。
>   `wood_put_dis = 25.0`(国服/国际服热更同，`global_data`；同表 `wood_destroy_dis=22`、`wood_span_dis=30`)。
>   加成 = 单位属性 `MBSet.RemoteInteractionRange`(有 buff 8818 时为 0)，常态 0。
>   **服务端** `iLogicCivilian.can_putdown_panel` 再验：`cheat_check_valid(dist, put_dis+10)`，超了 `log_cheat_info` 并拒绝。
>   若辰/我们用的是**水平**距离 + **场景模型原点**(objcoor)，游戏用的是**三维** + **逻辑单位坐标**(get_position3)——不一致是"2.1 米有时不灵"的主因候选。
> - **游戏自己的判定结果可直接读(零注入)**：`ui_dict['UIBattle']` 实例上的 `cbtn_alpha_st`(主交互按钮类型，`CIV_HAND_ALPHA_STATE`
>   按定义顺序 DEFAULT0/SP_FLAG1/CREEP2/**PUT_PANEL3**/SPAN_PANEL4/SPAN5/CAVE6/SAVE_TGT7…，**3 待上机确认**)+ `cbtn_tgt_uid`(目标 uid)。
>   `UIBattleButton` 是 `UIBattleBase` 的父类混入；`tick_btn_alpha` 每帧写，`pc_hotkey` 按键时读。叠加层 `PyCore::read_inter_button`
>   + 自动盖板面板显示原始值 + 开关「只在游戏显示放板按钮时点」(默认关，产物 `qypmrbdv.sh`)。
>   ✅ 2026-10-23 用户上机：放板按钮出现时确为 **3**。刷新慢有两层：①我们旧版"不开自动时每 10 轮读+90ms 空转"≈1s(已修，每轮读，产物 `oxrmcwtb.sh`)；
>   ②游戏 `tick_btn_alpha`：PUT_PANEL 在**完整检查组** `_civ_alpha_checker_info`，只在 `frame_cnt % g_opt_mgr.ui_update_button_inv == 0` 时跑
>   (快速组 `_quick` 每帧)；检查顺序 SP_FLAG→CAVE→CREEP→SAVE_TGT→SPAN(翻窗)→PUT_PANEL→SPAN_PANEL，先中先得(靠窗时按钮是翻窗)。
>   按下时 `handler_cbtn_prime` 按 `cbtn_alpha_st` 决定动作 ⇒ 它变 3 之前点了也放不了板，这层延迟是下限。
>   事件日志 `/data/IdentityV_pallet_log.csv`(界面「记录日志」)：btn/cand/near/tap/down/test/hold*，带水平/三维距离、高度差、监管距离。
>   **2026-10-23 首份日志(存档 `逆向\第五人格_脚本解包_反作弊\intl_tid\pallet_log_20261023.csv`)**：空闲态是 **10**(不是 0)；3→放下后立刻 4。
>   按钮变 3 时场景坐标距离 1.52~1.99m、变回 10 时 1.97~2.56m，夹着 2.10m(25 单位)⇒判据坐实、场景原点坐标与游戏逻辑坐标误差在噪声内；
>   进/出的偏差 ≈ 游戏检查节流造成的 0.1~0.2s 滞后。dz 全 <0.1m，高度差场景未测。测试点击在 3 时点下 0.88s 后变 4 ⇒ 触摸点准。
>   板 uid↔场景对象稳定(1000063↔0x…94a220、1000066↔0x…938930)。读按钮改为"读成功才更新、失败沿用≤300ms"(产物 `knqchart.sh`)。
>   **定版(产物 `kcfwsinx.sh`)**：放行固定开启(`g_btn_st != 3` 就不点，无开关)；按钮只在自动开着时读；事件日志/按钮读数行/沿用标记/相关配置项全部删除。
>   要再查时序问题，从 `knqchart.sh` 那版的 git 历史或本节描述恢复日志即可。
> - **砸中判定(完整版，2026-10-23)**：没有"放下就能砸中"的现成字段，是倒板过程中动态算的。
>   公式取自 `ClientUnits/MyButcherUnit.is_in_panel`(变量名完整、可读)，与 `iCommonPanel.is_unit_in_hit_range` 同：
>   `dir1=监管-板; cos=cos∠(dir1, 板.get_direction3); dist=三维距离; y=|dist·cos|(沿板朝向/倒下方向，两侧); x²=dist²−y²(沿板长)`，
>   命中 = `y < y_max 且 x² < 12²`；`panel_hit_range=(13,12,3)`，y_max=13，**板子正在倒(USEING)时 13+3=16**。
>   时机：`on_putdown_start` 起，按 `scene_model_config.panel_hit_time = (0.0, 1100.0)`ms(随放板速率缩放)、`hit_check_interval=1/30s`
>   每 33ms 检一次，**倒板开始后 1.1s 内任一次检测监管在区内就算砸中**(`has_hit` 置位后停)。事后可读：板 `has_hit`、监管状态 HIT_BY_PANEL。
>   对比若辰矩形(沿向 ±8.63、横向 ±宽/2+0.38)：游戏区大得多(y±16、x±12)，且有 1.1s 窗口 ⇒ 可以提前点。
>   ⚠ 我们场景层的板朝向(objcoor+0xb8/+0xc0)对应游戏的 get_direction3(朝向)还是板长方向，未核对(开「显示判定范围」看矩形长边即可)。
> - **监管移速(2026-10-23)**：配表 `pydata/player.move_speed`(单位/秒)，监管绝大多数 54~56(4.54~4.71m/s，杰克 56 ≈ 用户实测 4.73)，
>   梦之女巫本体 72、喧嚣 60；求生者 25(实际跑 ≈3.8m/s，说明有状态倍率)。全表(id↔名字按字段顺序配对，个别行可能错位)存
>   `逆向\第五人格_脚本解包_反作弊\intl_tid\role_move_speed.tsv`。运行时 `common_cs/mgr/MoveSpeedMgr.speed_real` =
>   base_speed × 状态倍率 × buff + 跑酷/滚轮等；该类走 Cython 优化(cclass)，属性未必在实例 dict，叠加层不读它。
> - **快速监管预判(产物 `jcadlmtp.sh`，未上机)**：每轮记监管水平位置，100ms 窗口最小二乘测速；速度 > `fast_mps`(默认 5.9 = 4.71×1.25)、
>   且不在刹车(后半段速度 < 前半段 70% 视为刹车)时，把位置每 20ms 推一次、推到 `lead_ms`(默认 200)，任一点落进现有判定矩形即命中(标"预判")。
>   相邻样本 >30m/s 视为传送清空历史。正常速度走近停住的到不了门槛 ⇒ 不会被骗板。放行仍要求游戏按钮==3。
>   上机：快速位移能砸到了，但更快的会穿过。**修正(产物 `mtoqefhi.sh`)**：①传送判据改"单次跳变 > 5m"——远端位置随网络包阶梯更新，
>   越快那一跳换算速度越高，旧的 >30m/s 规则会把快速冲刺误清(主因)；②测速窗 80ms/≥3 样本/≥30ms；③预测步长 20→5ms；
>   ④刹车判据 70%→50% 且两半各 ≥30ms 才判；⑤提前量默认 200→350ms(上限 800)。
>   **提前量原理**：是固定时间≈端到端延迟 L，与速度无关；要砸中需 0 ≤ L−提前量 ≤ 穿区时间，越快容错越小；
>   点早被 1.1s 倒板检测窗兜住、点晚就穿过 ⇒ 宁大勿小。
> - **默剧艺人的板子**：`ClientUnits/MimePanelUnit(PanelUnit)`，`is_mime_panel` 标记；升起(`rising`)/下沉(`sinking`)期间
>   `can_not_put_down`=真(用 `_block_put_down_keys` 集合)，其余走普通板子流程(放下/砸中监管/`_publish_mime_panel_stun_butcher`)。
>   模型 `chr/player/dm65_survivor_w/h55_survivor_w_moju/h55_survivor_w_moju_woodplane01.gim` 含 woodplane → 我们按类名收板会收进来；
>   场景层状态偏移 +0x750/+0x30 对它是否同样适用未验。`get_panel_units_ex` 按位置取板(`room.get_scene_model_by_pos`)，不分类型。
> - 界面：2026-10-23 三档「模式」改成「触发宽度」(默认 12，5~15)+「随机宽度」(上下限 5~15，每点一次重抽)。

> **★ 加任何 auto-* 功能前先读 skill `touch-inject-arbitration`**:商业外挂 007(第五人格 ESP)的
> 触摸注入仲裁(controller_gate 五拒绝原因 / finger-outside-gate / owner / epoch / 队列)完整逆向 +
> 逐轴对照本文这套。结论:你不缺砸板算法(本文若辰那套已落地),缺的是 owner/epoch/队列/finger-gate 的
> 完整仲裁体系 —— 多加几个自动功能后抢手指/卡键/封号会集中爆发,照那篇 §5 给 `Touch::InjectTap` 补。

> **★★ 2026-09-26：已照若辰 10.1.74 落地**（`IdentityV\jni\src\Android_draw\AutoPallet.h` + `TouchHelperA.cpp` 的
> `Touch::InjectTap`，产物 `xihspefb.sh` md5 `e8af9bb5…`，已推送 `/data/`，**未上机**）。下面第零节是若辰的完整逻辑，
> 比后面「帝五忍鸽」那套新、偏移也新（帝五的 `+0x730` 是旧版本，这一版是 `+0x750`）。**以第零节为准。**

> **★ 2026-10-12 上机：菜单里「自动盖板」复选框点了没反应，其余控件正常** —— ImGui **ID 冲突**：
> `CollapsingHeader("自动盖板")` 里放了 `Checkbox("自动盖板")`，同一 ID 栈下标签相同 → ID 相同，点击被折叠框吃掉。
> 改成 `Checkbox("开启##auto_pallet")`，产物 `zdwpboui.sh`（md5 `be93ed89…`，已推送 `/data/`）。
> **以后菜单加控件，标签别跟所在折叠框同名**（要同名就用 `##后缀` 区分）。
> 我当时先误判成"evfilter 独占真屏导致注入被丢"并改了 `TouchHelperA.cpp`，用户否定，已 `git checkout` 撤回 —— 别再往那个方向查，
> 先问清楚"点不下去"指的是菜单控件还是游戏按钮。

> **★ 2026-10-14：加随机 + 去孽蜥条件**（产物 `stimgknc.sh` md5 `3fda2a40…`，已推送 `/data/`，**未上机**）：
> - 自动点击位置在触摸点半径 `jitter_px`(默认 10) 圆内随机（角度均匀、半径均匀 → 偏向中心）；按住时长 `hold_ms ± jitter_ms`(默认 5)，下限 10ms。
>   **测试点击不随机**（用户要求，方便对准）。菜单「位置随机(px)」「时长随机(±ms)」，「显示触摸点」多画一个黄圈 = 随机范围。「上次」行会写实际坐标和时长。
> - **孽蜥不再整套跳过。★ 待办**：若辰那条规则真正想挡的是**飞天(跳跃)中的孽蜥**，不是地面上的；以后找到跳跃状态判据
>   （动作号 `[[obj+0x750]+0x30]` / 高度差等）再加回一条只过滤飞天的严格判断。代码里 `thread_main` 有 `TODO(孽蜥)`。

> **★ 2026-10-22：触摸「面积」特征 —— 真机采样把结论反转了（event7，25s / 12554 行，采样存 `scratchpad\touch_sample.txt`）。**
> 先前（10-21）基于能力位（`getevent -lp` 声明 `TOUCH_MAJOR` max 255）推断"真人 major 在抖、注入恒 6 → 暴露"，**实测推翻**：
> 本机触摸屏 `/dev/input/event7` 运行时**只上报** `ABS_MT_POSITION_X/Y`、`ABS_MT_SLOT`、`ABS_MT_TRACKING_ID`、`BTN_TOUCH`、`BTN_TOOL_FINGER`，
> **从不上报** `TOUCH_MAJOR/WIDTH/PRESSURE/MINOR/ORIENTATION`（**能力位声明支持 ≠ 运行时发**）。真人手指在本机就是"纯坐标"，无任何面积/压力动力学可模仿。
> → **暴露方向反了**：不是"真人有、你缺"，而是**"你多写了真人没有的字段"**：
>   `InjectTap` 的 `inject_has_major` 取自能力位 `EVIOCGBIT`（582）→ 本机为 true → 643 行写 `TOUCH_MAJOR=6`。
>   于是真人点击的 slot 永远没有 `TOUCH_MAJOR`，唯独自动砸板那一下冒出 `TOUCH_MAJOR=6` → **零误报签名**。
>   另：真人按下/抬起都发 `BTN_TOOL_FINGER`（DOWN/UP），`InjectTap` 只发 `BTN_TOUCH`（645/659）**漏发 `BTN_TOOL_FINGER`** → 又一处"真人有、你没有"。
> **正确修法（本机，极简，不需要任何曲线/采样/公开数据）**：让注入 slot 的**字段集与真人完全一致**——
>   ① 去掉 643/644 的 MAJOR/PRESSURE 写入，或把 `inject_has_major/pressure` 判据从"能力位 `EVIOCGBIT`"改成"运行时**真的观察到**真人 slot 发过该 code"；
>   ② 补发 `BTN_TOOL_FINGER`（随 `BTN_TOUCH` 一起 DOWN/UP）；③ `TRACKING_ID` 抬起写 -1 已一致（658，真人抬起也是 `ffffffff`）。
> **"运行时镜像"含义随之修正**：镜像的是**真人实际发哪些 ABS code（字段集）**，不是"镜像 major 数值"（本机没有数值可镜像）。
> **小游戏采样 / 公开数据集（Touchalytics 等）/ 面积包络建模 —— 本机全部作废**（真人无面积）。只有换到**运行时真发 major 的屏**，才需要回到"镜像数值+多帧 `SYN_REPORT` 曲线化"那条老路。
> **判据铁律：该写哪些触摸字段，看运行时真人 slot 实际发了什么，不能信能力位（`EVIOCGBIT` 会谎报支持）。**
> 其它实测：坐标系 raw 高分辨率（X max 127999，非屏幕像素，`Screen2Touch` 负责缩放）；采样率 ~250Hz（帧间 ~4ms）；点击 vs 滑动唯一区别是 `POSITION_X/Y` 的逐帧位移量，字段结构相同。
> **已落地（2026-10-22 上机验证通过）**：`TouchHelperA.cpp` —— `TypeA` 读循环记 `inject_saw_major/pressure/tool_finger`（`std::atomic<bool>`）、`probe_inject_caps` 加探测 `inject_has_tool_finger`、
> `InjectTap` 判据 `inject_has_* → inject_has_* && inject_saw_*`（本机真人不发 major/pressure → 不再写）+ 按下/抬起补发 `BTN_TOOL_FINGER`。
> 产物 `tikqagwn.sh`（md5 `0367c723…`，已推 `/data/`）。**上机验证**：触发注入（面板「测试点击」或自动砸板）时 `getevent -lt /dev/input/event7`，
> 看注入 slot 应**不再有 `TOUCH_MAJOR`、且带 `BTN_TOOL_FINGER`**（与真人字段集一致）。⚠ `inject_saw_*` 要玩家先碰过屏才就绪，验证前先正常操作几下。
> **实测结果（2026-10-22，`event7` = `goodix_ts`，`ABS_MT_SLOT` max 9 / `ABS_MT_TRACKING_ID` max 65535）**：注入那一下 `slot=9`、`tracking_id=0xfff8`（`= max-1-(seq&7)`，真人是 `0x38xx` 小值，一眼可分）；
> 该块字段 = `SLOT/TRACKING_ID/POSITION_X/Y/BTN_TOUCH/BTN_TOOL_FINGER`，**无 `TOUCH_MAJOR`**；全采样 `TOUCH_MAJOR/PRESSURE/WIDTH` 出现 **0 次**、`BTN_TOOL_FINGER`:`BTN_TOUCH` = 66:66 配对。与本机真人单指字段集一致 → 签名消除确认。
> ⚠ **坑：叠加层运行时独占/grab 了 `event7`**（`/proc/<pid>/fd` 有一个 `rwx` 指向 event7 的 fd），外部 `getevent` 旁观会**读空**（EXIT_124、0 行）。采样得由用户在能读到的时机自采（本次用户自跑成功）；或先停叠加层再采真人基线。
> **多指场景实证（回应"左手摇杆+右手砸板会不会被打断"）**：采样双指段里**第二根手指按下只发 `SLOT/TRACKING_ID/POSITION_X/Y`，无任何全局键**；
> 全采样 EV_KEY 只有 `BTN_TOUCH`×16 + `BTN_TOOL_FINGER`×16，**无 `BTN_TOOL_DOUBLETAP`**（本机多指时第二指静默）。而 `BTN_TOUCH`/`BTN_TOOL_FINGER`（含新补的）都在 `others==0` 守卫内
> → 摇杆按着（`others>=1`）时一律不发，注入只选**空闲 slot**、不碰摇杆 slot。**结论：注入第二指字段集 = 真人第二指，摇杆零影响。**
> 本轮对真实砸板（左手摇杆）场景的**净效果 = 去掉 `major=6`**（它不受 `others` 守卫、每次注入都写，是该场景唯一签名）；`BTN_TOOL_FINGER` 补发只在单指（`others==0`）生效。
> ⚠ **验证分场景**：测试点击（左手没按，`others==0`）→ 看注入 slot 有 `BTN_TOUCH`+`BTN_TOOL_FINGER`、无 `major`；实战砸板（摇杆按着，`others>=1`）→ 只有 `slot+tracking+坐标`、无 `major`、无全局键（**这才对，别期待看到 `tool_finger`**）。

## 「成功」≠「确认放下」调研（2026-10-18，读 `AutoPallet.h` 结案）

用户报面板出现「成功 4、确认放下 3」。**两个计数本来就不该相等,是量两件不同的事:**
- **成功 `g_tap_ok`** = `Touch::InjectTap()` 返回 `INJECT_OK`——点击**成功写进了触摸设备**(OS 层)。`AutoPallet.h` 227(测试)/389(自动)自增。
- **确认放下 `g_confirmed`** = 点过那块板的状态在 3 秒内离开了 16(`BOARD_STANDING`)——**板子真的倒了**(游戏效果层)。348–349 自增。

**差值 = 点下去了、但没观测到对应的"倒下"。** 成因按可能性排:
1. **`pending` 单槽被覆盖(记账丢失,最可能,解释 off-by-one)**:`pending` 只存**一块**板(391 行)。若前一块还没观测到倒下,就对**另一块**板点了第二次,`pending` 被覆盖 → 前一块即使倒了也不再计数。**板子确实倒了,只是没记上**。门控用的是 `last_board`+冷却、**不是** `g_confirmed`,所以砸板功能不受影响。
2. **3 秒超时(353 行)——真没倒**:板子 3 秒内没离开 16 就丢弃不计。真实原因:点击**落空**(⚠ `jitter_px=50` 偏大,50px 随机圈可能把点带出放板按钮)、求生者当时**放不了板**(不在交互范围/动作中/被别人先放了)。
3. **`read_state(pending)` 读失败(348 行)**:板子倒下后对象被回收/页换出、或 `+0x750` 两次读不一致 → `read_state` 返回 false → 不计 → 3 秒超时丢弃,**虽然倒了也没记上**。
4. **state==16 语义未验(文件头 48 行 caveat)**:若 16 的含义不精确,confirm 逻辑会系统性少计。

**性质**:`g_confirmed` 注释明写「只用于统计/面板显示」(39 行),**不参与任何控制逻辑**。所以不等是**面板/诊断层的事,不是功能 bug**,砸板照常工作。

**怎么便宜地定位这次的 4 vs 3(不用新探针,现有日志就够)**:叠加层已经把两个事件都带地址+时间打进日志——
点击 `[盖板] auto <result> (x,y) <hold>ms 板子=0x<addr>`(396 行)、确认 `[盖板] 板子状态已变化 obj=0x<addr> ...用时=<ms>ms`(350 行)。
拉 `/data/local/tmp/hack_stdout.log` 把每次 tap 的 `板子=` 地址和 confirm 的 `obj=` 地址对一遍:
- tap 的板子没有对应 confirm、但紧接着有对**另一块**板的 tap → **①记账丢失**(板子倒了没记上,无需管)。
- tap 没对应 confirm 也没被覆盖 → **②/③真没倒或读失败**:这块板若从没变过状态,就是真落空/放不了,这才需要 `pallet_probe.py` 核。

**若要让「确认放下」变准(可选,因为只是面板)**:
- `pending` 单槽 → 小队列/集合(记最近 N 块点过的板+时间戳,各自独立确认)=治①。
- 差值分类计数(覆盖 / 超时 / 读失败)直接显示在面板,一眼知道是哪种。
- `pallet_probe.py`(立板/放板前后)钉死 state==16 语义 = 治④。
- **若日志显示②占多数(真落空)**:`jitter_px` 50→~15、复核 `touch_x/touch_y` 对准按钮中心——**50px 随机半径是真落空的头号嫌疑**(默认值 2026-10-15 从 10 调到了 50,见主 SKILL #20)。

**结论**:不等是预期的(两层指标),绝大多数是记账层(①③)——砸板没问题;唯一可能是真功能损失的是②,而②的最大嫌疑是 `jitter_px=50`。先拉日志按地址对一遍再决定要不要动代码。

## 零、若辰 10.1.74 的自动盖板（2026-09-26 反汇编，地址是 `若辰正式版(4).sh` 里的）

主循环 `0x342B00~0x34453C` 和命中判定 `sub_34517C` 被混淆，**Hex-Rays 超时**，全部手读汇编；
`sub_344D7C`(读板子)、`sub_3448A4`(点后复读状态) 能反编译。IDA 用法：先 `-A -S` 跑一个只 `auto_wait()+save_database()` 的脚本存库，
再每个函数单独起一个 idat64 进程反编译、120 秒超时就杀（一个函数卡死不会拖垮其余）。

**配置**（`/data/local/若辰读取版_config.cfg`）：`lian_banzi_enabled` / `lian_banzi_mode`(0~2) / `Touch_X`=2450 / `Touch_Y`=1050 /
`wood_range`=20(只在画范围时用) / `show_wood_touch_point` / `show_banzi_range`。界面在「自动盖板 · 更多设置」，另有「测试盖板触摸」按钮。

**输入**（全部场景对象；`objcoor=[obj+0x28]`）：
| | 读法 | 说明 |
|---|---|---|
| 板子 | 场景数组里类名含 `woodplane` 的对象（另合并 Python 侧板子列表 `sub_38F028`，3 秒内有效，按 0.5 单位去重） | |
| 板子位置 | `objcoor+0xa0` 12 字节，前后两次读 `+0x28` 一致 | |
| **板子状态** | **u32 `[[obj+0x750]+0x30]`**，前后两次读 `+0x750` 一致 | **立着 == 16**（"按板子状态16筛选"、`no_standing_board`） |
| **板子朝向** | **`objcoor+0xb8` / `objcoor+0xc0`** 当水平向量 (x,y)，长度 > 1e-5 | 判定矩形的长轴 |
| 自身 | Python 玩家列表里 is_self 且阵营 2 的那条的坐标 | 我们用 `PySelf::anchor()` |
| 监管 | 全部监管里离自己最近的；排除键 247(红夫人镜像)的重复 | 我们用 `PySelf::hunter_body()` |
| **监管动作号** | **`[[obj+off]+0x30]`，off 依次试 `0x750,0x730,0x758,0x768,0x788,0x790,0x818,0x830,0x908`** | 跟板子状态是同一个组件 |

**命中判定 `sub_34517C(cfg, 自身S, 监管H, 板子P, state, 圆形?)`**，只看水平面，`cfg = {11.886, 8.25, 半宽, 25, 80}`：
```
state == 16
|S-H| / 11.886 <= 3.0 米
|S-P| <= 25 单位(≈2.1 米)                        // 自己得站在板边
圆形(小丑拉锯)：|H-P| <= 80 单位(≈6.7 米)
否则：d = 归一化(objcoor+0xb8, +0xc0)
      along = |(H-P)·d| <= 8.25 + 0.38
      perp  = |d.x*(H-P).y - d.y*(H-P).x| <= 半宽 + 0.38
多块命中取离自己最近的
```
- **小丑拉锯**：监管类名含 `sxwd` 且 `|动作号 - 0x1802CE| < 4` → 圆形判定（日志"小丑拉锯中：改为圆形判定 半径=80"）。
- **孽蜥**：监管翻译名含"孽蜥"时整套不触发（我们按类名 `lizard`）。
- **半宽 = 模式**：暴力 12/2、演戏 8/2、随机 = 每次点完在 8.0~12.0（`8 + (xorshift%41)*0.1`）重抽后 /2。

**门控**：同一块板点过就不再点，直到连续 150ms 没有候选；两次点击至少隔 800ms（失败也算）；
触摸点必须在屏幕内；自动校准(QTE)进行中不点；点完记下这块板，等状态离开 16 → 日志 `board_state_changed`（只做确认/统计）。

**点击**：`sub_34453C` 把 (Touch_X, Touch_Y) 塞进触摸任务队列（source `lianxuan_auto_banzi`，测试按钮是 `lianxuan_banzi_test`），
最终走 `sub_4241C8`：真实触摸屏上**从最高 slot 往下找空闲 slot**，`ABS_MT_SLOT/TRACKING_ID/POSITION_X/Y/BTN_TOUCH + SYN`，按住后 `TRACKING_ID=-1`。
没有空闲 slot 返回 `no_free_slot`，不抢。

**我们的实现与若辰的差异**（`AutoPallet.h` 文件头也写了）：只用场景对象的板子（不合并 Python 板子）；只看 `PySelf` 的监管本体（2v8 只看第一个）；
没有 QTE 互斥（我们没有自动校准）；板子位置/朝向按对象缓存 2 秒，每轮只重读附近板子的状态；注入复用 `Touch` 模块已打开的设备 fd
（`Touch::Init(...,true)` 是只读不 grab，fd 仍是 `O_RDWR`），坐标用 `Touch2Screen` 的逆运算 `Screen2Touch`。

**⚠ 上机要核对的三件事**（`逆向存档\_scripts\pallet_probe.py [次数]`，立板/放板前后各跑一次）：
1. 板子状态 `[[+0x750]+0x30]` 立着是不是 16、放下后变成什么
2. `+0xb8/+0xc0` 是不是板子的长轴方向（看「显示判定范围」画出来的矩形是否顺着板子）
3. 小丑拉锯时动作号是不是 `0x1802CE`

---

> **★ 触摸注入部分优先看 [`ruochen-teardown.md`](ruochen-teardown.md) 第四点六节。** 那份从「若辰」逆出的触摸后端更成熟：
> **MT type-B 空闲 slot 共存注入**（不 EVIOCGRAB 独占、不克隆虚拟设备，真手指照常），三后端优先级
> （**用户选哪个驱动就走哪条**：TwT/天堂 → 内核触摸，RT → /dev/input；不是优先级回退，见该节更正），scale=屏幕分辨率÷设备 ABS_MT 范围，完整 tap 时序 + 结果码 + 绑核。
> 本文下面这套「帝五忍鸽」是**独占触摸屏+克隆 uinput**，实现更重；做自己的 auto-pallet 时优先用若辰那条 slot 共存路线，
> 本文的**盖板判定逻辑**（板子 AABB / 朝向对齐 / 高度差 / 触发范围 / 冷却）仍然有效、照用。

来源：第三方工具「帝五忍鸽_逆天改命」悠惹 V1.1，文件 `yr_dw.rc`
（ELF64 AArch64 可执行文件，1,957,680 B，NDK r27c，已 strip）。
2026-09-22 逆向，原文件和总报告在 `C:\Users\31297\Desktop\新建文件夹\`（`yr_dw_分析.md`）。
下文函数地址都是这个二进制里的虚拟地址。

**可信度说明**：盖板线程 `0x7A7DC`、选监管 `0x7ADA0`、菜单 `0x79C48` 有 Hex-Rays 伪代码；
数据收集段（`0x73390` 内联的一大块）和触摸代理（`0x7C28C`）靠注释反汇编读出来。
`+0x730→+0x30 == 0x30010` 的**语义没有上机验证过**，是按用法推的。

---

## 一句话

求生者视角下，监管站进“离自己最近那块板子”朝向对齐的一个矩形范围里（取的是 AABB），高度差 ≤ 20，
并且自己离这块板子 ≤ 触发范围，就在用户预设的屏幕点（交互键位置）±50px 的随机位置
模拟一次 20ms 的点击，然后进入冷却（默认 3 秒）。

---

## 1. 数据来源（读线程 `0x73390` 每帧收集）

它把数组里的对象按类名分桶，每条记录 0x280 字节。实现时用我们自己的 `data[]` 就行，这里只记判据：

| 桶 | 类名匹配 | 数量变量 | 记录里存了什么 |
|---|---|---|---|
| 板子 `1E06C0[]` | `strstr` 命中 `woodplane001` **或** `woodplane01` | `21EF3C` → 发布到 `21EEC0` | `+0x08` 对象指针，`+0x10` objcoor，`+0x250` 状态值（见下） |
| 监管 `20F4C0[]` | 含 `boss`，且 `+0x70 == 0x1000000` 且 `+0x1a0 == 450.0f` | `21EF40` → `21EEC4` | 同上 |

- **板子状态值**：`state = *(u64*)( *(u64*)(obj + 0x730) + 0x30 )`，存进记录的 `+0x250`。
  盖板线程**跳过 `state == 0x30010` 的板子**，推测是“已放下/已踩碎”。⚠️ 未验证。
  验法：同一块板子在 立着 / 放下 / 被踩碎 三种状态下各读一次这个值。
- **自身**：用独立签名拿自身坐标（见第 5 节）。某个实体的 `objcoor.X/Y` 与自身坐标**完全相等**时，
  它就是自己，它的阵营写进 `1E03C4`（`2` = 求生者）。
  我们这边直接用 `PySelf.h` 的锚点即可，不用照搬这套相等比较。

坐标约定和我们一致：`objcoor = *(obj+0x28)`，`+0xa0/+0xa4/+0xa8` = X / Z(高度) / Y。
**下文公式里的 “Y” 都是水平面第二轴（`+0xa8`），“Z” 是高度（`+0xa4`）**。

---

## 2. 主循环（`0x7A7DC`，独立线程，每轮 `usleep(10000)` = 10ms）

```c
srand(time(0));
for (;;) {
    int h = 最近活跃监管(self.X, self.Y);          // 0x7ADA0，见 2.1
    if (h != -1 && 板子数 >= 1) {
        // 2.2 找离“自己”最近、状态不是 0x30010 的板子
        int p = -1; float best = -1;
        for (i in 板子) {
            if (板子[i].state == 0x30010) continue;
            vec3 pos = read12(板子[i].objcoor + 0xa0);
            float d = sqrt( sq((int)pos.X - (int)self.X) + sq((int)pos.Y - (int)self.Y) );  // 注意先截成 int
            if (best == -1 || d < best) { best = d; p = i; }
        }
        if (p != -1) {
            vec3 P = read12(板子[p].objcoor + 0xa0);        // 板子位置
            vec3 H = read12(监管[h].objcoor + 0xa0);        // 监管位置
            float m78 = read4(板子[p].objcoor + 0x78);      // 旋转矩阵 X 轴的 x 分量
            float m90 = read4(板子[p].objcoor + 0x90);      // 旋转矩阵 Z 轴的 x 分量
            float θ   = atan2f(m90, m78);                   // 板子朝向（弧度）
            bool hit  = 监管在板子矩形内(P, H, θ);          // 2.3
            float ds  = sqrt( sq((int)P.X - (int)self.X) + sq((int)P.Y - (int)self.Y) );
            if (hit && ds <= 盖板触发范围
                && 盖板开关 && 自身阵营 == 2
                && time(0) - 上次触发 >= 冷却秒数) {
                float tx = 触摸点X + rand()%100 - 50;
                float ty = 触摸点Y + rand()%100 - 50;
                touch_down(tx, ty);     // 0x7D3C8
                usleep(20000);          // 按住 20ms
                touch_up();             // 0x7D46C
                上次触发 = time(0);
            }
        }
    }
    usleep(10000);
}
```

### 2.1 选监管 `0x7ADA0(selfX, selfY)`

遍历监管桶，只认 `read4(obj+0x1a0) == 450.0f && read4(obj+0x70) == 0x01000000`
（原码把后者当 float 比 `2.351e-38`，位模式就是 `0x01000000`），
读 `objcoor+0xa0` 的 12 字节，按 **int 截断后的水平距离**取离自身最近的那个，返回下标，没有就返回 -1。

⚠️ `+0x70` 就是我们记录里的**可见位**，跟视角走（见 SKILL.md「活跃位是可见，不是存在」）。
求生者视角下监管离得远时它本来就是 0，所以这里等于“只对看得见的监管生效”。
对盖板这个场景刚好合适（监管近才需要盖），但**别把它理解成存在性判据**。

### 2.2 选板子：离“自己”最近

注意：选的是**离自己最近**的板子，不是离监管最近的。先确定自己要守哪块板子，再看监管有没有进入它的范围。

### 2.3 矩形判定 —— 实际是旋转矩形的 **AABB**

```c
a = 板子范围X * 0.5;   b = 板子范围Y * 0.5;
// 旋转矩形四个角
x1 = P.X + a*cosθ + b*cos(θ+π/2)     y1 = P.Y + a*sinθ + b*sin(θ+π/2)
x2 = P.X + a*cosθ - b*cos(θ+π/2)     y2 = P.Y + a*sinθ - b*sin(θ+π/2)
x3 = P.X - a*cosθ - b*cos(θ+π/2)     y3 = P.Y - a*sinθ - b*sin(θ+π/2)
x4 = P.X - a*cosθ + b*cos(θ+π/2)     y4 = P.Y - a*sinθ + b*sin(θ+π/2)
hit = min(x) <= H.X <= max(x)
   && min(y) <= H.Y <= max(y)
   && fabs(H.Z - P.Z) <= 20.0f;       // 高度差，排除楼上楼下
```

它**没有**把监管坐标变换到板子局部坐标系里做真正的有向矩形判定，而是用四个角的轴对齐包围盒。
板子斜放（θ≈45°）时，包围盒会比真实矩形大一圈，角落会误触发。
**自己实现时建议做成真正的 OBB**：
```c
dx = H.X-P.X; dy = H.Y-P.Y;
u =  dx*cosθ + dy*sinθ;      // 沿板子长轴
v = -dx*sinθ + dy*cosθ;      // 沿板子法向（板子两侧）
hit = fabs(u) <= a && fabs(v) <= b && fabs(H.Z-P.Z) <= 20;
```
顺带可以用 `v` 的符号判断监管在板子**哪一侧**，原版没有做。

θ 的调试显示：原码还算了一个角度 `θ*180/π + 180` 存进 `21EF44`，只用于显示。

---

## 3. 菜单参数（`盖板设置` 折叠页，保存在 `Save.txt`）

| UI 名 | 变量 | 控件 | 范围/格式 | 含义 |
|---|---|---|---|---|
| 盖板开关 | `byte_1E038A` | checkbox | | 总开关 |
| 触摸位置 | `byte_1E038B` | checkbox | | 在触摸点画一个半径 100 的圆，方便对准交互键 |
| 盖板触发范围 | `21EF5C` | slider | 1 ~ 50，`%.0f` | 自己到板子的水平距离上限 |
| 板子范围X | `21EF60` | slider | 1 ~ 30，`%.1f` | 矩形沿板子朝向的全长 |
| 板子范围Y | `21EF64` | slider | 1 ~ 30，`%.1f` | 矩形垂直方向的全宽 |
| 触摸点X | `21EF68` | drag | `%.1f` | 触摸坐标 |
| 触摸点Y | `21EF6C` | drag | `%.1f` | 触摸坐标 |

- 这些变量都在 bss，默认值是 0，实际值从 `Save.txt` 读入。**需要用户自己调**，没有出厂默认值
- **冷却**：`.data` 里的 `dword_1DBBB0 = 3`（秒），`qword_1DBBA8` 存上次触发时间，UI 上不可调。
  面板显示“触摸操作 1 冷却时间: Ns”，就是 `上次 + 3 − now`
- 还有“触摸操作 2”（冷却 `1DBBB8/1DBBC0`，同样 3 秒，触摸点在 `21EF78`，标记开关 `1E038D`），
  这个版本里**没找到触发它的代码**，像是预留给第二种自动操作的
- 距离单位是**游戏原始坐标单位**，不是米。我们代码里有 `距离比例` 做换算，实现时先实测一块板子的尺寸

**触摸点 ↔ 屏幕坐标的关系**：画标记圆时用的是 `(触摸点X, 屏幕高 − 触摸点Y)`
（`2*1E03B8 - Y`，其中 `1E03B8 = 短边/2`），说明它的触摸坐标系 **Y 轴相对屏幕是翻转的**。
这和横屏时触摸屏的原生方向有关，自己实现时要按设备实测，别直接照抄。

---

## 4. 触摸注入：uinput 代理（`0x7C28C` 初始化，`0x7D3C8` 按下，`0x7D46C` 抬起）

这一节是**最值得抄的部分**。它没有直接往 `/dev/input/eventN` 里写（那样会和玩家手指抢 slot，摇杆会断），
做法是：

1. `opendir("/dev/input/")`，逐个打开 `event*`，用 `EVIOCGBIT` / `EVIOCGABS(0x35/0x36 …)`
   （`0x80184540 + code`）找出带 `ABS_MT_POSITION_X/Y` 的触摸屏，读出它的 absinfo
2. **`EVIOCGRAB`（`0x40044590`）独占真实触摸屏**，之后游戏收不到真实设备的事件
3. 打开 `/dev/uinput`（`O_WRONLY|O_NONBLOCK` = `0x801`），按真实设备的 absinfo 克隆出一个
   虚拟触摸屏（`UI_SET_EVBIT`/`UI_SET_ABSBIT` 等，`UI_DEV_CREATE`），**设备名随机**（`rand`）
4. 起一个线程，持续读真实触摸屏的事件，把玩家的手指状态**转发**到虚拟设备
5. 注入时（`0x7D3C8`）：
   - 用 `21F1CC` 做自旋锁（`sched_yield` 等待）
   - 坐标乘缩放系数（`21F1D0/21F1D4`），从屏幕像素换算成触摸屏分辨率
   - 写入一个**专用手指槽**：tracking id 固定为 **19**（`0x13`），active=1，位置=(x,y)
   - 调用 `0x7C0D0`：把真实手指和注入手指**合成完整的 MT slot 状态**，一次性写进 uinput 并 `SYN_REPORT`
6. 抬起（`0x7D46C`）：专用槽 active=0，再调一次 `0x7C0D0`
7. 退出时先 `EVIOCGRAB(0)` 释放真实设备，再 `UI_DEV_DESTROY`（`0x5502`），然后 close
8. 失败时打印 `获取屏幕驱动失败`

好处：玩家正在拖摇杆时注入一次点击，摇杆不会断，因为两根手指各自占一个 slot，状态由代理统一合成。
代价：**独占了真实触摸屏**，代理线程一旦卡住或崩溃，整台手机的触摸都会失灵，
而且虚拟设备要在进程退出时正确销毁，否则设备节点会残留。**实现时一定要处理好信号退出路径。**

---

## 5. 依赖：本机坐标签名（顺带发现，可以独立使用）

在 bss 逐页扫数组签名时，令 A = 满足 `u64[A] == 0x4000` 的位置：

```
u32[A - 0xb0] == 1   &&   f32[A - 0xac] == -1.0f
  =>  A - 0xa8 起的 3 个 float = 本机玩家 X / Z / Y   (每帧读 12 字节)
```

它和数组签名是同一个 A（数组条件是 `f32[A-0x10]==1.0 && u32[A-8]==0x101`，数组头 = A+0x38）。
这是一个**纯 bss 的自身锚点**，不依赖 Python 层，可以给 `PySelf.h` 当兜底或交叉校验。
⚠️ 在我们的 `2026.0917_b6f53566` 上没验证过。验法：`devread` 读 `A-0xa8` 的三个 float，
和 `g_cam_ctrl.unit.model+0x20` 对应场景对象的 `objcoor+0xa0` 比一下，看是否相等。

---

## 6. 自己实现时的建议

1. **自身和阵营**：用 `PySelf.h`（`g_cam_ctrl.unit`），比“坐标相等”靠谱，
   而且机械师操控玩偶时也能正确跟随（原版的坐标相等法会把玩偶当成自己吗？没验证）
2. **监管**：用我们已有的本体集合（`units_by_type[1]`），别再靠 `boss` + 450 + 可见位
3. **板子是否可用**：
   - 先验证 `+0x730→+0x30` 这个值（第 1 节的验法）
   - 或者直接走 Python 层：`units_by_type` 里木板的键（军工厂那局是 11 块），看有没有 `is_down` 之类的属性，
     这比猜 `0x30010` 更权威
4. **范围判定**：用真正的 OBB（2.3 节），加上“监管在哪一侧”的判断
5. **触摸**：照抄 uinput 代理（第 4 节）。直接 `input tap` 太慢（要 fork 一个 shell，约 100ms+），
   而且需要 `su` 才有 INJECT_EVENTS 权限（见 android-re-toolkit 二节）
6. **冷却**：原版写死 3 秒，建议做成可调；另外建议加一条“刚盖过的板子不再触发”
7. **阈值单位**：把游戏坐标单位换算成米再暴露给 UI，原版直接暴露原始单位，调起来很难受
