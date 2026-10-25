# 若辰读取版 逆向拆解（第三方商业外挂，当"标准答案"用）

> 2026-09-23 从用户给的 `若辰正式版(4).sh`（在 `C:\Users\31297\Desktop\新建文件夹\1\`）逆出来。
> 这个 `.sh` 是**假后缀**，真身是 **aarch64 Android 原生可执行文件**（ELF PIE，NDK r27c，
> 内嵌 Dear ImGui + Vulkan/GLES），版本自报 `若辰正式版 10.1.74-mary-identity-official`。
> 它是一个**外部只读型**第五人格外挂：root 终端里跑，ptrace + `/proc/pid/mem` 读游戏，
> 默认纯读取，只有"本地美化"会 ptrace 注入一个内嵌的小 so（二进制里没有 `libbeautify` 这个名字，日志标签 `RCBeauty`；见第四点八节）。
> 卡密走第三方平台 `w2.t3yanzheng.com`（明文 HTTP，IMEI 绑定，缓存明文在 `/sdcard/.km`、`/sdcard/.imei`）。
> 验证/加密函数用 OLLVM 控制流平坦化保护，Hex-Rays 反编译会挂死；**功能读取逻辑没混淆但函数极大**
> （中央读取器 `sub_3AAC54` 有 57KB），也反编译不动，全靠读汇编 + 提取属性名还原。

## 为什么这份文档值钱：它和我们的"Python 层"是同一条路，但更成熟

我们自己维护的第五人格 ESP，玩法状态一律走 **Python 层**（对象图按名字查属性，见 [`python-layer.md`](python-layer.md)）。
若辰用的是**完全一样的思路**，而且比我们做得更狠：

- **它不读死偏移，全部按 Python 属性名读**，并且**每个字段准备了一串候选名依次回退**
  （例：治疗进度试 `cured_process_client → _cured_process_client → cure_process_client → _cure_process_client`）。
  这就是为什么它能扛住网易热更——**属性名比结构体偏移稳得多**。
- 所以这份文档里那一大堆属性名，就是一份**"第五人格每个玩法状态挂在哪个属性上"的现成字典**。
  我们要新做一个功能时，**先来这里查作者读的是哪个属性名，直接抄名字**，省掉在对象图里瞎扫。

> ⚠️ 名字是从**这一个版本**的二进制里提取的。用之前仍要在活体上确认该属性存在（网易可能改名，
> 但作者的多候选回退表已经把常见改名都覆盖了，可以照抄整串候选）。

---

## 零、2026-09-24 活体实测校正（**先读这个，下面的原文有几处是错的**）

注入探针在训练局 / 准备房间 / 大厅逐条验证过。数据来源 `逆向存档\2026.0917_b6f53566\captures\cmd\`（`*_verify*`、`heal_series_0924.txt`、`*_prep1`、`prepdiff_*`）。

| 原文 | 实测 | 结论 |
|---|---|---|
| ① 治疗进度 0.0~1.0，`normalized = raw/maximum`，maximum 来自 debug_record_cured_info | 进度 **0~100**。**2026-09-26 重读汇编**：maximum 是**写死的**（自愈 60 / 被治 100）；`debug_record_cured_info` 只取进度项写日志、不参与显示；**不外推**；显示只用 `cured_process_client`，而它在非本机单位上恒 0 | 见第三节 ① 重写 |
| ⑦ 101 = "取对象自带名"、侦探走 `identity_type` 特判 | **2026-09-26 解跳转表：101 = 侦探**。名字寄存器先预设"侦探"再 switch，只有 101 那格不改名字；`identity_type` 只在一张通用"单位类型候选名"表里 | 见第三节 ⑦ |
| ③ 局前预知读 `waiting_for_process` | `UIRoomWait` 上**没有**这个属性；`player_tips.data` 为 None | 这一版不成立。监管 pid 在 `UIRoomWait.b_uid2pid` |
| 四点五 `world_type==0x2713` 判阶段 | 0x2713 = 10003 = **准备房间的 `scene_id`**；`world_type` 样本：大厅 50 / 准备 4 / 训练局 51 | ⚠ 用户不认可把 `world_type`/`scene_id` 当判据（多个大厅、多个地图可能各不相同）。用类名 `WorldMatchRoom` 或 `UIRoomWait` 是否存在 |
| 四点五 准备阶段信息在 `UIRoomWait` | 对，但**天赋的实时源是 `g_avatar.final_genius_dict`**；`eid_2_player_info` 是快照；`c_skill_data` 只在我是求生者时有内容 | 见 `idv-replay-genius` 六点七节「准备阶段数据源全表」 |
| ⑤ 监管动作读 `state`/`action`/`action_id`（从 combat_unit） | unit 本体和 `combat_unit`（50 条属性）上**都没有** | 用 `unit.animation_parameter[0]`（动画名）+ `skill_mgr.last_cast_skill_id` |
| ⑥ copycat = 普通对局的镜像/复制解析，`identity_id∈[100,200)⇒监管` 可当阵营兜底 | 普通对局单位上 `components`/`identity_id`/`camp*`/`mirror_uid`/`copy_uid`/`owner_uid` **全不存在** | ⑥ 很可能和 ⑦ 是**同一个功能**（「模仿者」官方英文就是 Copycat），`[100,200)` 是身份局里 1xx 段的归属，**别用到普通对局的阵营判定** |
| 模型变体整串 | `ext_model`/`model_in_scene`/`clone_model`/`server_model` 存在但为 None；其余不存在 | 这几个角色上没用，换有特殊形态的角色再看 |
| 手持物耐久/次数整串 | `_remain_use_times`/`_init_use_times` 可用（橄榄球、香水 3/3）；`_remain_lifespan` 等为 0 | 次数能用 |
| 五点五 `+0xCA8` 第二跳 | **`根+0xCA8 == 根+0xA58` 9/9 成立** | 可当交叉校验。原文"类比 `+0x330/+0x3B8/+0x440` 那组槽"不对：那组是 bss 签名附近的槽位，`+0xA58/+0xCA8` 是根对象上的字段 |
| 五点五 校验器 6 条 | 我们每帧只搬了"两跳指针范围 + 16 个 float 有限"两条；防竞态复读评估后不做 | 见主 SKILL 2026-09-24 一节 |

---

## 一、通用读取原语（所有功能共用）

中央读取器 `sub_3AAC54`（0x3AAC54，57KB）遍历世界、逐 unit 把下面这些原语堆起来用：

```
resolve_attr(obj, {候选名1, 候选名2, ...}, n)  = sub_39E26C  // 依次试候选名，返回第一个命中的 PyObject*，取不到=0
py_to_double(ctx, pyobj, &out_double)          = sub_3715C0  // PyFloat/PyLong → C double，带 NaN/inf 校验（FABS 后比 0x7FF0..）
py_to_string(ctx, pyobj, &out_stdstring)       = sub_3A805C  // PyStr → std::string（SSO：sub_32AE5C/sub_32ADB0 做赋值）
py_to_list  (ctx, pyobj, &out, W3=type)        = sub_371DB0  // 读 list/tuple；tuple 校验 (end-start)==0x28 即 5 元素
```

**读一个 float 属性的标准汇编模式**（治疗进度那段，0x3B7854 附近）：
```
LDR   X0, [SP, obj]                  ; X0 = 目标 unit 的 Python 对象
ADRL  X8, "cure_process_client"      ; 候选名写进栈上的名字数组
STR   X8, [SP, names] ; MOV W2, #n
BL    sub_39E26C                     ; 解析属性 -> X0 = PyObject* 或 0
CBZ   X0, 下一个候选
BL    sub_3715C0                     ; PyFloat -> D0
TBZ   W0, #0, 下一个候选             ; 失败换下一个候选名
FABS  D0,D0 ; FCMP D0, #+inf         ; NaN/inf 校验，异常就丢弃
```

世界遍历链：`g_world_mgr → cur_world → collision_mgr → _scene_col → 各 unit`。

---

## 二、`sub_3AAC54` 完整属性读取序列 = 游戏状态字段字典

按它在函数里出现的顺序分组（`A / B / C` 表示同一字段的多候选回退，取第一个命中）。**这是本文档最有用的部分。**

### 身份 / 类型
```
unit_type, unit_hide, server_hide, model, uid
copy_uid, owner_uid, mirror_uid, {_cache_puppet_uid | cache_puppet_uid}
generatorunit / doorunit / civilianunit / yidhrapuppetunit   // 按类名判 unit 种类
unit_id | id
```

### 坐标（走 combat_unit 子对象）
```
{position | visual_position | logic_position | pos | world_position | puppet_position}
// 场景坐标读不到时的多路回退，和我们场景层 objcoor+0xa0 是两套，这套是 Python 侧权威
```

### 状态 / 动作 / 朝向（监管动作命中动作表就靠这段）
```
状态: state | _state | status | state_id
动作: action | action_id
朝向: direction | dir | forward
朝向分量: {direction_x | forward_x}, {direction_y | forward_y}
```

### 破译 / 大门
```
fix, hack, work, unlock, fix, generator      // 密码机/大门进度相关布尔与进度
map_percent                                  // 走 params 读，破译/地图百分比
```

### 玩家 / 归属
```
player, _player_name, model_path
params{ pid, role_id }
{_host_uid | host_uid}, {_master_uid | master_uid}
player_name | real_name
```

### 阵营 / 身份（求生 vs 监管）→ 详见第三节 ⑥ copycat
```
components | _components
identity_id, role_type, {camp_id | camp}, {idx | index}
// 从 components 组件列表里的身份组件读；camp 读不到时用 identity_id∈[100,200)→监管 反推
```

### 鬼魂 / 幻影
```
is_phantom_ghost, is_ghost         // 伊斯人/时空之影判定，和我们场景层 +0x6D 位判是两套
```

### 天赋 / 技能 / 手持物
```
genius_id_lv_lst                   // 天赋（详见 idv-replay-genius）
support_skill_id                   // 辅助技能
handheld_id_lv, held_item_id       // 手持道具
```

### 手持道具明细（独立显示框上手持物品）
```
item_lst → { item_id | weapon_id, item_name }
耐久/数量: _remain_lifespan | cur_count | durability | amount | remaining_count
初始:      _init_lifespan | total_power_num | init_power
使用次数:  _remain_use_times, _init_use_times
冷却:      remain_cd | item_cd_time, _left_duration_time
使用中:    _b_in_use | b_in_use | is_using | in_use | b_using   // 一串布尔候选
```

> **★ 2026-09-26 反汇编复核（求生者身上带了什么 —— 若辰做了，而且很细）**：
> - 走 Python 层，不走场景层。`item_lst` 在 `0x3b1fc8` 被引用：`sub_39E26C`（按候选名取属性）→ `sub_371DB0`（按列表解析），
>   然后逐个道具读上面那几组字段（id/名字、剩余次数、耐久、冷却、是否在用）。
> - 除了 `handheld_id_lv` / `held_item_id`，字符串里还有 **`hand_item_id` / `carry_item_id`**（本节原来没记，也是手持物候选名，
>   活体没验）。
> - 开关 `hook_held_items`（UI `##draw_held_items`）；日志/报告里有 `live_held_items=`（`0x3e3094` 引用）/ `cfg_held_items=`（`0x3e2dac`）。
> - 活体已验的只有 `_remain_use_times/_init_use_times`（见第零节）；其余候选名照抄前先在对象上确认存在。

### 特殊角色状态
```
_w_xiangshuishi        // 调香师香水状态（自动香水连招用）
joseph                 // 约瑟夫（相机/世界切换）
```

### 监管"吃人/猜对"类（厂长、蜘蛛等）
```
guess_right_count                          // 猜中数（预言家？）
{eaten_count | eat_count}, eaten_uids, corpse_uids, round_box_uids
```

### 治疗 / 自愈（见下面功能详解 ①）
```
cured_process_client | _cured_process_client | cure_process_client | _cure_process_client
debug_record_cured_info | _debug_record_cured_info      // 5 元组，若辰只取第 3 项(进度)写日志，不用于显示
cured_uid | _cured_uid                                  // == 自身 uid 时若辰按"自愈"、上限写死 60
校验标签: missing_progress / invalid_progress / zero_progress / outside_display_range / sampled
```

### QTE / 校准指针（自动校准、约瑟夫模式靠这段）
```
GK.input → battle_ui → _in_qte
qte_visible_flag, visible, qte_hit_flag, qte_fail_flag, qte_kind
qte_uid, {qte_target_uid | target_uid}
exce_pos, qte_zhizhen, needle, rotation                 // 指针角度/位置
```

### 可见性（透视遮挡）
```
ref_unit, native_unit, component, camera, unit, visible, skin
// 判"当前对本机可见"，和我们场景层 +0x73 可见位是两套；作者走组件/相机链
```

---

## 三、五个功能详解（用户 2026-09-23 点名逆向）

### ① 治疗与自愈百分比（开关 `hook_healing_progress`，`##draw_healing`）—— 2026-09-26 按汇编重写
代码在 `sub_3AAC54` 的 `0x3B7700~0x3B7D10`（`llvm-objdump` + 自写 ADRP/ADD 交叉引用逐条看过）：

- **显示用的进度只有一个来源**：`cured_process_client`，读不到依次试 `_cured_process_client` → `cure_process_client` → `_cure_process_client`。
- `debug_record_cured_info`：`sub_371DB0` 转成 5 个 PyObject*（校验 `(end-start)==0x28`），**只取第 3 项（`[x8,#0x10]`，进度）**
  存进报告的 `debug_raw=`，画面上不用。**时间戳/速度/上限三项都不读，这一段没有引用 `now`，不做外推**。
- **maximum 是写死的**：`cured_uid`（字符串；读不到或是 `"0"`/`"None"` 时当成自己）等于自身 uid → **60.0**（`0x404E…`），否则 **100.0**（`0x4059…`）。
- 判定：进度无效或超过上限+容差 → `invalid_progress`；进度 == 0 → `zero_progress`（不画）；
  `normalized = 进度 / maximum`，落在 **[0.0005, 0.995)** → `sampled`（画），否则 `outside_display_range`。
- `healing_display_mode=sample_only` = 只采样不装常驻 hook（降封号风险）。

**对照我们的实测（`idv-replay-genius` 六点九节、`captures\cmd\heal60_0925_*`）**：非本机单位的 `cured_process_client`
恒 0（训练局 4 个人机 240 帧全 0），所以若辰**画不出别人的治疗进度**（正式局真人会不会下发没验）；本机的 `cured_process_client`
也只是事件快照（9-24 数据里它每次都等于 `debug_record_cured_info` 的进度项），所以若辰的条是一跳一跳的。
**我们的方案更好**：`进度 = 记录进度 + 速度 × (unit.now − 记录时间戳)`（治疗者列表非空时），封顶取记录里的上限 ——
所有人、每帧连续、上限不写死。`unit.now` 与记录时间戳同钟且连续，外推在 5 次改写点误差 ≤ 0.1，已实测。

顺带：若辰的**密码机进度也不是直读**，读 `fix_process` + `last_sync_process` 再按速度平滑
（格式串 `reader-generator-merge`：`raw/sync/speed/speed_sampled/direct/prior/offset/active/display/completed`，@`0x3A90E4`）。

### ② 认知分 / 赛季胜率（`sub_3EC5C0`，= 开局查战绩）

> **★ 2026-10-16 订正（反汇编 `sub_3EC5C0` + 调用者 0x3f2060 实锤）：这是若辰自己发 HTTP 请求查的，不是读游戏内存。** 调用者所在函数有 `socket/connect/sendto/recvfrom` + 字符串 `GET /api/v1/uid/<uid>/profile?timeout_ms=8000 HTTP/1.1`、`Host: w2.t3yanzheng.com`、`Authorization: Bearer <token>`、`&imei=`，先 `cmp w8,#0xc8`(HTTP 200) 才调 `sub_3EC5C0` 解析 JSON。
> 结论：**认知分/段位/胜率的数据在若辰后端（卡密平台 t3yanzheng），不在游戏、不在本地。接口要 Bearer token（卡密换的、绑 IMEI、会过期），非公开。** 所以 ② 的 `meta{status,not_found,ok}` 是**若辰自己那次请求的响应壳**，不是游戏的查档。
> **对我们的意义**：这条**抄不进只读内存的叠加层**（无本地数据源），除非自建等价后端。下面 `sub_3EC5C0` 的字段是它解析那段 JSON 用的；`in_photo`（`sub_412220`）才是真·读游戏内存（无网络），是局前战绩里唯一可落地的部分。~~原 ④ 四点五"账号级数据能读"的框架按此订正，见那节。~~

读 JSON 响应里的嵌套战绩结构：
```
meta{ target_uid, status, hidden, not_found, ok }
data{ detail, hidden_fields, butcher_data, civilian_data }     // 监管/求生分开
  └ part, part_lv,
    season{ season_id, rank_battle_cnt, rank_battle_win_cnt, rank_battle_lose_cnt,
            character_ladder_score, score }
```
- **认知分** = `character_ladder_score`（监管、求生各一份 part）
- **赛季胜率** = `rank_battle_win_cnt / rank_battle_cnt`
- `in_photo`（`sub_412220`，读 `uid`+`in_photo`）= 是否真人（在开局合照里），区分人机
- 显示串 `[uid=%lld %.0f%% 照片=%d]` = uid、胜率%、是否真人

### ②' 手记（`hand_note_mode`）—— 屏显玩家备注/标记（2026-10-16 调研，**部分未坐实**）
**从二进制确认的**：
- 一条备注的数据结构：`note_android_ident`（按 **Android 设备标识**索引）+ `note_name` + `note_data` + `note_end`（连续 rodata @`0x2dd248`，走 `.rela.dyn` 按名字解析，和战绩 JSON 同一手法、同一 rodata 页）。
- 配置：`hand_note_mode`、`hand_note_font_size`、`hand_note_distance_`、`hand_note_color_%d_%d`（**按"类别×序号"两级索引的颜色**）、UI `##note_enable` / `##unified_note_size`（配置读在 `0x339900` 一带）。

**强推断（未 100% 跟到底）**：这是**屏显"玩家备注/标记"**——局内在特定玩家身上显示预置文字（大概率"主播/代练/演员/疑似开挂"类标记）。依据：① 按 `android_ident`（设备标识）索引，本地没有"别人设备→备注"这种数据；② 全二进制无本地 note 文件、无手记专用 URL；③ `note_*` 走 `.rela.dyn` 按名字解析、与战绩响应同页——**基本可认定备注是跟战绩那次 t3yanzheng 后端请求一起下发/解析的**。
→ **和战绩一样抄不进只读叠加层**（标记库在若辰后端，本地无源）。要彻底坐实"服务器下发"还需跟完手记的取数/绘制函数（目前证据一边倒但没到"亲眼见 GET /api"那种程度）。

### ③ 局前预知（预知监管者；读 `waiting_for_process`）
- 输出 `waiting_prediction_available` / `waiting_prediction_name`（监管者名）/
  `waiting_prediction_note=waiting_stage_cache_not_current_screen_verification`。
- 报告里 `joseph_match=` 单独判约瑟夫。
- 机制：**等待/匹配界面**读 `waiting_for_process` + 配合 ② 的 `butcher_data`，开局前报出监管身份+战绩。
  国服走 `国服等待界面显示本阵营档案`。note 明说是"缓存、非当前屏验证"——预测有缓存、非 100% 实时。
- **对照我们自己的做法**：我们准备阶段预知走的是**场景对象类名扫描**（数组里含 `boss` 的对象），
  局内才走 Python（见 SKILL 待办 #10、`collect_units` 遮蔽 BUG）。若辰这条是**读专门的等待状态属性**，
  是我们没走过的第三条路，值得抄——准备阶段直接读 `waiting_for_process`/`waiting_prediction_*` 比扫类名干净。

### ④ 自动盖板 / 砸板（板子检测 `sub_3BD77C` / `sub_3C5DEC`）
> **★ 2026-09-26 已完整逆出并落地，以 [`auto-pallet.md`](auto-pallet.md) 第零节为准。** 下面这段是早期按字符串猜的，有两处不对：
> 板子来源主要是**场景对象**（类名含 `woodplane`，状态 `[[obj+0x750]+0x30]==16` 表示立着），Python 板子列表只是补充；
> 判定是「监管在板子朝向矩形内 + 自己离板 ≤25 单位 + 两人 ≤3 米」，跟监管动作表无关（动作号只用于小丑拉锯改圆形判定）。
- 板子实体类名 `woodplaneunit`；引用 `pallet_unit` / `palletunit`。
- `sub_3C5DEC` 按类名分类：`civilianunit` / `doorunit` / `woodplaneunit`。
- 逻辑：检测靠近监管者的 `woodplaneunit` 位置 + 监管者位置，监管进入板子正下方判定区时，
  向 `##wood_x/##wood_y` 触摸点注入点击 → 砸板。配置 `lian_banzi_enabled` / `lian_banzi_mode`（`##banzi_mode`）/
  `show_banzi_range` / `wood_range`（`##wood_range_show`）/ `show_wood_touch_point`。
- 触发时机结合 ⑤ 的动作表判断监管当前动作是否可被砸中。
- **对照 [`auto-pallet.md`](auto-pallet.md)**：那份是从「帝五忍鸽」逆的另一套自动盖板。若辰这套的**板子来源**
  走 Python `woodplaneunit`（稳），而 auto-pallet.md 里那条"板子状态 `+0x730→+0x30`"是**未验证的场景层偏移**。
  两份对照着看，优先用 Python 类名这条。

### ⑥ 镜像/复制 ESP 解析（copycat 绘制，`sub_3AAC54` 身份块）
⚠️ **注意别和 ⑦「模仿者/身份局」混淆**：这里的 `copycat`（开关 `hook_copycat_mode` / `##draw_copycat`，UI 标签也写"模仿者"）
是**普通对局里**对每个单位解出①真实身份 ②若是复制/镜像/傀儡属于哪个真身，覆盖红夫人镜像、傀儡(26号守卫/宿伞)、复制类。
**而用户说的"模仿者独立模式"是 ⑦ 那个身份局隐藏身份揭示**，两者同名不同物。

**读取（全按属性名，`sub_3AAC54`）：**
```
① 复制/镜像/归属源（0x3AB618 附近）：
   unit_type==0xF8(248) ? copy_uid : owner_uid  → 字符串（复制/归属源 uid）
   mirror_uid                                    → 字符串（红夫人镜像源 uid）
   _cache_puppet_uid | cache_puppet_uid          → 傀儡控制者
   + 一个位置字段(sub_3C73C4 → [+0x60/+0x68/+0x70/+0x74/+0x78])
② 身份元组（0x3B60F4，从 components/_components 组件列表里的身份组件读）：
   identity_id | role_type   → int，有效 [0,10000)  = 角色 id
   camp_id | camp            → int，有效 [0,32)      = 阵营
   idx | index               → int，有效 [0,128]     = 槽位序号
   is_ghost / is_phantom_ghost                       = 鬼魂/幻影
③ 阵营反推（★可复用）：camp 读不到或 ≤0 且 identity_id∈[100,200) → 强制 camp=1(监管)
```
**输出**（报告 `sub_3DD608`）：`copycat[uid,name,index,role,identity,camp,pos,entity,counter]`，`counter`=同一真身的复制/镜像计数。

**对我们的价值**：
1. `identity_id∈[100,200)⇒监管` 是干净、抗热更的阵营兜底判据（我们判自身阵营/camp 一直较绕，见 `PySelf.h`）。
2. 身份元组从 `components` 列表读（不是直接挂 unit 上），是"这单位到底是谁"的正解，比类名黑名单/几何判定稳。
3. `mirror_uid`/`copy_uid`/`owner_uid`/`cache_puppet_uid` 把每个复制/镜像映射回真身 uid —— 红夫人镜像(MaryMirror)配对可直接用 `mirror_uid`，不必再算镜面几何（对照 SKILL 里那套垂直平分线镜面）。

**模型路径解析 `sub_3C8C3C`**：把一个单位的所有 model 变体属性**按序全试**取第一个命中：
`model → ext_model → interactive_model → model_in_scene → ref_model → world_model → role_model →
avatar_model → another_model → clone_model → server_model`，再对 `.gim` 路径做子串匹配。
★ 我们只用了 `another_model`（废弃模型黑名单），这里说明还有 `clone_model`/`ext_model`/`interactive_model`
等一整排模型变体可用，形态/克隆判定可扩这串。

### ⑦ 模仿者 = 身份局（社交推理模式）隐藏身份揭示（2026-09-23 逆向，`sub_394ED4`）★用户点名的独立模式
**这才是用户说的"模仿者独立模式"**：一个类狼人杀的社交推理模式，每个玩家有隐藏身份（治安官/猎人/千面人…），
若辰把每个人的隐藏身份+阵营直接读出来显示 = 开天眼。开关 `显示身份` / `阵营与计数`。

> **★ 2026-09-24 两局实测结案（`_scripts\copycat300.ps1`，数据 `captures\cmd\copycat_0924_153905` / `_155412`）：**
> - 模式：`g_world_mgr.cur_world` = `WorldBattleCopycat`（wt=80，scene 82/83）；UI 有 `UIBattleCopycat*`。
> - 玩家 = `units_by_type[1088]` `CopycatPlayerUnit` ×12（**不在键 1/2**）；死亡后原单位留在 1088 且 `model.visible=False`，
>   另生成 `[1089] GhostCopycatPlayerUnit`（同 `unique_id`，`identity_id=None`，`copycat_index=-1`）。
> - **身份 = `unit.identity_id`**，进局约 2 秒赋值、整局不变（开会/死亡都不变）。冗余两份：
>   `unit.params['identity_id']`、`unit.combat_unit.components[1007].identity_id`（= 若辰说的"组件里的身份"）。
> - **全场 12 人的真身份都下发给客户端**：两局均 12/12 有值、构成均为 7×1xx / 3×2xx / 2×3xx；
>   第二局本人是中立(301)，照样读到 3 个模仿者。用户确认两局本人身份（114 掮客 / 301 流浪汉）与游戏一致。
> - **游戏内号码 = `copycat_index + 1`**（用户确认：本人 index 4 = 5 号、死亡者 index 9 = 10 号）。
> - **阵营没有独立字段**（若辰的 `camp*`/`camp_type` 全不存在）：按号段 1xx=侦探团 / 2xx=模仿者 / 3xx=中立。
>   `g_avatar.copycat_advance_data.last_camp_lst`（如 `[1,1,1,1,2]`）是本人历史阵营，编号同此。
> - 其他：`[1210] CopycatDirectorCloneUnit`（导演局才有，identity=None）、`[1203] CopycatGhoulUnit` 食人鬼
>   （`dead_reason='ghoul_kill'`、`kill_anim_src_uid` 指向它）、1092~1214 是场景交互物。
> - 101 = 侦探（2026-09-26 解跳转表确认，见下）。名字表实测只对上本人两项 + 号段/阵营结构。
> - 叠加层已落地（`check_lobby` 认 1088、身份簿锁存、独立折叠框、按 `unit.position` 绘制）—— **完整记录见 [`copycat.md`](copycat.md)**。
>
> **★ 假面舞会（所有人变石像）若辰怎么处理 —— 2026-09-26 查证：没有任何专门处理，它天生不受影响。**
> - 全二进制搜不到 `masquerade`/`statue`/`dancer`/`舞会`/`石像`；`model_ref` 只在一张通用"模型属性候选名"表里
>   （`model_obj/ref_model/worldModel/modelObject/_model/_world_model/render_model/scene_model/model_ref`，@`0x4D9CE8`）。
> - 原因：它**根本不按场景对象/模型配对**。位置读 Python 单位属性 `position → visual_position → logic_position → pos →
>   world_position → puppet_position`（`0x3AC114` 一带）自己用矩阵投影；身份读 `combat_unit.components` 里的
>   `identity_id`（`0x3B60F8`~`0x3B6A30`）。模型换成石像、场景里多出 12 个对象，对它都无所谓。
> - 我们照抄了这条路（2026-09-26，见 [`copycat.md`](copycat.md) 第四节）。

**核心：identity_id → 身份名 跳转表**（`sub_394ED4` 内 @0x399DDC，switch 值 = `[身份对象+0x30]` = identity_id，基数 101）：

| id | 身份 | id | 身份 | id | 身份 |
|---|---|---|---|---|---|
| 101 | **侦探** | 113 | 密探 | 205 | 怪盗 |
| 102 | 哨兵 | 114 | 掮客 | 206 | 催眠师 |
| 103 | 治安官 | 115 | 药剂师 | 207 | 地下医生 |
| 104 | 猎人 | 116 | 巡林员 | 208 | 处刑人 |
| 105 | 香料师 | 117 | 执灯人 | 209 | 指挥家 |
| 106 | 锁匠 | 118 | 评论家 | 301 | 流浪汉 |
| 107 | 银行家 | 201 | 神偷 | 302 | 送货员 |
| 108 | 修士 | 202 | 千面人 | 303 | 愚人 |
| 109 | 演说家 | 203 | 阴谋家 | 304 | 棋手 |
| 110 | 拳击手 | 204 | 烟火师 | 305 | 清洁工 |
| 111 | 灵媒 | | | 306 | 顾问 |
| 112 | 学徒 | | | 307 | 降灵师 |
| | | | | 308 | 导演 |

- **101 = 侦探**（2026-09-26 整表解码，`llvm-objdump` @`0x399DB4`）：`sub w9, w8, #0x65` → `cmp #0xcf` → 越界走默认(`未知身份`)；
  跳转前先 `mov x6, x19`（`x19` = 字符串"侦探"@`0x2EF53`，循环外预装），再 `ldrb [0x2DDC60 + idx]` → `br 0x399DE0 + b*4`。
  **只有 101 那格直接跳到汇合点 `0x399F84`、不改 `x6`**，所以显示"侦探"；其余 34 个 id 各自 `adrp+add` 换名；
  119~200 / 210~300 走默认 = `未知身份`。~~原记录"101 取对象自带名""侦探走 `identity_type` 特判"是错的~~。
- id 分三段 `101–118 / 201–209 / 301–308` = 三个阵营。若辰的阵营名表（`0x4D8E58`）是 **侦探团 / 模仿者 / 神秘客**
  （中立在它那里叫"神秘客"；我们界面仍写"中立"，用户定的）。
- 已用户确认：103=治安官、104=猎人 与实际模式对得上（2026-09-23）。

**阵营判定两条路**：
1. `sub_3BE5BC`：优先读 `camp_type` 属性 → int，∈{1,2} 直接用（1/2）。
2. `sub_4112E0`（类名兜底，★通用）：类名含 `butcher|hunter|ripper|killer` → **阵营1**；含 `civilian|survivor|player` → **阵营2**。

**相关字段**：`identity_id`(决定上表) / `identity_type`(只在通用"单位类型候选名"表里，与侦探无关) / `role_id` / `role_uid` / `role_type`；
`camp_type`(∈{1,2}) / `camp_id` / `_camp` / `camp`；类名 `hunterunit` / `civilianunit` / `mycivilianpuppetunit` / `mirrorcivilian`。
**显示串**：`%s[%d]未知身份%d丨%s` / `resolved_role=` / `identity=` / `未知身份` / `未知阵营`。

> 备注：`侦探团`/`模仿者`/`神秘客` 是阵营名表（`0x4D8E58` 起，经 `.rela.dyn` 重定位引用，所以 ADRP 交叉引用搜不到）；
> `记录员`(@0x37991) 仍不在 switch 表里，用途未知。我们已支持该模式（见 [`copycat.md`](copycat.md)）。

### ⑤ 监管动作命中动作表（自动飞轮/砸板的判定核心）
- **读监管当前动作**：见"状态/动作/朝向"那段（`state*`/`action`/`action_id`，从 combat_unit）。
- **动作表结构**（`sub_3488D8` 构建，CSV 列头 `# name,camp,action,type,delay_seconds,n`）：
  每行 = (监管者名, 阵营, action_id, 类型, 延迟秒, n)；`type ∈ normal | charged | skill`。
  来源 = 编译期内置表 + `/data/若辰飞轮动作.csv`；统计 `config rules=%zu self_actions=%zu rejected=%d builtin=%d`。
- **学习建表**：`lian_action_learn_enabled` / `lian_action_learn_hunter` / `lian_action_learn_survivor`
  —— 开启后自动记录观测到的 (监管者名, action_id)，增量补全表。
- **匹配判定**（格式串实锤）：
  - `名字=[%s] 去括号=[%s] 索引命中=%d 候选行数=%d 动作=%d(0x%08X) 结果=%d 并列=%d 行=%zu 距离=%d`
    —— 监管名去括号后查表，候选行里按 action_id 找最近匹配
  - `容差命中 action=0x%X 表内最近差=%d delay=%d` —— action_id 允许容差取最近，命中取该行 `delay_seconds` 当提前量
  - `已识别 -> 开启约瑟夫模式`、`受击确认(action=%d) -> 立即点第2下(回溯)` —— 特定动作触发连招

---

## 四、完整配置项 / 功能开关表（`sub_33831C` 读、`sub_34D600` 写，配置文件 `/data/local/若辰读取版_config.cfg`）

这是若辰的全部功能开关，**可当我们的功能清单参照**（带值的是数值/坐标项）：

```
绘制:  show_draw_line, show_draw_prophet(预知), show_draw_secret_mechine(密码机深挖),
       hook_draw_bones(骨骼), hook_draw_boxes(箱子), hook_copycat_mode(复制/镜像),
       hook_healing_progress(治疗), hook_draw_exit_gates(大门), reader_wuchang_landing(无常落地),
       hook_draw_talent_team(天赋), hook_box_talents(框上天赋), hook_waiting_stats(局前战绩),
       hook_held_items(手持物), hook_only_started_generators(只显示已开机),
       hook_hide_generators_after_five(破译五台后隐藏), hook_gates_only_exit_phase(仅开门战显示门),
       hook_skill_cooldowns(技能CD), show_draw_cellar(地窖), show_draw_wood(板子), show_draw_Prop(道具),
       inform_ghost(预知监管), unified_show_runtime_data(运行数据), redqueen_mode(红夫人镜像)
天赋绘制参数: hook_talent_x/y/font_size/row_height, hook_bone_thickness
地图:  enable_arms_factory(军工厂), enable_radar_mode(雷达), radar_zoom_range, enable_mirror_edge_indicator,
       enable_closest_mirror_only, g_manual_map_index, map_display_size, map_pos_x/y
自动/触摸:
       lian_banzi_enabled/mode(自动盖板), show_wood_touch_point, show_banzi_range, wood_range, Touch_X/Y
       lian_flywheel_enabled(自动飞轮), lian_flywheel_x/y, lian_flywheel_show_point/region/region_size,
       lian_flywheel_release_delay, lian_flywheel_counter_skill, lian_flywheel_block_board
       lian_skill_enabled(连招/香水), lian_skill_x/y, lian_skill_tap_interval, lian_skill_tap_hold,
       lian_skill_one_shot, lian_skill_recall_window, lian_skill_hit_
       lian_emote_enabled(表情), lian_emote_slot_override, lian_emote_agree_/disagree_
       lian_action_learn_enabled/hunter/survivor(动作学习)
       auto_qte_enabled(自动校准), auto_qte_touch_lead_ms, auto_qte_virtual_lead_ms, auto_qte_real_lead_ms,
       auto_qte_perfect_margin, auto_qte_touch_x_ratio/y_ratio, auto_qte_touch_hold_ms, show_auto_qte_touch_point
       vol_up_action / vol_down_action(音量键映射动作)
手记:  hand_note_mode, hand_note_font_size, hand_note_distance_, hand_note_color_
其他:  mem_feature_fps(内存功能帧率), core_bind_draw/data(绑核), Debugging
```

## 四点五、准备阶段的信息获取（★直接答我们主 SKILL 那条待办）

我们主 SKILL 的结论是"准备阶段 unit 没创建，读不到人，得去找大厅侧的房间/匹配数据结构（不在 unit 上）——那是开放式搜索"。
**若辰已经把这个开放式搜索做完了**，答案是走 **UI 管理器**，不走 unit（`sub_3F2A1C` / `sub_3B9530` 实锤）：

### 数据源：`UIRoomWait` 这个 UI 对象
```
game_kernel → g_ui_mgr → ui_dict → 查 "UIRoomWait"
    ├─ player_tips → data   （准备阶段玩家列表，list 步长 0x78，每项含名字/uid/信息）
    ├─ room_guuid           （房间全局 id）
    ├─ members              （房间成员，sub_3B9530 读）
    ├─ seat_idx             （座位序号）
    └─ waiting_for_process  （预知/等待状态）
```
读取原语：`sub_3F5AEC(obj, root, "key", &out)`（按 key 读属性）+ `sub_372F04`（在 ui_dict 里按名字查 UI）。
**这就是"不在 unit 上的大厅房间/匹配结构"**——挂在 `g_ui_mgr.ui_dict["UIRoomWait"]` 上，准备阶段就绪。

### 阶段/模式判定：走 world_mgr（不靠 units_by_type 的键）
```
game_kernel → g_world_mgr → battle_world / cur_world → scene_id / world_type
```
`world_type` 是个数值，直接分模式（之前逆到 `world_type==0x2713` 那个判据）。比我们待办里"数 units_by_type 的键区分大厅/准备/局内"更直接。

### 战绩/档案（⚠ 2026-10-16 订正：不是读游戏内存，是若辰发 HTTP 查后端）
~~`国服等待界面显示本阵营档案` + `sub_3EC5C0` 读 `butcher_data`/`civilian_data`——账号级，不挂 unit。~~
**实锤是 `GET /api/v1/uid/<uid>/profile` 到 `w2.t3yanzheng.com`（带 Bearer token），`sub_3EC5C0` 解析返回的 JSON（见第三节 ② 订正块）。** 游戏客户端根本不持有任意对手的认知分/胜率，所以这份数据**既不在 unit、也不在任何本地 Python 对象**里。
→ 真正的分界：**挂 unit 的（天赋）准备阶段读不到；挂 UI/room 的（`UIRoomWait` 人员列表）能读；认知分/段位/胜率只能向若辰后端查，本地无源。**

### 工程做法：独立等待服务线程
`ruochen-waiting-service-v1` = 若辰给准备阶段预知单开了后台服务线程。
⚠️ 对照主 SKILL 待办 #10「别给预知单开线程，因为数据源是最贵的全数组类名扫描」：**若辰能单开，正因为它把数据源
换成了便宜的 `UIRoomWait` UI 对象**。所以只要我们把预知数据源从"类名扫描"改成"读 UIRoomWait"，待办 #10 的顾虑就不成立，可以放心按阶段单独跑。

**一句话**：准备阶段人员/房间信息在 `game_kernel.g_ui_mgr.ui_dict["UIRoomWait"]`（`player_tips.data`/`members`/`room_guuid`/`seat_idx`/`waiting_for_process`），模式判定用 `g_world_mgr.battle_world.world_type`，战绩用账号级 `butcher_data/civilian_data`。全是 Python 层按名字可达，不依赖 unit。

## 四点六、触摸注入后端（★做自动功能必备；比 `auto-pallet.md` 那套更成熟，核心知识）

自动盖板/飞轮/校准/连招都靠往触摸设备注入手指。若辰这套（`sub_422C04` 设备初始化 / `sub_421B1C` 枚举 /
`sub_4241C8` 单击 / `sub_42499C` 双击 / `sub_425004` 飞轮释放）是纯 root、不需要 uinput 克隆的做法。

### ★ 2026-09-26 更正：不是"按优先级自动选"，是**用户启动时选一个驱动，触摸后端跟着驱动走**

（IDA 反汇编 `sub_31C3CC` 主流程 / `sub_32B310` 连接分派 / `sub_422C04` 触摸初始化 实锤。旧写法"天堂 > TwT > /dev/input 按优先级"是错的。）

启动时终端提示 `请选择已刷入的驱动：1. RT  2. TwT  3. 天堂`，`strtol` 读一个数，**只连这一个驱动**（内部编号 RT=2 / TwT=1 / 天堂=3，
存在驱动对象 `+8`，连上后 `+4` = 实际后端）。30 秒连不上就报 `驱动连接失败：30 秒内未找到支持的游戏进程`。**只需要刷一个。**

| 选项 | 连接方式 | 读写 | 触摸 |
|---|---|---|---|
| 1 RT | 扫 `/dev`（跳过 vndbinder/watchdog0/device-mapper/xt_qtaguid/gpiochip）+ 扫 `/proc/*/fd` 里带 ` (deleted)` 的节点，`ioctl 0x801/0x803` 探测，路径缓存到 `/data/local/tmp/ruochen_driver_node`（`sub_32C160`/`sub_32D278`） | 驱动 | **/dev/input MT-B 空闲 slot**（RT 没有内核触摸） |
| 2 TwT | `syscall(142 /*reboot*/, 0x114514, 0x1919810, 0x2778, &fd)` 拿 fd；失败则扫 `/proc/self/fd` 找 `anon_inode:TwT_driver`（`sub_32BA98`）；再读目标 `/proc/pid/maps` 验证（`sub_32BC30`） | 驱动 | **内核触摸**：init `ioctl 0x400C5406`(12 字节全 0，`EALREADY` 也算成功) / down `0x400C5407 {slot,x,y}` / up `0x400C5408 {slot,0,0}` |
| 3 天堂 | **静态链进了天堂官方客户端**（就是 `paradise_api.h` 那个类，对象 8 字节 `{pid, fd}`，带 OLLVM 虚假分支 + 字符串加密；连不上直接 `exit(1)`）。`syscall(142, 0x7A3B9C4D, 0x2F8E1D6B, 0, &fd)`（`sub_48566C`） | 驱动 read `ioctl 0xC0285709` | **内核触摸**：`touch_init(短边, 长边)` = `ioctl 0x4008571E {int,int}`（`sub_485AB4`）/ `touch_up(slot)` = `ioctl 0x4018571F {u64 op=4, u64 0, u32 slot}`（`sub_485CE4`）/ `touch_down` 在 `sub_485BC8`（**没逐字节看**，大概率同一个 0x571F 换 op） |

触摸分派（`sub_422C04` @`0x422D84`）：`(后端 & ~2) == 1`，即 TwT 或天堂 → 走内核触摸 `sub_425A04`；否则（RT）→ `/dev/input`。
**内核触摸初始化失败不会退回 /dev/input**，只打 `init_failed reason=kernel_touch_init backend=%s`，这时就没有触摸。
内核触摸时 slot 号仍由若辰传入，但注入由驱动在内核里合成，跟 `/dev/input` 那套"找空闲 slot"不是一回事。

**我们的驱动**（`kerneldriver-qxqd.hpp`，`socket(AF_INET)` + `ioctl 601~608`）**不是这三家里的任何一个**，也没有触摸命令 →
`Touch::InjectTap` 走的 `/dev/input` 空闲 slot = 若辰在 **RT 模式**下的触摸路径。

失败原因串：`no_input_devices` / `no_compatible_touch_device` / `kernel_touch_init`。

### /dev/input 后端流程
- `sub_421B1C`：`opendir("/dev/input/")` → readdir 过滤 `event*` 前缀 → 收集所有 `/dev/input/eventN`。
- 逐个探测 **MT type-B 触摸屏**（EVIOCGABS 读 `ABS_MT_SLOT`/`ABS_MT_POSITION_X/Y`），选中 →
  `选中 MT-B 设备 path=%s scale=%.6f,%.6f btn_touch=%d`。
- **scale = 屏幕分辨率 ÷ 设备物理坐标范围**（`init_start screen=%.0fx%.0f physical_...`），并记 `orientation`。
- 成功：`init_ok path=%s fd=%d scale=%.6f,%.6f orientation=`（内核后端则 `init_ok backend=%s_kernel orientation=`）。

### ★★★ 关键：MT-B **空闲 slot 共存注入**（不打断真手指/摇杆）
- 用 **MT type-B 协议 + 分配一个空闲 slot** 注入手指。**没做 EVIOCGRAB 独占、也没克隆虚拟设备**
  （`sub_4241C8`/`sub_42499C` 里核心失败码是 `no_free_slot`，证明它是往同一个触摸设备申请空闲 slot）。
- 真手指用它自己的 slot，注入用另一个空闲 slot → **两者在同一 eventX 上共存**，摇杆/技能照常。没有空闲 slot 就失败退出，不抢占。
- **这比 `auto-pallet.md` 那套"独占真实触摸屏 + 克隆虚拟设备 + 专用 slot"更简单**：不用 EVIOCGRAB、不用建克隆设备，
  直接往真设备写另一个 slot 即可。**做我们自己的 auto-pallet 时优先考虑这条路。**

### tap 时序（`sub_4241C8` 单击 / `sub_42499C` 双击）
1. 自旋锁串行化（`sched_yield` 忙等）
2. 校验 backend ready + position valid（`scale>0`、x/y 有效）
3. **分配空闲 slot**（无 → `no_free_slot` 失败）
4. **DOWN**：`ABS_MT_SLOT` + `ABS_MT_TRACKING_ID` + `ABS_MT_POSITION_X/Y` + `BTN_TOUCH` + `SYN_REPORT`（失败 `down_write_failed`）
5. hold `hold_ms`
6. **UP**：`ABS_MT_TRACKING_ID = -1` + `SYN_REPORT`（失败 `up_write_failed`）
7. 报 `completed` + `latency_ms`
- 结果码全集：`completed / busy / not_ready / no_free_slot / invalid_position / cancelled_before_down / down_write_failed / up_write_failed / cancelled`
- source 标签：`cover`(砸板) / `flywheel_lift`(飞轮) / `double_tap`(连招) / `generic`；坐标从触摸对象 `[+0xA0]`(x)/`[+0xA4]`(y) 读。

### 绑核（降注入延迟）
- config `core_bind_draw` / `core_bind_data`：把**绘制线程**、**数据/触摸线程**分别 `sched_setaffinity` pin 到指定核。
- `TID=%d 已绑定核心 %d`；核不存在 → `[AFF] 核心 %d 不存在（共 %ld 核），退回核心 %d`；`core<0` → `[AFF] 跳过绑核（交给内核调度）`。

### 对我们 auto-pallet 的价值（对照 `auto-pallet.md`）
1. **共存 slot 注入 > 独占克隆**：不 grab、不克隆，往真触摸设备申请空闲 slot，真手指照常 —— 实现更简单更稳。
2. **三后端优先级**（内核驱动 > /dev/input）可抄：有内核驱动延迟更低，没有就 /dev/input 兜底，纯 root 即可跑。
3. **scale = 屏幕分辨率 ÷ 设备 ABS_MT 物理范围**：坐标换算的正解（我们叠加层坐标→触摸坐标要用它）。
4. **slot 管理 + 结果码体系 + 绑核** 直接借鉴；`sub_425004`(flywheel_lift 释放) 是自动飞轮的触摸落点参考。

⚠️ 注意 `sub_32BA98`（同时引用 `TwT_driver` 和 `/proc/self/fd` 扫描）是**反调试/反注入**探测，别和触摸后端混在一起看。

## 四点七、骨骼原生读法 + 遮挡系统（★同时补我们「骨骼」和「遮挡」两个短板，2026-09-25 逆向）

### 架构：独立 60Hz 线程，三段式，骨骼走**原生渲染层**（不走 Python）
```
sub_380038  reader-bones-60hz   60Hz 采样线程 + 本地碰撞网格构建（遮挡）
   → sub_3A32B0 / 3A37A4 / 3A38F0 / 3A3A24 / 3A3BDC  骨架发现（从 model 找 skeleton）
   → sub_39F0CC  reader-bone-pose  逐关节读世界变换 → 骨骼点（纯偏移原生读，全程无属性名）
   → sub_3CD688  anim_visible_check  可见性收集
```
**关键**：骨骼从**渲染层原生骨架**按偏移读，**不是** Python 对象。和我们 SKILL 里「骨骼子系统走渲染层」一致。

### 关节按名字映射（抗热更）
`bone_joint_maps_cached` / `bone_name_tables_accepted/rejected`：读骨架的**骨骼名表**，建 `名字→索引` 缓存。
关节靠**名字**定位、不靠写死索引 —— 引擎重排关节顺序也不失效（和我们 Python 层"按名字查"同思路，用在原生骨架上）。

### 时间域平滑（拒抖动，只发稳定姿态）★可治骨骼跳变
`transient_pose uid=%s sample=%d prev_v curr_v prev_h curr_h` → `stable_pose uid=%s samples=%d`：
连续采样，比相邻帧竖直/水平跨度(v/h)，稳定够样本数才发布；不稳的丢（`bone_rejected_snapshots`/`bone_filter_rejected`）。

### 坐标归一
`swap_yz`（引擎 Y/Z 轴交换）、`vertical_span`/`horizontal_span`（骨架竖直/水平跨度）、`anchor`（锚点）→ 投影成方框/骨骼线。

### ★ 遮挡系统（我们最大的短板）——两条独立路，可叠加
**路1：渲染层可见性属性**（`sub_3CD688`，用 `sub_39E26C` 解析 + `sub_3A7F04` 读 bool，收进一个 map）：
```
is_visible_in_this_frame  ← ⚠️ 活体实测=只判「在不在视锥/视野内」，不含墙挡遮挡（见下方 2026-09-25 对照实验）
in_xray / is_show_xray     ← 是否处于透视穿墙状态
const_visibility           ← 常量可见性
force_invisible            ← 被强制隐藏
total_visibility           ← 综合
```
→ 报告分三档 `bone_visible_units / bone_occluded_units / bone_unknown_visibility_units`（这三档是**路2 射线**判的，不是路1）。

> **★ 2026-09-25 活体对照实验（注入 in-process Python，监管视角 4 人机）**：把 囚徒(露头)/调香师(被挡)/邮差(被挡) 都放视野内，
> `unit.model.is_visible_in_this_frame()`：**三个全 True**（视野外那个 False）。**被墙挡的照样 True** → 证实 vif = 视锥内/外，**不是遮挡**。
> 同时 `in_xray`/`is_show_xray`/`total_visibility`/`const_visibility`/`force_invisible`/`get_occlude_id(=-1)` 在遮挡/露头之间**全一样**，
> **没有任何现成属性能反映墙挡**。**教训**：引擎不暴露"墙后"的现成位，真遮挡**只能靠几何射线**（正是若辰自建碰撞网格+射线的原因，见路2）。
> `is_visible_in_this_frame()` 仍有用 = 便宜的「在不在屏幕上」判据（比投影 VP 矩阵省），但别拿它当遮挡。
> 附：`model.hit_by_ray(p0,dir,test_faces=True)` 存在但**坐标是模型局部空间**、且只测"射线打不打得到这个模型自己"，判墙挡不实用（要逐墙逆变换）。

**路2：本地碰撞网格 + pruner + 射线**（`sub_380038`，`reader-local-collision`）：
```
stage=%s scene=0x%llx pruner=0x%llx remote=%u shapes=%u boxes=%u triangle_instances=%u
  meshes=%u vertices=%llu triangles=%llu rejected=%u build_ms=%llu ... collision=%d/%d/%llu rays=%d/%d
```
→ 从游戏物理场景**构建碰撞加速结构（pruner，类 PhysX broadphase）**，再用**射线**测目标是否被墙/障碍挡住。
这就是我们想要的"遮挡射线检测"，而且**自己建碰撞网格**做，不依赖引擎可见位。

### 性能自打点
`target_hz=%u frame_us=%llu actual_avg_us=%llu ... visibility=%d/%d/%d maps=%d names=%d/%d failures=... collision=%d/%d/%llu rays=%d/%d`（60Hz 目标，每帧耗时/可见性三档/碰撞/射线全计数）。

### 落地建议
- **骨骼**：原生渲染层骨架 + 关节按名字映射 + "稳定姿态才发布"（治跳变）。**★ 生产路线要抄若辰的原生偏移**
  —— 见 [`native-bones.md`](native-bones.md)（`get_bone_*` 是方法只有注入能调，进不了驱动裸读，只能当探针取真值）。
- **遮挡**：`is_visible_in_this_frame` 只是「在不在视野」（活体已证，见路1），要真墙挡只能上"本地碰撞网格+射线"（路2）或 SOC，没有现成位。

> **★ 2026-09-25 活体发现（`unit.model` = 原生 `world.model`）—— ⚠️ 下面这套 `get_bone_*` 是【方法调用】，只有注入能调，只能当探针取真值；生产裸读走 [`native-bones.md`](native-bones.md)**：
> ```
> model.get_bone_count()      → 53（标准 biped：'biped head'(17)/'biped spine'/'biped l hand'…）
> model.get_bone_name(i)      → 骨骼名（按名字取，抗热更）
> model.get_bone_matrix(i)    → 4x4；bone0(根)=世界矩阵(平移≈unit世界坐标)，子骨骼=父相对(局部)
> model.get_bone_prs(i)       → (位置, 旋转四元数, 缩放)
> model.get_bone_by_name(name) / bones_bounding_box / get_animator()
> model.world_position        → 模型世界根(=unit脚底)
> ```
> 实测：`get_bone_matrix(0)` 平移=`(146.1,8.76,-595.97)`=世界；`get_bone_matrix(17=head)` 平移=`(0.498,0,0.0017)`=父相对。
> **世界骨骼点**：根(0)是世界矩阵、子是父相对 → 沿父链 FK 累乘。`get_accum_matrix(i)` 返回 None（签名/未启用，可再试）。
> 若辰啃原生偏移是因为它是**外部读、进程里没 Python**；我们有注入 → 整个骨骼子系统换成调 `get_bone_matrix/prs` 更简单、按名字几乎不失效。
> （`_anim_data_component`/`_anim_graph_component`/`animator`/`animation_controller` 在 unit 上都是 None，骨骼只在原生 model 里。）

## 四点八、本地美化（皮肤/挂件本地解锁，2026-10-04 拆）—— 若辰唯一一个"写游戏状态"的功能

> **★ 2026-10-16：本地美化已单独建了完整技术栈 SKILL 在桌面 `本地美化\SKILL.md`**（投递链、脚本逐段、落地路径 A/B、风险、对象/方法速查）。要抄进我们叠加层时以那份为准；本节是原始拆解记录。

**存档**：`逆向存档\_第三方\若辰_10.1.74\beautify\`（`rc_beautify.so`、`kBeautifyScript.py`、`朋友版_解锁美化.py`），
提取脚本 `逆向存档\_scripts\ruochen_extract_beautify.py <主程序> <输出目录>`（找第二个 ELF 头，不写死偏移）。
⚠️ 下面的属性名/方法名**全部来自代码，我们没活体验证过**。

### 投递链（主程序 → so → Python）

```
主程序: 特征扫描 libclient.so 得 4 个 CPython RVA（见第五节 beautify_*_rva），缓存 .cache_rc_beautify_%016llx
        校验失败任一 → "美化保持纯读取"：签名未唯一匹配 / RVA 特征落在函数内部 / GIL 入口间距校验失败
     → ptrace 注入内嵌 so（主程序文件 +0x2d6730，30000 B，md5 ba34ce71…）
     → 调 ruochen_beautify_start_v1(ensure, release, run_simple_string)   三个参数任一为 0 返回 -2，CAS 保证只启动一次
so:    分离线程 Execute: ensureGil → runScript(kBeautifyScript) → releaseGil，logcat 标签 RCBeauty "script_exit=%d"
       依赖只有 libc/liblog/libdl/libm，不碰任何游戏符号；弱引用 memfd_create（推测从内存加载，未验）
脚本:  起 Python 守护线程，100ms 轮询 UDP 127.0.0.1:55556 收 {"type":"hook_control","local_beautify_run":bool}
       状态回报 UDP 55555 {"type":"beautify_diag",...}，并写 /data/data/com.netease.dwrg/files/beautify_diag.json
主程序等 55555 第一条回执，超时报 "美化首次回执超时"
```

**so 只是脚本执行器**，开关全走 UDP，不重复注入。这跟我们 `injection.md` 那条链同构，区别是它的 CPython 入口全靠扫描。

### 脚本做了什么（四个 hook + 解锁列表）

| 动作 | 位置 |
|---|---|
| 把配表里所有皮肤追加进"已拥有" | `GK.DM.cloth_data` → `g_avatar.role_cloth[str(pid)][1]`；`update_unlock_cloth_type_info()` 刷新 |
| 所有挂件追加进"已拥有" | `GK.DM.decoration_data` → `g_avatar.article_unlock['decoration_list']` |
| 换皮肤不发服务器 | 替换 `Avatar.set_cur_role_cloth(role_id_str, cloth_id, will_start_game, need_reply=False, match_type=None)`，改调 `reply_update_cloth(id, {'role_id': int})`（走游戏自己的回执流程） |
| 换挂件不发服务器 | 替换 `Avatar.update_article(article_type, article_id, info=None)`：`ComuKeys.ARTICLE_TYPE.DECORATION` 改调 `reply_update_decoration` |
| 局内自己用选中皮肤 | 替换 `ClientUnits.BaseUnit.BaseUnit.__init__(params)`：`params['uid'] == room.info_dict['self_uid']` 时改 `cloth_id` / `model`(= `cloth_data[id]['model_path']`) / `article_setting` |
| 扩展资源 | `article_unlock` 下 `appendage_list` / `face_frame_list` / `face_vfx_list` / `tag_vfx_list` / `specific_action_list` / `specific_action_sfx_list` / `profile_tag_list` / `profile_decoration_list`，配表按 `<stem>_data` 等候选名找；`appendage_id_list`、`reply_unlock_face`；`update_article` 再包一层：type `2`→`reply_update_specific_action`、`6`→`reply_update_appendage`（并写 `article_setting['role_appendage'][role]`）、`9`→`reply_update_face`、`21`→`reply_update_specific_action_sfx` |
| 回滚 | 解锁时记下补进的 id（`C\t角色\t皮肤` / `D\t挂件`）、原皮肤（`LocalArticleUnlockOriginalCloths`）、扩展资源整份快照；关闭时全部还原 |

防重复安装的标记是函数对象上的 `LocalArticleUnlockHooked` / `LocalResourceUpdateHooked` 属性，原函数存在 `...Original` 里。
脚本里注释 `Extended resources are layered on top of the original 0806 skin path` —— 有个 8 月 6 日的基础版。

### 朋友版 `解锁美化.py`（2026-10-04 用户转来）：同源分支，**有致命 BUG**

同一套基础代码（函数名、标记名、撤销格式全一样），但**只有脚本、没有投递手段**（末尾 `run('enable')` + `print`，要靠别的执行器 exec）。

| | 朋友版 | 若辰 |
|---|---|---|
| 换模型同时换 `anim_group`/`low_mtg`/`fast_low_mtg`/`se_path` | **有** | 没有（只换 `model`，另有一张空的 `LOCAL_BEAUTIFY_MODEL_OVERRIDES`）|
| 皮肤专属动作：hook `worlds.BattleEvent.BattleEvent.handle_state_update_event`，`ENTER_STATE` 时把 `params['anim_name']` 里的默认动作换成 `state.get_action_data_of_state(params)['action']`（需 `replace_group_id == 皮肤id`），并重绑 `room.battle_event.FUNC_HANDLE_EVENT` 里已绑定的方法 | **有，但跑不通** | 没有 |
| 扩展资源 / 恢复原皮肤 / UDP 开关 / 诊断 | 没有 | 有 |

**★ 卡模根因（"触发动作时皮肤不动"）**：第 21 行调用 `PatchLocalSkillStateAnimation(...)`，**文件里没有定义**（从更大的版本里截出来时漏了）。
本机单位每次 `ENTER_STATE` 都会走到这里（第 18 行 `SelectedCloth != Unit.cloth_id` 恒不成立，因为 init hook 已把 cloth_id 改成选中的），
`NameError` 冒出包装函数，`Original(...)` 不执行 → 状态切换整个丢掉 → 不播动画。
修：删第 21~23 行；包装函数里 `try: event = Patch(event) except Exception: pass` 再调原函数（补丁出错最多是动作没换，不会再吞事件）。

**哪个更完整**：若辰（稳健、资源全、能回滚）。朋友版唯一多出来的是动画配套，若辰缺这块的后果
（自带动作组的皮肤播默认动作）是推测，没实测。要合并就以若辰为底，移植 anim 字段和修过的状态 hook。

### 对叠加层有用的部分

- `GK.DM.cloth_data[cloth_id]['model_path']` = 皮肤模型路径 → 可以把场景类名（`.gim` 路径）反查到 `cloth_id` / `role_id`，做皮肤类名映射时用。
  `cloth_id ≈ pid*100+款式` 已在 `idv-replay-genius` 记过。
- `g_avatar.role_cloth[str(pid)][0]` = 本机当前穿的皮肤。
- `room.info_dict['self_uid']` = 本机单位 uid（另一个"自身"来源，与 `g_cam_ctrl.unit` 见主 SKILL）。

## 五、SO 自愈画像系统（作者怎么扛热更，值得学）

若辰对付热更的办法和我们的 `PyRoot.h` 思路一致但更全，缓存在 `/data/local/tmp/ruochen_so_profiles`：
```
matrix_rva / matrix_feature_rva / matrix_instruction_rva   // VP 矩阵定位（世界→屏幕）
pyruntime_rva / py_type_rva / py_long_type_rva             // CPython 运行时（读 Python 对象）
beautify_gil_ensure_rva / gil_release_rva                  // = PyGILState_Ensure/Release
beautify_run_simple_string_rva / run_string_rva / err_print_rva  // = PyRun_SimpleString/PyErr_Print（注入执行 Python）
```
全部用**特征签名扫描**动态定位，带 `live CPython type validation failed` 运行时校验，`一键适配更新` 手动触发。
和我们 `PyRoot.h` 读 `.PyRuntime` 段找 sys.modules 是同一套哲学（见 SKILL 待办 #5）。

---

## 五点五、VP 矩阵链定位（2026-09-23 逆向，和我们的矩阵链交叉验证）★

作者把链条**直接写死在日志串里**：`Lua entry search -> 0xA58/0xCA8 -> +0x2C0`（字符串 @0x339db），
`sub_36D8E0` 汇编实锤。核心函数：`sub_36B820`(初始化，起常驻线程) → `sub_331850`(线程) →
`sub_36BA8C`(扫描主循环，4.5KB) → `sub_36D8E0`(候选校验器) → `sub_36DE2C`(安全指针读原语)。

### 链条
```
候选槽 → [解引用] → entry
entry + 0xA58 → A
entry + 0xCA8 → B          ← 要求 A == B（双路交叉校验，这版两跳指向同一对象）
A + 0x2C0     → Matrix     ← 16 个 float = 4×4 VP 矩阵（64 字节）
```

**和我们的链正好吻合**：我们是 `根指针 +0xa58 → 矩阵对象 +0x2c0 = Matrix`（见 SKILL「矩阵链」节）。
两套**完全独立**的逆向都落到 `+0xA58 → +0x2C0`，**这两个偏移可信度因此拉满**。
`+0xCA8` 是我们没用过的第二跳，可当 `+0xa58` 失效后的备用（同一数组的另一个槽，
类比我们 `+0x330/+0x3B8/+0x440` 那组等间隔槽）。

### 校验器 `sub_36D8E0(candidate, &out_entry, &out_matrix)` 的验收（可直接搬来当热更自愈验收闸）
1. `read(candidate)`→entry；`read(entry+0xA58)`=A、`read(entry+0xCA8)`=B → **要求 A==B**
2. `matrix_addr = A + 0x2C0`
3. **指针范围校验**：低 40 位落在合法用户态区间
4. **映射表校验**：matrix_addr 落在 maps 区间表（`qword_5DE720`，步长 0x38，[+0]start/[+8]end/[+0x18]可读标志）
   内、后续 ≥0x40 字节可读 —— 同 `devread` 的"页必须常驻"
5. 读 64 字节 = 16 个 float，**必须全部有限**（逐个 FABS 比 +inf，NaN/inf 即废）→ 对应面板 `matrix_finite_values=`
6. **防竞态复读**：entry+0xA58/+0xCA8 再读一遍要求一致 —— 就是我们 `python-layer.md` 的"防竞态三读"，作者在矩阵上也做了

### 工程结构（值得学）
- 常驻后台线程循环重取，纳秒时钟（`0x3B9ACA00`=1s）限时退避，丢失自动重取（`Lua matrix unavailable; reacquiring`）
- **唯一性要求**：扫全部候选，命中不唯一就拒（`Matrix chain not unique: hits=%zu valid=%zu`），防撞假矩阵
- 配置项 `domestic_fixed_chain`：国服可走写死链绕过扫描
- 入口来源不同（若辰走"Lua entry search"扫候选，我们走 bss 签名 `(PerObjectParamBuffer`），但**殊途同归到同一个 `+0xA58→+0x2C0`**——哪套签名失效都能用另一套重定位。

---

## 六、怎么用这份文档做新功能（给未来的自己）

**要在我们自己的 ESP 里新增一个玩法功能时，流程改成：**

1. 先来本文档第二节/第三节查：**若辰读的是哪个 Python 属性名**（连同它那串候选名一起抄）。
   —— 这一步替代了"在对象图里瞎扫找字段"，作者已经替我们把字段名找好了。
2. 拿属性名去我们的 Python 层验证工具活体确认：
   `python _scripts\py_chain.py --type <键> --attr <属性名>`（见 SKILL 第零步）。
3. 读到值后套 [`python-layer.md`](python-layer.md) 三条铁律（逐实例算 entries / int-float 互变 / 防竞态三读）
   落进 `PyProgress.h` / `PyGenius.h` / 对应头。
4. 若辰的字段名是**这一版**提取的，网易改名时先试它的多候选串，仍不中再自己扫。

**注意边界**：若辰是"外部读 + 汇编级"，我们是"驱动/注入 + 源码级"；能直接搬的是**"读什么属性、怎么算"**
（第二~三节），**不能搬**的是它的触摸注入后端（`TwT_driver`/`/dev/input`）和 OLLVM 保护的卡密逻辑。

**原始产物**：源二进制已存档到 `逆向存档\_第三方\若辰_10.1.74\若辰正式版(4).sh`（md5 `c78b70da…`；原件在 `Desktop\新建文件夹\1\`）；
`.i64` 没存（会随临时目录清掉），需要时按下面重建：
用 IDA（`C:\ida83\` ASCII 联接）跑一次 auto-analysis 得 `.i64`（约 15 分钟）；本文档的属性名是从
`sub_3AAC54` 等函数的汇编里 `ADRL Xn, "..."` 注释提取的。**关键结论都已写进本文档，不依赖那些临时文件。**
