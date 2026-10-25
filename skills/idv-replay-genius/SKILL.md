---
name: idv-replay-genius
description: 第五人格(com.netease.dwrg)的天赋/辅助特质/技能冷却怎么读——录像文件(pickle)离线解析 + Python 层活体读取。任何时候要查"谁带了什么天赋""监管的辅助特质是哪个""技能冷却多少""录像文件里有什么"，或者要写这类解析脚本时，先读这个。与 idv-reverse-resume(场景对象层/ESP偏移)配套：那边是坐标和绘制，这边是玩法配装数据。
---

## 这是什么

第五人格的**玩法配装数据**（天赋、辅助特质、技能冷却）在哪、怎么读。两条独立的路：

| | 录像文件 | Python 层活体 |
|---|---|---|
| 在哪 | 设备上的 `.txt`（其实是 pickle） | 游戏内嵌 CPython 堆 |
| 拿得到 | 开局快照：全场所有人的天赋 + 监管辅助特质 | 实时：当前特质、技能冷却配置 |
| 优点 | 离线、可重复、不用开游戏 | 实时，能进叠加层 |
| 缺点 | 只有开局那一帧的状态 | 要在局内，且受内存压力影响 |

场景对象层（ESP 坐标那一套）和偏移失效排查看 `idv-reverse-resume`，
CPython 走法的通用知识看它的 `python-layer.md`。**那两份的结论这里不重复**。

---

## 一、录像文件：就是 Python pickle，不用写解析器

```
/storage/emulated/0/Android/data/com.netease.dwrg/files/netease/
    dwrg.common/Documents/video/<账号uid>/<对局guuid>/
        battle_frames_snapshot_0.txt    ← 开局同步帧，**天赋只在这个文件里**
        battle_frames_snapshot_1..N.txt ← 逐帧事件流
        game_info.txt                   ← 结算信息
        total_info.txt                  ← 时间轴事件(cipher_done / gate_open)
    vmap.txt                            ← 录像索引
```

扩展名是 `.txt`，内容是 **pickle 协议 2**（`\x80\x02}q\x00`）。游戏内嵌 CPython，
直接 `pickle.dump` 出来的，所以 `pickle.load` 就能读。

⚠ **pickle 反序列化会执行任意代码**，必须用受限 Unpickler。实测只需要放行三类：

| 引用 | 处理 |
|---|---|
| `bson.objectid.ObjectId` | 本地桩类，只当 12 字节 id 容器，不装 pymongo |
| `_codecs.encode` | 限定只允许 `(str, 'latin1')`，py3 的 bytes 就是这么还原的 |
| `__builtin__.set` / `frozenset` | 游戏写 pickle 用的是 **py2 风格模块名** |

现成实现：`C:\Users\31297\Desktop\逆向存档\_scripts\replay_genius.py`

```
replay_genius.py pull [目录]     # 从设备拉(自动处理 su 拷贝 + 权限)
replay_genius.py <目录>          # 解析单局或整个录像根目录
```

**对局文件夹名是 MongoDB ObjectId 风格，前 8 位十六进制是 unix 时间戳**，
所以按文件夹名排序 = 按时间排序，不用去看 mtime。

### 天赋在哪

```
battle_frames_snapshot_0.txt
  data[0].snap_shot.event_data.entities[<uid>]
      genius_id_lvs      = [[天赋id, 等级], ...]     全场每个人都有
      support_skill_id   = [id]    监管辅助特质；求生者恒为 None
      player_name / unit_type(1监管 2求生) / pid(角色) / is_bot / cloth_id
```

`game_info.txt` 的 `genius_data` 是另一份（按分支分页 `show_genius_dict`），互为校验。
**真人对局里 `genius_data` 装的是全场五个人，不只自己** —— 别拿它的键来认"谁是本机玩家"，
要用顶层 `unique_id`（我在这里错过一次，结果五个人全标上了★）。

`cloth_id ≈ pid*100 + 款式`，可以拿来交叉校验 pid。

**关键推论：客户端开局第一帧就拿到了全场所有人的天赋。** 所以"谁带了绝处逢生"
这类问题不需要等它生效、也不需要任何差分 —— 静态就能知道。

---

## 二、天赋 id 表（已验证）

**监管和求生者共用同一套 id 号段，同一个 id 两边是不同天赋，必须靠 `unit_type` 区分。**

### ★ 2026-09-22：完整 80 条全表已拿到，见 [`genius-table.md`](genius-table.md)

不用再靠差分推了。进程内注入直接读游戏配表
`GK.DM.civilian_genius` / `GK.DM.butcher_genius`（各 40 条，id 1~40），
名称经 `get_passive_skill_data_from_id_lv()` + `do_ui_tid_replace()` 解出中文。
**那是游戏自己的数据，不是推断。** 下面只留最常用的四个终端：

| id | 求生者 | 监管者 |
|---|---|---|
| **8** | 飞轮效应 | **禁闭空间**（官方写"禁闭"，旧记录写的"紧闭"）|
| **16** | 回光返照 | 底牌 |
| **24** | 化险为夷 | 挽留 |
| **32** | 膝跳反射 | 张狂 |
| 26 | **绝处逢生**（psv=102） | 掌控欲 |

结构也校正了：**不是"4 分支 × 8 槽位"**，而是由配表里的 `layer`/`node_seq` 定义 ——
`layer 1` 是 4 个分支根（id 1/9/17/25），`layer 4` 才是终端（8/16/24/32），
`id 33~40` 是 `layer 3` 的额外节点（`node_seq` 4/5）。`pre_genius` 给出前置依赖。
旧记录"1-8/9-16/17-24/25-32 分段"只是巧合地接近，**别再拿它当判据**。

"每人恰好占 2 个终端"这条实测结论**仍然成立**（注入实测：监管 18 条天赋里终端只有 16/24，
求生者 14 条里终端只有 8/16）。

> 历史：监管 8 曾经只是排除法推的，2026-09-21 拿注入脚本里那张 `TALENTS`
> 俗称表（封窗/底牌/一刀/张狂）做过交叉印证。现在由配表实测坐实，那一轮推理是对的。

### 「谁有谁没有」差分法（绝处逢生就是这么找出来的）

id→名字推不出来，必须外部对照。两种办法：

1. **用户直接报配装**。`game_info.txt` 的 `genius_data` 就是本机玩家的天赋，对着 id 报名字。
   四个终端天赋是这么定的。
2. **两局约束方向相反的差分**：
   ```
   候选 = (A局全员交集) ∩ (B局有的人交集) - (B局没有的人并集)
   ```
   绝处逢生：已知 A 局四个求生者全有、B 局只有其中两人有 → 五局样本下唯一候选 26。
   **两局方向相反是关键，只给一局的话候选会剩一大把**（A 局全员交集有 17/18/25/26 四个）。

---

## 三、辅助特质（监管专属）

`support_skill_id`，是个 list，实测都只有一个元素。跟天赋是**两套独立编号**。

| id | 特质 | 冷却 | 技能对象 id |
|---|---|---|---|
| 1 | 聆听 | **充能型**，参数未知 | ? |
| 2 | 失常 | 90 | ? |
| 3 | 兴奋 | 100 | ? |
| 4 | 巡视者 | 90 | ? |
| **5** | **传送** | **100.0** ✅实测 | 按角色不同，见待办 #3 的 `support_skill_data`（红夫人 `25741,25743`，共享冷却） |
| 6 | 窥视者 | **充能型**，最大 3 层 / 每层 30 秒 | ? |
| **7** | **闪现** | **150.0** ✅实测 | **711 / 712**（`game_start_cd=60`）|
| 8 | 移形 | 100 | ? |

冷却数值由用户 2026-09-22 直接提供（5/7 另有活体实测佐证）。技能对象 id 只有 5/7 验过，
其余六个等哪局带到了，探针会自动 dump `skill_dict`。

### ⚠️ 两种情况 `_cd_delta` 可能不够用（都还没验）

**(a) ~~充能型特质~~ —— 2026-09-22 用窥视者实测结案，见第四节「充能型技能」。**
结论：`power_num`=最大层数、`_cur_power_num`=当前层数、`_cd_delta`=距下一层回满的秒数。
**`_cd_delta` 语义统一**，普通技能是"剩余冷却"、充能技能是"下一层剩余"，一套读法通吃。

**(b) ~~底牌切换特质时"等比例返还冷却"~~ —— 2026-09-22 实测结案。**

**游戏在切换时直接重算 `_cd_delta`，读它就对，不用自己算比例。**

实测（红夫人带底牌，窥视者 3 层用掉 2 层 → 切成闪现）：

```
t=307.2   711(闪现)._cd_delta = 75.90   cd_time=150.0
t=347.6   711._cd_delta = 35.50    ← 40.4 秒过去减 40.4
t=351.6   711._cd_delta = 31.47    ← 4.03 秒过去减 4.03    速率恒 -1.0/秒
```

⚠️ **我原以为是它们、结果全程没动的字段**（别再查）：

```
监管本体.exchange_cool_time_list = [0,0,0]   切换前后完全相同
skill_mgr.cd_rate                = 1         同上
```

两个附带发现：

- **旧特质的技能对象会冻结**：切走之后 `25732._cd_delta` 死停在 `26.6498`、
  `_cur_power_num` 停在 `1/3`，不再递减。**不能靠"哪个在动"判断当前特质**。
- **`skill_mgr.leader_skills` 跟着切换变**：切换前含 `{25732, 25733, ...}`、
  切换后是 `{711, 712, ...}`（另含角色自身技能 2601/2604/2605/2610/2611/2612）。
  这是"当前辅助特质对应哪个技能对象"的可靠途径，配合 `support_skill_id` 用。

**"等比例"的公式（用户 2026-09-22 确认）**：按**已消耗比例**换算。
窥视者 3 层用掉 2 层 = 消耗 2/3 → 切到闪现得到 `150 × 2/3 = 100` 秒冷却。
实测读到 75.90 是因为切换发生在读取前约 24 秒（已经从 100 往下走了）。
**但实现上不需要用这个公式** —— 游戏已经把结果写进 `_cd_delta`，直接读。

### ★ 敌方监管的冷却也读得到（2026-09-22 实测）

求生者局里读对面 `ButcherUnit`（非 `MyButcherUnit`）的 `skill_mgr.skill_dict`，
闪现 `_cd_delta = 12.66`、`cd_time = 150.0`，**在实时递减**。
所以"显示监管闪现还剩几秒"这种功能在客户端侧是有数据支撑的。

（本机侧已对过账：起始 149.53 与游戏 UI 的"149"一致。敌方侧数值合理且在实时递减 ——
客户端要播放闪现特效本来就得知道对方放了技能，所以本地能正确起算。
只是**没跟对方的 UI 逐秒对过**，真要上线做"监管闪现倒计时"再核一次即可。）

**id 就是 1~8 连号，全表齐了。** 4/7/8 另有五局录像佐证（三个取值一一对应，无冲突），
5/7 另有 Python 层活体读取佐证。

⚠ **snapshot_0 记的是开局那一刻的特质。** 监管带「底牌」可以局中换特质，
换之后的值只能从 `battle_event` 流里追，或者去 Python 层读实时值。

---

## 四、Python 层：实时读特质与技能冷却

链路（静态根等通用部分见 `idv-reverse-resume/python-layer.md`）：

```
units_by_type[1] -> ButcherUnit 实例   (本机操控时类名是 "MyButcherUnit")
  support_skill_id            当前辅助特质，list
  now                         ★ 游戏内时钟(秒)，每秒 +1，比绕 room 取时间直接
  skill_mgr                   -> 技能管理器(81 条属性)
      skill_dict              -> {技能id: Skill实例}  (每个 Skill 有 223 条属性)
          _cd_delta           ★★ 剩余冷却秒数，0=可用。见下
          cd_time             冷却总长(会被天赋等改)。_cd_delta/cd_time = 进度环
          csv_cd_time         配置冷却(闪现150 / 传送100)
          game_start_cd       开局初始冷却，实测闪现是 60.0
          start_cast_time     上次释放时刻(unix 秒)
          start_frame/last_frame   释放时的游戏帧时间
          current_cast_stage  0/1/2 释放阶段
          skill_head_id       每次释放递增
          cd_timer            恒为 None，**别用**
      share_cd_skills         {id: {共享CD的id集合}}，实测 {711:{711,712}, ...}
      skill_btn_status        {按钮序号: 0/1}，释放瞬间对应键 0->1
      last_cast_skill_id      上一个释放的技能
      _has_teleport_skill     bool，有没有传送
      is_in_replay            bool，**能判断当前是不是在看回放**
      st_add_cd               **skill_mgr 上没有这个属性**，它在 Skill 对象上
```

### ★ 剩余冷却 = `skill._cd_delta`（2026-09-22 注入实测结案）

直接就是秒数，不用自己算时间差。实测闪现（`csv_cd_time=150`）：

```
t+0s    _cd_delta   0.0   -> 149.533     ← 按下的瞬间
t+2s              149.533 -> 147.516
t+4s              147.516 -> 145.517
t+6s              145.517 -> 143.499     ... 速率恒为 -1.0/秒
```

起始值 149.53 与游戏 UI 显示的"149"一致。`711`/`712` 因为在 `share_cd_skills` 里，同步变化。

**为什么以前找不到**：`_cd_delta` **不在冷却中时恒为 0**。早前"冷却正在走时对 236 条属性差分、
19 秒零变化"的结论是在没有冷却的时段测的。字段名其实一直记在本文档里，只是没认出含义。
**教训：差分之前先确认被观测的量真的处于变化状态。**

### ★ 充能型技能（2026-09-22 窥视者实测）

窥视者（辅助特质 id **6**）对应 `SkillEyeCreate` **25732** / `SkillEyeChannel` 25733 /
`SkillEyeCreate` 25734。**只有 25732 的 `_cd_delta` 是活的**，另外两个恒为 30.0，别读错对象。
⚠️ 不能靠 `is_leader_skill` 区分：25732 和 25733 **都是 True**（只有 25734 是 False），
必须按 id 直接取 25732。

```
power_num       = 3      最大充能层数        (不是当前层数!)
_cur_power_num  = 1..3   当前剩余层数
_cd_delta       = 秒      距下一层回满，每秒 -1；归零时 _cur_power_num+1 并重置为 cd_time
cd_time/csv_cd_time = 30 每层充能时间
game_start_cd   = 10     开局初始
```

三次采样实证：

```
t=157.7  _cur_power_num=1  _cd_delta= 1.33
t=192.1  _cur_power_num=2  _cd_delta=26.98   ← 回满一层, 计时重置
t=198.1  _cur_power_num=2  _cd_delta=20.93   ← 6.05 秒减 6.05, 速率恒 -1.0/秒
```

⚠️ **反面结果（别再查这几个）**：即使在充能技能上，
`power_use_cd` / `cur_power_use_cd` / `skill_cast_initial_num` / `skill_cast_max_num` /
`skill_num` **依然全是 `0`/`None`**。它们不是充能相关字段。

（`_cur_power_num` 到达 `power_num` 之后 `_cd_delta` 怎么表现，没验。）

### 已知技能 id 与冷却

| id | 技能类 | csv_cd_time | 备注 |
|---|---|---|---|
| `711` / `712` | `SkillSpellFlash` | 150.0 | 闪现（辅助特质 7），`game_start_cd=60` |
| `9742` / `9744` | — | 100.0 | 传送（辅助特质 5） |
| `1810` / `1821` / `1882` | `SkillImperSwitch*` / `SkillImperUmbSwitch*` | 30.0 | **无常**（换伞/换位） |
| `1621` | — | 17.0 | 未对上角色 |
| `1612` | — | 9.0 | 未对上角色 |
| `3630` / `3631` | `SkillDarkdetectiveCrowCreate(Channel)` | 20.0 | 某个"乌鸦"监管，角色未对上 |
| `3633` / `3635` | `SkillDarkdetectiveChangeCrow` | 55.0 | 同上，`share_cd_skills` 里与 3632/3634 共享 |
| **`25732`/`25733`/`25734`** | `SkillEyeCreate` / `SkillEyeChannel` | 30.0 | **窥视者（特质 6）**，充能型 3 层，`game_start_cd=10` |
| `2610` / `2611` / `2612` | `SkillMaryPlaceMirrorPrepare` / `SkillMaryPlaceMirror` / `SkillMaryExchange` | 0 / **15.0** / 0 | **红夫人**，放镜 `game_start_cd=8` |
| `701` `1811` `1814` `1816` `1818` `1822` `1827` `1829` `1833` `1851`~`1859` `1883` | `SkillNormal` 等 | 0 | 无冷却，普攻/子技能 |
| **`11111`** | `SkillFlywheelSprint` | **135.0** | **飞轮效应**（求生者天赋 8），`game_start_cd=50`，见下 |

### ★ 梦之女巫：本体和每个信徒的特质冷却各自独立（2026-09-22 实测，求生者视角读对面女巫）

`units_by_type[236]` = `YidhraPuppetUnit`（本局 5 个）。每个信徒有**自己的** `skill_mgr`、`skill_dict`、
`711`/`712` 闪现对象（地址各不同），`support_skill_id` 与本体相同（`[7]`）。三次采样、间隔 10.2 秒，
本体 105.40→95.23、信徒 143.03→132.87 / 132.30→122.13 / 三个没放过的 13.03→2.87，全部严格每秒 -1。
从没放过的信徒值完全相同 = 出生时一起带上的开局冷却。本体放技能时自己 `model.visible=False`，
`_current_yidhra_puppet_uid` 指向当前附身的信徒。信徒技能：`2400~2409` SkillNormal、`2421` OperatePuppet(cd 2)、
`22761/22762` 巡视者（本体是 `21761/21762`）；本体独有 `2410~2413` SkillYidhra*（`2413` PlaceMark cd 75）。
`PyGenius.h` 已把 `[236]` 纳入（不读天赋，只读特质冷却），绘制侧信徒只画特质行。采样脚本 `_scripts\cmd_yidhra.py`。

### ★ 求生者天赋的冷却：飞轮效应（2026-09-22 注入实测）

天赋落地成被动技能，被动的配表里 `active_skills` 指向一个**真正的技能对象**，
冷却就挂在那个技能对象上，读法跟监管辅助特质完全一样：

```
GK.DM.get_passive_skill_data_from_id_lv(207, 1)      # 207 = 飞轮效应的被动 id
   active_skills = (11111,)    skill_cd = 10.0  ← 这个 10 不是飞轮冷却，别被骗
unit.skill_mgr.skill_dict[11111]  SkillFlywheelSprint
   cd_time = csv_cd_time = 135.0   game_start_cd = 50.0
   _cd_delta  剩余秒，每秒 -1.0，0 = 可用       start_cast_time = 上次使用(unix 秒)
   is_leader_skill = True，也在 leader_skills 里    power_num = 0(非充能)
```

实测：使用后约 6.47 秒读到 128.52（135 − 6.47 = 128.53），之后三次采样严格每秒 -1.0。

- 同一局其余三个求生者都**没带**天赋 8，`skill_dict` 里也没有 11111 —— 所以
  **"非本机求生者的飞轮冷却能不能读到"还没验**（监管闪现那边敌方是读得到的，见上）。
- 通用推论（未逐个验）：想要某个天赋的冷却，先查 `passive_skill_data[(psv, lv)]['active_skills']`
  拿技能 id，再去 `skill_dict[id]._cd_delta` 读。psv id 见 [`genius-table.md`](genius-table.md)。

无常还有个 `unit.imper_umbrella_dis`（伞的距离，实测 84.47 → 0.0），
以及 `units_by_type[401] = ImperUmbrellaUnit`。

⚠️ **顺带发现反作弊痕迹**：监管本体上有 `anti_move_speed_cheat_idx`，每轮递增。
动移速相关的东西之前先想想这个。

### 活体天赋：属性名跟录像不一样，而且会间歇性读空

```
units_by_type[2] -> CivilianUnit (1300+ 条属性)
units_by_type[1] -> ButcherUnit
    genius_id_lv_lst    list[[天赋id, 等级], ...]   ← 注意不是录像里的 genius_id_lvs
    support_skill_id    list[id]                   ← 求生者也有这个字段(录像里却是 None)
    uid / model / position                          model+0x20 = 场景对象，用来跟绘制循环配对
```

⚠ **`genius_id_lv_lst` 经常读不出内容**，PC 侧脚本里表现成 `[]` 或"读不到"。
同一时刻隔壁的 `support_skill_id` 却每次都好。**原因未定**，下面两个推断都不要当结论。

**属性名本身是对的**（2026-09-21）。`007开源骨骼进度绘制优化` 那份注入脚本
在第 6167 / 6210 / 6540 行用的就是 `getattr(player, 'genius_id_lv_lst', [])`。
两套独立实现撞到同一个名字 → 待办 #7 的可能性 (a)「位置错了」基本可以划掉。

**更有价值的是第 6167 行所在的函数：`probe_info_readiness()`。**
他把"`genius_id_lv_lst` 非空"当成**开局就绪判据**：

```python
genius_list = getattr(player, 'genius_id_lv_lst', [])
if genius_list:
    info['talent_ready_count'] += 1
...
info['full_ready'] = info['old_timing_ready'] and info['uid_ready_count'] >= 1 \
                     and info['talent_ready_count'] >= 1
```

两条推论：

1. **作者知道它会空** —— 空不是异常，是"还没同步好"。所以别再把"读到空"当成 bug 去查。
2. **进程内确实能读到非空** —— 否则 `full_ready` 永远不成立，他整套 info 采集根本跑不起来。
   这基本排除了"这个 list 在任何时刻对任何人都是空的"。

⚠ 但**注意他只要求 `>= 1` 个玩家非空**，而且另外两处读到空时是 `if genius_list:` 静默跳过。
所以**不能推出"进程内每次每人都读得到"** —— 关于稳定性，他的代码没有提供任何证据。

**但这反过来指向一个更重要的新怀疑：问题可能出在"读取方式"而不是"读取位置"。**
他在游戏进程内、持 GIL、在 `UnitManager.tick` hook 里读；我们是跨进程 + 裸内存 +
自己复刻 CPython 3.11 的 dict 布局。这两者会在以下地方产生不同结果，见待办 #7 的 (d)。

> **已推翻 ①**：「空 = 这人已淘汰」。后来全场六个人同时为空，说不通。
>
> **已推翻 ②**：「这个 list 会被反复重建，采样撞在空窗里」。这条是**在错误的测量上编出来的** ——
> `pyw.list_items()` 在**读失败**和**真的空**两种情况下都返回 `[]`：
> ```python
> b = self.m.get(L, 0x20)
> if not b: return []          # 读失败
> if not (0 <= n < 100000) or not it: return []   # 也返回 []
> ```
> 所以"全场一起空"这个观察根本立不住，它可能全是读失败。**别拿 `list_items` 的返回值
> 判断"列表是不是空的"**，要自己读 `ob_size` 才算数。

**当前最合理的假设（还没验）**：冷热页差异。`support_skill_id` 是界面一直在用的热数据，
只有一个小 list 装一个小整数；`genius_id_lv_lst` 是十几个嵌套 list，要碰的页多得多，
而且开局读一次之后再没人碰，是冷页 —— **内存压力下优先被换进 zram**。
这跟 skill 里那条"内存压力会让键名先读不出来，值却好好的"是同一类现象。

**怎么定论**：`genius_probe.py`（分步报告，不吞错误）会把每一步分开说：
值指针是否有效 / 对象头读不到 / `ob_size` 真的是 0 / 元素数组读不到 / 内层几好几坏，
并在每轮打印 `VmRSS`、`VmSwap`。**如果是冷页换出，`ob_size` 会读不到而不是读成 0，
而且失败率会跟 `VmSwap` 正相关。** 下次在对局里跑一次就知道。

这个结论会影响实现：如果是页换出，C++ 侧走内核驱动（微秒级、机制不同，
`PyProgress.h` 一直很稳）未必会踩到，锁存可能根本用不上。

> **锁存本身有个反噬**：它会把**第一次**读到的非空值冻结下来，
> 万一那次读到的是垃圾，就把"偶尔错"变成了"永久错"。
> 所以 `PyGenius.h` 的 `读天赋()` 加了准入校验：条目必须形如 `[id, 等级]`、
> `id` 在 1~64、等级 1~3，且成功解析的条目 **≥ 8 条**，不满足就当读失败、**绝不锁存**。
> 加锁存类的缓存时都该配一个这样的准入门槛。
>
> 阈值数的是**单个玩家**天赋表里的条目数，不是场上玩家数 ——
> 一个人的表实测有 12~18 条（见过最少的 12 条）。取 8 是给"内层个别条目所在页
> 读不到"留余量，同时离随机垃圾能凑出的条数足够远。

根因没追到底。**当前是靠锁存绕过去的，不是解决了** ——
天赋一局之内不会变，读到一次非空就按 `uid` 记住，之后读空/读失败都沿用记忆值。
用 `uid` 当键而不是 `model`，因为 `model` 会短暂为空。已实现在 `PyGenius.h`。

**记忆的清理时机：`unit_mgr` 地址变了才清。**
`uid` 每局都从 `1000001` 重新开始，不清的话下一局会套用上一局同号玩家的天赋 ——
那是实打实的错误信息，比"没有信息"糟得多。而 `unit_mgr` 实例每局重新分配
（见 `python-layer.md` 的生命周期），地址一变就是换局了。

> 曾经用的是"连续 8 轮失败(约 4 秒)就清"。**那个判据是错的**：对局中途链路短暂中断
> （内存压力把 CPython 堆压进 zram）也会走到那条路，结果是天赋行白白消失。
> 换成比地址之后，中途中断不再影响记忆。注意比较只在**拿到有效新地址**时做，
> `unit_mgr` 读不到时什么都不动。

**找过的替代来源，已排除**：`skill_mgr.passive_skills`(set) 实测监管只有一个元素 `{1611}`，
而 1611 正是 `skill_dict` 里那个 `csv_cd_time=0` 的技能 —— 那是**角色自带的被动技能**，
不是天赋（监管带四个天赋，这里却只有一项）。`leader_skills` / `relative_skill_set`
也是技能 id 的集合，同理。**别再往 skill_mgr 里找天赋。**

唯一还没试的方向：录像里 `set_attribute` 带的 `<uid>_psv_sid_<n>` 属性来源串，
说明天赋落地后变成了属性修正项，挂在某个属性/buff 管理器上。但那是"效果"不是"配装"，
要反推回天赋 id 未必划算 —— 锁存方案已经够用，优先级低。

> 读 Python `set` 要自己解：CPython 3.11 `PySetObject` 是
> `+0x18 used、+0x20 mask、+0x28 table`，表项 `setentry{key, hash}` 16 字节，
> 槽位数 = `mask+1`，空槽 key 为 NULL。小集合用内嵌的 `smalltable(+0x40)`，
> 此时 table 指针就指向它，照读即可。**元素对象散落在别处，必须批量预取**，
> 否则全部读不到。已实现在 `py_named.py` 的 `解集合()`。

### ~~剩余冷却还没找到~~ —— **2026-09-22 已结案：`skill._cd_delta`**

答案和实测数据见第四节。下面保留当时的错误推理，用来记教训：

> **当时"已排除"的结论，大半是错的**：
> - ~~"技能对象里没有任何时间戳字段"~~ —— 错。223 条属性里有 `start_cast_time`、
>   `start_frame`、`last_frame`（都是浮点时间戳）。`cd_timer` 是 `None` 不代表别的时间字段不存在。
>   ⚠️ **`cd_begin` 不是时间戳，是个方法**（`<bound method SkillBase.cd_begin_normal>`），
>   我一度把它写成时间戳字段，2026-09-22 实测更正
> - ~~"冷却正在走时对 236 条属性差分，19 秒零变化"~~ —— 这个观测本身不成立。
>   `_cd_delta` 每秒减 1，不可能 19 秒不动。**当时多半根本不在冷却中**
> - `last_flash_time` / `last_flash_end_time` / `last_cd_delta` 恒为 0 —— 这条仍然成立
> - `flash_effect_handler` 变成 int 能当"刚用过"信号 —— 仍然成立
> - ~~"界面每帧用服务器帧号现算，不落成属性"~~ —— 错，落成 `_cd_delta` 了
>
> **教训**：差分之前**先确认被观测的量真的处于变化状态**。
> 拿一个静止的量做差分，只会得到"这里什么都没有"的假结论，而且很难自己发现。
> 正确做法是先制造一个已知的变化（按下技能），再看谁跟着动。

已查清的三个 dict：`skill_btn_status` = `{按钮序号: 0/1}`（释放瞬间对应键 0→1）；
`share_cd_skills` = `{id: {共享CD的id集合}}`；`st_add_cd` **不在 `skill_mgr` 上**，在 Skill 对象上。

---

## 五、下次测试怎么安排（用户定的）

之前几轮效率低，是因为在**看回放**且反复拖进度条：

- 拖进度条会让对局重新初始化，**实例地址和 dict 条数都会变**（964 ↔ 965 ↔ 968）
- 于是 entry 序号在两次采样之间就漂了，按序号追的差分全作废

**正确做法：用户自己操控监管，进一个时长无限的局，用一次技能，保证至少 150 秒窗口。**
这样实例稳定、冷却确实在走，差分才有意义。

---

## 六、工具与性能（`逆向存档\_scripts\`）

| 脚本 | 用途 |
|---|---|
| `replay_genius.py` | 录像解析（受限 pickle + 天赋/特质表） |
| `py_named.py` | **主力**。按名字读某类单位的属性；`--into <属性>` 下钻到子对象；不给筛选条件就列全部 |
| `py_skills.py` | 遍历 `skill_mgr.skill_dict` 每个技能的冷却字段；`--id` 指定技能，`--all` 全列，`--tick` 前后差分 |
| `py_tick.py` | 找"正在被重新赋值"的属性（两阶段，见下） |
| `py_valscan.py` | 把全部数值属性解出来按值域筛（`--ts` 只看时间戳量级、`--near X`） |
| `py_entry.py` | 按 entry 序号直读，跳过键名全扫。**序号会漂，只适合同一实例内的即时复查** |

### 两阶段差分：别一条条解对象

直接把每条属性都解出来要抓上千个散落小对象，PC 侧一次 adb 往返 ~30ms，
全扫一遍 **25 秒**，慢到实例都换了。但 dict 的 entries 是**一整块连续内存**
（`nentries × 16` 字节），一次读完只要 **0.9 秒**。属性每被重新赋值就换一个新值对象，所以：

```
阶段一  只读 entries 块，比两次的**值指针** -> 圈出正在被重新赋值的少数条目
阶段二  只对这几条解值、再采一次算差值   -> 谁在按秒递减一目了然
```

### 三个反复踩到的坑

1. **序号会漂，名字不会。** entries 是追加写的，对局中实例会不断被加新属性
   （964→968），拖进度条更会整个换实例。**差分必须按名字比，不能按序号比。**
   `py_entry.py` 那种按序号直读只适合同一实例内的即时复查。
2. **内存压力会让键名先读不出来。** `VmSwap` ≥ `VmRSS` 时，值还读得到但键字符串页
   已经换出，表现是 py_chain 报「这个类没有属性 X」、`类名 = ?`、属性只捞回一半
   （435/968）。**这不是偏移失效**，清后台就好。清完之后同一个全扫从 24 秒降到 4.7 秒。
   诊断：`su -c 'cat /proc/<pid>/status'` 看 VmRSS/VmSwap。
3. **`$PID` 在 PowerShell 里是只读内置变量**，赋值失败后打印出来的是 PowerShell 自己的
   进程号，会被误读成"游戏重启了"。用别的变量名。另外引号里的 `|` 会被当管道，
   `grep -E "a|b"` 要用单引号包。

### 其它

- `devread` 偶发 `PermissionError: pm.bin 被占用`（上一轮句柄没释放），重试即可
- 录像文件属 `u0_a310` 且目录是 `drwxrws---`，shell 用户直接读不到，
  要先 `su -c cp` 到 `/data/local/tmp` 再 `adb pull`
- 后续快照 `_1..N` 里 `battle_event` 是事件流，每条是 `[时间戳, {et, data, retry_times}]`。
  `et=10999` 是 RPC（`channel/id/func/args/kwargs`），能看到
  `set_attribute` 携带的 `<uid>_psv_sid_<n>` / `<uid>_buff_sid_<n>`（被动/buff 来源 id）。
  **后续快照里没有 `genius` 字段**，天赋只在 `_0`。

---

## 六点五、道具真假之分 —— **2026-09-22 结案：`+0x6D & 0x40`**

> **★ 2026-10-15 补：道具的三类数据源（probe2 进程内实测）**
> - **在求生身上**：`unit.item_lst[i]` —— 身份看**类名**(ItemInjector镇静剂/ItemBird/ItemFragrance香水/ItemMail邮件…)，`item_id`/`item_name` 候选名**解不出**(恒 None)；`_remain_use_times`/`_init_use_times` 准、`_b_in_use`。
> - **箱子开出掉地上的松散道具**：❌ **没有任何 Python 实体** —— 地上放一根镇静剂实测，`units_by_type` 没冒新 key、`all_units` 无 Item*、无管理器/全局持有它，掉道具的求生者 uid 整个从对象图消失。**所以掉地道具只能走场景层**(就是本节 `+0x6D & 0x40`)，Python 层查不到，别再找。
> - **宝箱本体**：`units_by_type[5] = BoxUnit`(一局 8 个)。字段：`opener_uid`/`luck_opener_uid`(谁开的，None=没开)、`state`、`box_cd_time`/`box_cd_total_time=180`(开过的刷新冷却)、`position`(可做宝箱ESP)。
> - **求生者开箱交互**(CivilianUnit 上)：`box_uid`(正在开哪个箱)、**`lucky_last_pick_item_detail=(item_id, 数量)`**(最后拾取的道具 id，如 (51,1)/(66,1))、`lucky_first_pick_item`、`carry_unit_uid`/`carrying_offerings`。
> 若辰的手持物候选名(`handheld_id_lv/held_item_id/hand_item_id/carry_item_id`)见 `idv-reverse-resume/ruochen-teardown.md`。
>
> **★ 2026-10-15 调查：「已捡走的道具残留幽灵」过滤——`+0x6D&0x40` 对这种情况失效，且场景对象本体找不到判据（未解，下次下钻子对象）。**
> 现象：道具被捡走后在原地留一个幽灵模型，仍在对象数组、仍被绘制。注意这跟六点五原本的「用完后的废弃模型」**是两种东西**，`+0x6D&0x40` 只管后者。
> 实测(内核驱动 dump 场景对象前 0x300 字节，draw_Gui 道具绘制块临时加的 prop_dump，已删)：
> - ⚠️ **必须同类型比**。先拿魔术棒(真) vs 护肘(幽灵)比，`+0x6F`(10/00)/`+0xD7`(01/00)/`+0xD8~E7块`(有值/全0)看着能分——**全是假象，是"魔术棒 vs 护肘"的类型差异**。
> - 换**同类型护肘的真 vs 幽灵**(方法论§3.2 最强差分)：`+0x6F`/`+0xD7` **两边都=00**(推翻)；`+0xD8块`更反过来(真=全0、幽灵有值)——因为那个幽灵地址 `720ACE23D0` 是**之前魔术棒复用**的，块里是陈旧数据。
> - **结论：场景对象本体没有任何稳定字节能区分同类型的真/已捡幽灵。** 64 处稳定差异**全是子对象指针**(+0x20/+0x28/+0x30/+0x78/+0xF8/+0x110/+0x1C8…)+ 陈旧数据；连 config 的"存在指针"`+0x30` 两边都非空。这是主 SKILL §3.3 说的"区分在内存本体里不存在"。
> - **下次从这做**：跟着差异子对象指针**下钻一层**——尤其 `+0x28`(坐标子对象)、`+0x30`(存在指针指向的对象)、`+0x20`，dump 真/幽灵各自的子对象再 diff，判据很可能在子对象里(真的指向 live、幽灵指向陈旧/失效)。或确认是纯逻辑层(可交互注册，但监管端未必下发)。
> - ⚠️ **读场景字节只走内核驱动**(draw_Gui 里 `vm_readv`)。本次就是在道具绘制块临时加 dump 做的，**别用 /proc 跨进程**(见 idv-reverse-resume 顶部反作弊警告)。
> - 另一条线索：用户实测「魔术棒捡起来后幽灵被正常过滤掉了、护肘没有」——说明不同道具清理行为不同，值得留意。

**问题**：道具用完后，会在**最后使用的地点**留下一个废弃模型，仍在对象数组里、仍被绘制循环
捕获，叠加层照样把它画出来。

### ★ 判据

```cpp
是真实道具(obj)  =>  (getByte(obj + 0x6D) & 0x40) != 0
```

**同局同时刻的对照**（注入取 `item_lst[i].model` → root 读 `+0x20` 拿场景对象，2026-09-22）：

| 字段 | 手持真道具 ×5 | **掉地上的真道具** | 废弃模型 |
|---|---|---|---|
| | 监管ItemBase/盲杖/铲子/电线×2 | `ydy_e_tang_football.gim` | `h55_pendant_patrol.gim` |
| **`+0x6D`** | **`0x50`**（=`0x40\|0x10`） | **`0x50`** ✅ | **`0x10`** ← **只差 `0x40` 位** |
| `+0x73` 活跃位 | 1 | 1 | **1** ← 分不开 |
| `+0x240` | 2 | 2 | **2** ← 分不开 |
| `+0x1a0` | 0 | 0 | `0x162A1629`（垃圾） |
| `+0x298` / `+0xa8` | 相同 | 相同 | 相同 ← 分不开 |

**手持和掉地上的真道具 `+0x6D` 完全一样，都是 `0x50`**（掉地上那个已验类名+坐标：
高度 1.36 贴地）。⚠️ 我曾推测"`0x10` 是跟玩家绑定位，掉地上应该丢掉" —— **推测是错的，
`0x10` 照样保留**，真正的区别只在 `0x40` 位。结论对，过程错，别照抄那个推理。

### 被证伪的东西（别再用）

- ~~`+0x1a0 != 500`（旧判据 B）~~ —— **跨样本不成立**。旧记录说废弃的是 `500`，
  这次废弃的却是垃圾值 `0x162A1629`，而 5 个真道具全是 `0`。当初那个 500 是巧合。
- ~~`+0x73`（活跃位）能挡住废弃模型~~ —— **不能**。废弃模型的 `+0x73` 照样是 `1`。
  这同时说明"废弃 = 不渲染 = visible false"这个直觉**是错的**。
- ~~`+0x240 == 2`~~ —— 真废都是 2，从来挡不住（本来就知道，这次再次确认）。

### Python 侧的旁证（较弱）

废弃模型在 Python 侧**没有宿主**：把该局**全部 199 个单位**的 `model+0x20` 读出来
（199/199 读取有效，全带 `0xB4` 标记、无 0 值）逐一比对，没有任何一个指向它。
真实道具则都挂在 `unit.item_lst[i].model` 上。

⚠️ 但**别把"无宿主"当判据**，有个对照没做：**掉在地上的真实道具是否有宿主未验证**
（那局 5 个道具全在手上）。`+0x6D & 0x40` 不依赖这个，优先用它。

### 还没验的边界

- 木偶师人偶 `+0x6D = 0x90`（`0x80|0x10`）同样不带 `0x40`，会被这条判据滤掉。
  人偶走的是角色分支不是道具分支，**但改代码前确认一下 `阵营` 到底怎么分的**。
- 只验过 `h55_pendant_patrol`（巡视者）一种废弃模型。别的道具用完的残骸没单独验，
  但机制应当相同。

### 对象生命周期：快照和读指针必须压在同一次操作里

实测同一轮内：废弃巡视者的 `+0x28`（坐标子对象）从有效指针变成 `0`（对象正在拆除）；
之前读到的铲子对象几分钟后**全字段归零**（已释放/复用）。
**我隔了一两分钟再读，差点据此得出错误结论。** 取对象地址和读它的字段要连在一起做。

工具：`prop_check.py`（按 `+0x6D` 分组列出 `+0x240==2` 的对象并带类名）、
`objdiff.py`（两个对象原始字节 diff + 已知语义字段表 + 类名）。
本轮用的是注入取 `item_lst[i].model` 的 Python 对象地址 → root 读 `+0x20` 拿场景对象 →
逐字段对照，流程记在 `idv-reverse-resume/injection.md`。

## 六点七、★ 第二个天赋来源：`GK.g_avatar.final_genius_dict`（2026-09-23 注入实测）

**准备阶段读不到天赋这个结论是错的**（旧说法：`units_by_type` 里没有玩家单位 ⇒ 读不到）。
正确的推理是用户给的：**界面上能看到队友带什么，数据就一定在客户端内存里**，只是不在 unit 上。

```
GK.g_avatar            类 Avatar，账号级对象，不随对局重建
  final_genius_dict    {unique_id(str): [终端天赋id, ...]}   ← 就是界面显示的那两个大天赋
```

自定义房间准备阶段实测（用户报：三个队友都是"搏命心脏"）：

```
'1001' -> [16, 24]   '1002' -> [16, 24]   '1003' -> [16, 24]
'1000' -> []         '6734a84949508640296455e0' -> [16, 32]   ← 自己(账号 guuid)
```

`16 = 回光返照(俗称心脏)`、`24 = 化险为夷(俗称搏命)`，与界面逐一对上；自己是 `[16,32]`(回光返照+膝跳反射)。

- **键是 `unique_id`**：机器人是 `1000/1001/1002/1003` 这种小整数字符串，真人是账号级十六进制串。
  这同时印证了待办 #9 那个"`unique_id` 可能是真人/AI 判据"的猜测。
- **值只有终端天赋**（4 个大天赋那一档），不是完整的 `genius_id_lv_lst`。
- `'1000' -> []` 含义未定（可能是监管位或空位）。

### ★★ 花名册：`GK.g_avatar.player_data_list`（局外局内都在，2026-09-23 两边实测）

比 `final_genius_dict` 更完整，一个结构给出全房间每个人：

```
[{role_type, status, player_name, eid, pid, bot, cloth_id, final_genius, is_ready}, ...]
   role_type   1=监管 2=求生者
   pid         角色 id(cloth_id ≈ pid*100+款式，实测 14/1401、25/2501、32/3201、96/9601 全对上)
   eid         人机是 int(1000~1003)，真人是 ObjectId(账号)
   final_genius[终端天赋id, ...]   监管那条是 None(监管天赋不放这里)
   bot         人机标记
本人那条额外有：uid('<账号uid_A>' 账号字符串)、support_skill_id([4] = 辅助特质!)、
                cloth_dyeing/face_info/article_setting 等一堆外观数据
```

准备阶段同样的内容还挂在 UI 上：`GK.g_ui_mgr.ui_dict['UIRoomWait'].eid_2_player_info` /
`.player_others` / `.uid2pid` / `.uid2pos` / `.uid_2_eid`。**但 UIRoomWait 进局就销毁**
（实测局内 `ui_dict` 只剩 2 个键），所以**统一用 `g_avatar.player_data_list`**，局内局外都能读。

### ★★ 哪些是实时的，哪些是进房快照（2026-09-23 前后差分实测，**这条最重要**）

做法：准备界面抓一份完整快照 → 改天赋 → 再抓一份 → 1017 行逐行 diff。结果：

| 结构 | 实时性 | 内容 |
|---|---|---|
| **`g_avatar.final_genius_dict`** | ✅ **实时，两个视角都是** | `{str(eid): [终端天赋]}`，改天赋立刻变（`[16,32]`→`[8,24]`）。**2026-09-24 监管视角**：对面真人求生者 60 秒换 16 次，每次都跟着变 |
| **`UIRoomWait.c_skill_data`** | ✅ 实时，**但只在我是求生者时有内容** | `[[eid, 名字, 角色pid, 状态, [终端天赋]], ...]`，只装本阵营队友。**2026-09-24 实测：我是监管时是空列表 `[]`** |
| `g_avatar.genius_data_b/c_active_page` | ✅ 实时 | 只有**自己**的，完整带等级 |
| `g_avatar.tmp_geinus_data` | ✅ 实时 | 编辑天赋时才出现（游戏自己把 genius 拼错成 geinus） |
| **`player_data_list` / `eid_2_player_info`** | ❌ **进房快照** | 改天赋/改特质后**纹丝不动** |

**我在这里栽过一次**：第一版把大天赋接到了 `player_data_list.final_genius`，结果叠加层显示的是进房时的旧值
（用户已改成移形，面板还写巡视者）。**两份数据内容长得一模一样，只有做前后差分才能分辨谁是实时的。**

⚠️ **监管特质目前只有快照值**：`support_skill_id` 只在 `player_data_list` 里，差分那轮用户是求生者，
所以监管侧还没验过有没有实时源（见待办 #12）。

⚠️ **快照的另一个坑（2026-09-24）**：回到大厅后 `player_data_list` / `final_genius_dict` **仍是上一局的数据**，
进新房间才立刻换成新房间的。所以局外显示必须以 `UIRoomWait` 面板存在为前提，只判"不在局内"会显示旧数据。

### ★★ 准备阶段数据源全表（2026-09-24，两个视角各实测）

| 来源 | 我是**求生者** | 我是**监管** | 实时？ |
|---|---|---|---|
| `UIRoomWait.role` | `2` | `1` | —— 本机阵营的判据 |
| `UIRoomWait.uid2pos` / `uid2pid` | 4 个求生者（含自己）`{eid: 座位1..4}` / `{eid: pid}` | 4 个求生者 | 进房定 |
| `UIRoomWait.b_uid2pos` / `b_uid2pid` | 监管 `{eid: 0}` / `{eid: pid}` | 自己 | 进房定 |
| `UIRoomWait.c_skill_data` | 队友+自己的终端天赋 | **`[]`** | 实时 |
| `UIRoomWait.eid_2_player_info` | 全房间 | 全房间 | ❌ 快照（只有 status 变） |
| `g_avatar.player_data_list` | 全房间 | 全房间 | ❌ 快照；大厅里是上一局 |
| **`g_avatar.final_genius_dict`** | 全部求生者 | 全部求生者（自己那条 `[]`/`None`） | ✅ **实时** |

- **`uid2pos` 的键、`eid_2_player_info` 的键、`c_skill_data` 的 `row[0]` 是同一个 Python 对象**（`is` 相同，人机 int 和真人 ObjectId 都是）。
- **`final_genius_dict` 的键是字符串**：人机 = `str(int eid)`，真人 = ObjectId 的 24 位小写 hex。
  **ObjectId 内存布局**（进程内 + PC 侧读内存双重验证）：`basicsize=24`、唯一槽 `__id`、无 `__dict__`
  → 对象 `+0x10` 是 bytes 对象 → bytes `+0x10` = 长度 12、`+0x20` 起 12 字节原始内容，`.hex()` 与 `str(oid)` 一致。
- 若辰拆解说的 `waiting_for_process` / `player_tips.data` 这一版**不存在或为 None**。
- 已知 pid：1 厂长、3 幸运儿、78 先知、94 邮差（用户在准备界面口头对照）。pid→名字的配表没找到，
  `GK.DM` 里只有 TID 文本 id（`fan_meeting_pid_config` 有 pid→cloth_id/unit_type）。

### ★ 准备阶段"我是监管时显示四个求生者天赋"—— 2026-09-24 落地过程（按版本，**别重蹈**）

| 产物 | 数据源 | 结果 | 教训 |
|---|---|---|---|
| (旧) | `c_skill_data` + 花名册特质 | 不显示天赋、特质是上一局的 | `try_refresh()` 假设局外 `unit_mgr` 不存在；实际在，`count==0` 就 `return false`、**缓冲不翻转**，绘制侧一直读上一局 |
| `nmreqobt.sh` | `c_skill_data` | "求生者天赋0条" | 我是监管时 `c_skill_data` 为空 —— **验证全在求生者视角做的** |
| `jvbpeldh.sh` | `eid_2_player_info` | 能显示但滞后 | 快照。**60 秒差分**（`prepdiff60.ps1`）才看出只有 `final_genius_dict` 在变 |
| `leaodntc.sh` | `final_genius_dict`，每轮从 `uid2pos` 现拼键 | 换几次后"0条" | 内存压力（VmSwap 1.1G > VmRSS 675M，PC 侧 eid 对象读不到）：eid 对象是进房时的冷页 |
| `oisdbrwc.sh` | 同上 + **每房间缓存座位→键**、缓存键对象指针、读不到沿用 | "双弹飞轮"只显示"双弹" | 显示侧 BUG，见下 |
| **`rduvwfos.sh`** | 同上 | 待上机（编译成功，推送时手机断开，**未推送**） | `GeniusLine` 是**前/飞轮/后三段**，准备阶段那行只拼了 `pre`+`post`，飞轮(8)永远丢 |

⚠️ 关于 `leaodntc.sh` 的"内存压力"结论：证据是 VmSwap + PC 侧读不到 eid 对象页（devread 拒读非常驻页，本身不算硬证据）。
**`oisdbrwc.sh` 之后没再报"0条"**，与该结论一致，但没做严格对照。
⚠️ 动态字符串**不能传给 `PyCore::find_key` / `resolve_index`**：它们的驻留缓存 `remember_interned()` 保存的是 `name` 指针，
只能传字符串常量；传栈缓冲会留下悬空指针并占满 32 个槽。按动态键查字典要自己遍历 + `str_equals`。
⚠️ 复用 `genius_segments()` 这类格式化函数前，先看它的**完整输出结构**（这次漏了中间段）。

工具（`_scripts\`）：`prepdiff60.ps1`+`cmd_prepdiff.py`+`prepdiff.py`（准备阶段 N 秒差分：候选源天赋时间线 +
`UIRoomWait`/`g_avatar` 全属性哈希差分）、`fgd_check.ps1`+`cmd_fgd.py`+`fgd_mem.py`（读取失败时：进程内 dump +
PC 侧按 C++ 读法逐步复查）、`cmd_seat.py`/`cmd_seat2.py`（座位配对与对象同一性）、`cmd_oid.py`（ObjectId 布局）。
**这类探针由用户自己在合适时机跑**，我只写脚本、给命令。

### 局内验证结果（2026-09-23，监管视角，四个人机求生者）

`final_genius_dict` 局内**仍然有效**，且与逐单位读的 `genius_id_lv_lst` 终端**完全吻合**：

| 单位 | `unique_id` | `genius_id_lv_lst` 里的终端 | `final_genius_dict` |
|---|---|---|---|
| CivilianUnit uid=1000001 | `1000` | 16、32 | `[16, 32]` ✓ |
| uid=1000002/3/4 | `1001/1002/1003` | 16、24 | `[16, 24]` ✓ |

**⚠️ 配对要分两种人**（这是唯一的坑）：

```
人机：unit.unique_id 是 int(1000~1003)  ==  eid(int)                → 直接对
真人：unit.unique_id 是账号字符串('<账号uid_A>')，而 final_genius_dict 的键是
      ObjectId 的十六进制串('6734a84949508640296455e0') —— **对不上**！
      要用 player_data_list 里那条同时带 uid 和 eid 的记录做桥，按 uid 字符串匹配。
      单位侧另有 unit.avatar_id / unit.params['entity_id'] 就是 ObjectId 本体，
      但那是 Python 对象，C++ 侧要比就得解它的内部字节，不如比字符串。
```

⚠️ **只在"本人是真人 + 四个人机"的局里验过**。真人求生者那条记录里有没有 `uid` 字段、
真人的 `unique_id` 是不是也是账号字符串，**都没验**（下次排到真人局跑一次 `cmd_ingame_genius.py`）。

### 这条路的价值

`final_genius_dict` / `player_data_list` 挂在**账号级对象**上、结构浅（一层 dict/list + 短 list），
而 `genius_id_lv_lst` 是十几个嵌套 list 的冷页，正是待办 #7 那个"间歇读不出"的根源。
**大天赋改走这条，读取量和失败率都会明显下降**，增量累积那套逻辑只需留给非终端天赋。
`player_data_list` 还顺带给出 `pid`(角色)、`player_name`、`bot` —— 人机判据也一并解决了（待办 #9）。

同族属性（都是**自己的**配装，与队友无关，别搞混）：`pid_to_genius`(角色 pid → 天赋页 id)、
`_pid_genius`/`pid_genius_mb_carnival`(每页完整内容)、`genius_data_b/c_active_page`(当前监管/求生页)。

### 局外的辅助特质：`player_data_list` 本人那条的 `support_skill_id`

准备阶段没有 unit，所以 `unit.support_skill_id` 读不到；**账号侧那条记录里有**：实测 `[4]`（巡视者），
与用户当时的选择一致。监管自己的天赋则在 `GK.g_avatar.genius_data_b_active_page`
（b=butcher，c=civilian），格式是 `{分支: {天赋id: 等级}}`，比 `final_genius` 完整（带等级、含非终端）。
实测监管页终端是 24(挽留)+32(张狂)。

⚠️ 找它时绕过弯路：`g_avatar` 上按 `support/skill/leader/trait` 关键字搜过两轮（393 个对象）都是空的，
因为它藏在 `player_data_list` 的**元素**里，不是属性名。**搜不到时要换成搜"容器里的元素"**。

工具（`_scripts\`）：`cmd_prepgenius.py`(按名字找)、`cmd_prepgenius2.py`(三层广度搜索，342 对象/48ms)、
`cmd_avatar.py`/`cmd_avatar2.py`(定点 dump)、`cmd_support.py`/`cmd_support2.py`(宽搜，748 对象/47ms)、
`cmd_roomwait.py`/`cmd_roster.py`(准备界面花名册)、`cmd_ingame_genius.py`(局内配对验证)、
`cmd_uidmap.py`(找 uid↔ObjectId 映射，1564 对象/276ms)。

**方法论：不猜字段名，穷举后扫关键字。** 按 `room`/`match`/`phase`/`support` 猜字段名两轮一无所获；
改成"把对象图广度遍历一遍，凡是名字命中关键字的都打出来"立刻命中天赋来源。
遍历上千个对象在进程内也只要几百毫秒，而 PC 侧同样的活要几百秒 —— 这类搜索只能走注入。

## 六点八、2026-09-23 的三条相关变化

1. **源码标识符已改成英文**：`天赋` → `PyGenius`（namespace）、`查名` → `find_key`、
   `校准序号` → `resolve_index` 等。本文件里提到的中文函数名按此对应，grep 时用英文名。
2. **`PyGenius.h` 不再写死模块偏移**：sys.modules 和 int/float/dict/True/False 由新增的
   `PyRoot.h` 在运行时找出（读 so 的 ELF 段表定位 `.PyRuntime` 段，槽 = 段起点 + 0xE9B0）。
   热更后这些数不用再改，面板上 `Py根:` 那一行显示它的状态。
3. **字典查找快了一个数量级**：entries 整块读 + 缓存驻留的键对象地址，全扫从几千次驱动读降到 1 次，
   命中缓存的校验从 3 次降到 1 次。两个假设都有自动回退，最坏只是变慢、不会读错。
   ⚠️ **PC 侧脚本没有这套优化**：`pyw.dget` 每个键都要单独 fetch（约 0.4 秒），
   所以"遍历所有单位读某个属性"在 PC 侧要几百秒，**这类活必须走注入**（进程内 10~30ms）。
   命令脚本里**不能 sleep**（在游戏主线程 exec，会卡住游戏），采样序列由 PC 侧连续投递；
   游戏内嵌的 CPython **没有 ctypes**，所以脚本里读不了场景侧内存。

## 六点九、治疗 / 自愈、动画、道具次数（2026-09-24 注入实测，训练局）

### 治疗 / 自愈（求生者类才有，`MyButcherUnit` 上没有）

| 字段 | 实测含义 |
|---|---|
| `cured_process_client` | 治疗进度 **0~100**（若辰文档写 0~1 是错的），int/float 都会出现 |
| `cured_speed_client` | 每秒增量。站立打针 18.7→17.3→16.7→16.0→14.7（逐针递减），倒地自愈 4.67 |
| `cured_uid` | 被治疗者 uid；== 自身 uid 即自愈（这局只见过自愈） |
| `debug_record_cured_info` | `(时间戳, [治疗者uid...], 进度, 速度, 上限)`；**上限站立 100、倒地 60**（第二次倒地后进度停在 59.99） |

实现规则：① **显示值 = 进度 / 上限**；② 进度**会残留**（打完停在 99.98 直到下次开始），"正在治疗"要看
**治疗者列表非空**，不能看进度 > 0。**缺样本**：被队友治疗（`cured_uid` / 治疗者列表的取值没见过）。
顺带：`floor_blood` 倒地后 100→83.2→76.1，疑似倒地放血条，未验。

### 监管当前动作

`unit.state/action/action_id` 和 `unit.combat_unit`（50 条属性）上**都没有**若辰说的动作字段。
可用的是 **`unit.animation_parameter[0]`**（当前动画名）+ `skill_mgr.last_cast_skill_id`：
无常一刀 = `happy_umb_attack_1_b`(1851) → `happy_umb_attack_show_b`(1852) → `happy_umb_attack_1_end_b`(1853/1857)，
切形态 `changover_whitetoblack_1_2_b`(1882)。求生者：`repair_3/4` 修机、`inject`/`inject_plus` 打针、`idle_2_xl`。
2 秒采样抓不到时序，做自动飞轮要逐帧另测。工具 `_scripts\cmd_heal.py`（单次采样，PC 侧循环投递）。

### 道具次数

`item_lst[i]._remain_use_times` / `_init_use_times` 可用（橄榄球 `ItemParkour`、香水 `ItemFragrance` 都是 3/3）；
电线 `ItemWire` 的进度在 `charge_process`。`_remain_lifespan`/`_init_lifespan` 这几个都是 0，含义未知。

### 若辰的模型变体 / 身份字段

普通对局单位上：`ext_model`/`model_in_scene`/`clone_model`/`server_model` **存在但为 None**；
`interactive_model`/`ref_model`/`world_model`/`role_model`/`avatar_model` 不存在。
`components`/`identity_id`/`camp*`/`copy_uid`/`owner_uid`/`mirror_uid`/`cache_puppet_uid` **全不存在** —— 是身份局专用。

## 六点十、监管全天赋树：画进叠加层（2026-10-19，probe2 实测 + 落地）

目标：叠加层里画出游戏「内在人格脉络」那棵径向树(监管全树，不止 4 终端)。配套 `idv-reverse-resume` 的 `GeniusTree.h`/`DrawGeniusTree`。

### 1. 默认天赋集落在 `genius_id_lv_lst` 本身（用户补充，已坐实）
- **监管可带空天赋，系统自动补一套默认**。默认集**直接填进 `unit.genius_id_lv_lst`**，不在别处。
- 叠加层 `PyGenius.h::read_genius` 读的就是这一个字段、**没有别的"默认"兜底源**——它能读到默认，纯粹因为默认就在这个 list 里。
- **第一次 probe2 读到 `genius_id_lv_lst` = 0 条，不是"训练房没天赋"**，是那条**间歇读空**(列表那刻没同步/冷页，见待办 #7)。同一局第二次读就是完整 18 条。探针读的字段一直对。
- 账号级 `g_avatar.genius_data_b_active_page`(`{分支:{id:等级}}`) 与单位 `genius_id_lv_lst` 两源一致；但**空天赋时 account 页会空**(它只反映你自己配的)，**要含默认认 `genius_id_lv_lst`**。

### 2. ★ 全树数据叠加层早就在手：`Info.genius_levels[1..40]`
`read_genius` 把 `genius_id_lv_lst` **全部条目**按 uid 增量累积进 `mem.levels[1..40]`，`collect_type` 再 memcpy 进 `Info.genius_levels[41]`。
现在只把 4 个终端(`genius_bits`)拿去显示，但**全树(每个 id 的等级)一直都在 Info 里**。所以画全树 = **纯显示、零新增读取/偏移**，`PyGenius::lookup()` 返回的 Info 直接用。

### 3. 监管全 40 节点拓扑（`cmd_genius_topo.py` dump，配表 `GK.DM.butcher_genius`）
- **4 分支根**(layer1,无父)：1 / 9 / 17 / 25。**同构、偏移 8**。
- 每支：`根 →(2.1/2.2/2.3)→(3.1/3.2/3.3)→终端(4.1)`。**终端走** `根→2.2节点→3.3节点→终端`(如 1→3→5→8★)；2.1 节点带两个 3.1/3.2 死端(无终端)。
- **终端 8/16/24/32**；父依次 `((5,3))/((13,3))/((21,3))/((29,3))`。
- **额外节点 33~40**(node_seq 4/5)挂在每支 **2.3 节点**(2/10/18/26)上：seq4 `33←2 34←26 35←18 36←10`、seq5 `37←26 38←2 39←18 40←10`。
- **配表无坐标字段**(键只有 layer/node_seq/pre_genius/passive_skill_id_lv/genius_type…)，所以径向布局只能自己算(`GeniusTree.h`)。`genius_type`=分支号、`butcher_genius_find_dict`=(branch,layer,seq)→id 可交叉校验。
- id→名表(监管 1~40)见 `genius-table.md`，已逐条对齐，无"配表/内置不一致"。

### 4. 工具（`逆向存档\_scripts\`）
- **`cmd_hunter_tree.py`**：dump 场上监管 `genius_id_lv_lst` 全树，逐条用配表解名称/层.序/前置 + 内置表交叉校验。局内跑(打监管最直接；打求生者也能读对面监管，但对面监管天赋服务器**不一定下发**)。
- **`cmd_genius_topo.py`**：dump 全 40 节点 `pre_genius`/layer/node_seq + 单节点全键 + `DM` 相关表(butcher_genius_data/find_dict/max_data/branch_passive_item_data/recommend_genius/pid_genius)。配表账号级，天赋页/大厅/局内随时能跑。

### 5. ★ send_cmd.ps1 两处修复（2026-10-19，所有探针受益）
- **中文乱码**：原来 `adb shell cat idv_cmd_out.txt` 把 UTF-8 文件按系统 GBK 解码→中文全坏(ASCII 不受影响)。改成 **`adb pull` 原字节 + `[IO.File]::ReadAllText(tmp, UTF8)` + `-split`**。
- **UID**：换机后游戏 UID 变 **`u0_a409`**，send_cmd 里 chown 的 `u0_a310` 已改对(之前靠目录 setgid+组 `ext_data_rw` 的组读权限才侥幸能用)。

## 七、待办

1. ~~**剩余冷却**~~ —— **2026-09-22 结案：`skill._cd_delta`**，见第四节。
   `skill_btn_status`/`share_cd_skills`/`st_add_cd` 也一并查清了
2. ~~**绝处逢生是否已生效过**~~ —— **2026-09-22 结案：`unit.ability_used`**。

   ```
   MyCivilianUnit uid=1000005   ability_used = {102: True}   ← 用过绝处逢生的本人
   CivilianUnit   其余三人        ability_used = {}
   ```

   键是**被动技能 id**（绝处逢生 = `102`，见 [`genius-table.md`](genius-table.md)），
   值 `True` = 本局已消耗。

   ~~⚠️ 只在本机玩家身上验证过。~~ —— **2026-09-22 补齐样本，完全结案：别人的也读得到。**

   本机打监管（`MyButcherUnit` uid=1000002）那局，场上真人木偶师触发了绝处逢生：

   ```
   CivilianUnit uid=1000001   ← 非本机，类名没有 My 前缀
     ability_used  dict @0x7C5B2119F0  nentries=1
         #0  键=102 (int)  值=1 (bool)          ->  {102: True}
     ability.passive_skill_dct  21 条: ... 121:3, 256:3, **102:1**   ← 配装里确实带了
   ```

   配装（`passive_skill_dct` 有 `102:1`）和消耗（`ability_used[102] = True`）互相印证。
   **服务器会把非本机玩家的被动消耗状态下发给本机客户端**，监管看四个人都准。

   ⚠️ **`ability_used` 只存在于求生者类上**，`MyButcherUnit` 身上根本没有这个属性。
   C++ 侧要按阵营分流去查，别在监管身上扫（每个单位白扫上千条）。

   同族字段：`trigger_event_only_once_lst`、`ghost_model_used`（实测都是 `[]`）；
   每个单位还有 `ability` = `ClientUnits.Ability.Ability` 实例，
   里面 `passive_skill_dct` = `{被动技能id: 等级}`（本局 22 条），
   `passive_skill_pydata` = `{(sid,lv): 完整配表}`。
3. ~~辅助特质六个的冷却~~ —— **冷却值 2026-09-22 由用户直接给全**，见第三节表格。
   **★ 2026-09-22 结案：权威配表 `GK.DM.support_skill_data[特质][handheld_id]['skill_id']`**
   （注入 probe2 命令通道 dump，原始数据 `逆向存档\2026.0917_b6f53566\captures\support_skill_data.txt`）。
   同一特质按监管角色(handheld_id)给不同 id，**没有统一规律**（曾以为是"前缀×1000+后三位"，**错**：
   传送有 `12644`/`13718`/`3844`，窥视者有 `735`/`738`，移形每个角色都不同 `8802`/`8811`/`8883`…）。
   **每组第一个 id = 主技能**（实测：窥视者 732 活、733 恒 30；闪现 711；传送 741 与 743 共享冷却）。
   聆听 `701`、失常 `751`、兴奋 `722`、闪现 `711` 全角色通用；巡视者/传送/窥视者/移形各 35~38 个角色版本。
   `PyGenius.h` 把每个特质所有角色的主技能 id 编成静态表，在 `skill_dict` 里找落在表里的那个。
   热更上新监管 → 表缺新 id → 该角色只显示特质名不显示冷却（不会错），重 dump 这张表即可。
   同目录还有 `role_support_config`（85 条，按角色的外观配置，与技能无关）。
   ⚠️ **这是真缺口，不是过期待办**。曾误以为"`leader_skills` + `is_leader_skill` 能通用筛出
   特质技能、不需要 id"，被抓包推翻（见待办 #6 (b) 的 BUG 记录）：`leader_skills`
   混着角色自身技能，没有 id 表分不出哪个是特质。缺 id 的特质只能显示名字、不显示冷却。
   哪天带到了，探针会自动 dump `skill_dict`，把 id 补进 `PyGenius.h` 的映射表。
   另外 **1(聆听) 是充能型但参数未知**（窥视者是 3 层×30 秒，聆听不知道）。
4. ~~监管天赋 8~~ —— **2026-09-22 配表实测结案：`butcher_genius[8]` = 禁闭空间**
   （官方描述"…同时可以封住窗户20秒…"）。见 [`genius-table.md`](genius-table.md)
5. ~~天赋 33+ 散号和中段小天赋~~ —— **2026-09-22 全部拿到**，
   80 条完整表见 [`genius-table.md`](genius-table.md)
6. ~~把天赋/特质接进叠加层~~ —— **2026-09-21 已实现，2026-09-22 编译验证通过**，
   见 `jni\src\Android_draw\PyGenius.h`（header-only，独立线程 500ms 一轮，
   双缓冲发布，`model+0x20` 指针身份配对）。绘制侧在人物距离下面依次加了天赋行
   和监管辅助特质行，开关是「显示天赋」。2026-09-22 又加了三件：

   **(a) 绝处逢生三态**：没带=白 / 带了未用=绿 / **已用=灰**，
   读 `ability_used[102]`（别人的也读得到，见待办 #2）。

   **(b) 监管辅助特质的剩余冷却**，显示在特质行上：
   `闪现 就绪`(绿) / `闪现 12.7s`(白) / 充能型 `窥视者 2/3 20.9s`、满层 `窥视者 3/3`。
   实现要点（两个坑都按第四节的记录避开了）：

   ```
   unit.skill_mgr -> leader_skills(set)  筛出当前特质的技能 id   ← 必须过这一步
                  -> skill_dict{id: Skill} 取 is_leader_skill=True 的那个
                     -> _cd_delta / cd_time / power_num / _cur_power_num
   ```

   - **旧特质的技能对象会冻结而不是归零**，所以"取 _cd_delta 最大/非零的"会读到
     上一个特质的残留值。`leader_skills` 读不到就干脆不显示，不猜。
   - ~~同一特质挂多个技能对象时只有 `is_leader_skill=True` 那个是活的。~~ **错**，见下。

   ⚠️ **BUG（2026-09-22 用户报"一直显示就绪，用过也一样"，对照抓包确认）**：
   上面这条链路**本身就是错的**，`leader_skills` + `is_leader_skill` 筛不出特质技能：

   ```
   skill_charge_窥视者.txt   leader_skills = {25732, 25733, 2601, 2604, 2605, 2610, 2611, 2612}
                              2601/2604/2605 SkillNormal lead=True  _cd_delta=0   ← 红夫人普攻等
                              25733 SkillEyeChannel    lead=True  _cd_delta 恒 30 ← 也是 lead，但是死的
   skill_cd_fields.txt       leader_skills = {3621, 711, 3624, 3625, 712, 3630, 3631, 3632, 3601, 3634, 3610}
                              3630/3631 (乌鸦监管角色技能) 也是 lead=True
   ```

   - `leader_skills` 装的是**角色自身技能 + 特质技能**，不是只有特质
   - `is_leader_skill=True` 的也不止一个（25732 和 25733 都是，但只有 25732 的 `_cd_delta` 在走）
   - 代码按 `skill_dict` 顺序取**第一个**同时满足两条的就 return，
     实际取到的是角色普攻 `SkillNormal`（`_cd_delta` 恒 0）→ 永远"就绪"

   **已修复（2026-09-22）**：`PyGenius.h` 的 `是特质主技能(特质, sid)` 查静态表
   （来自 `support_skill_data`，见待办 #3），遍历 `skill_dict` 先按 id 筛、只解那一个技能对象。
   `support_skill_id` 本身是实时值（底牌换完立刻变），旧特质的冻结技能对象不在当前特质的表里，
   自然不会被选中，所以 `leader_skills` 这一步也不需要了。临时调试面板已删。
   （中间版本用过"后三位"匹配，已被配表推翻并替换。）
   - 新写的 `读浮点()` 值域是 **0~600**，**不能套进度那条 0~100 的闸**
     （闪现 `csv_cd_time` 就 150）。防竞态三读一条没省，`_cd_delta` 每秒在减、
     float 对象一直在重新分配。
   - 读 `set` 用 CPython 3.11 `PySetObject` 布局：`+0x18 used`、`+0x20 mask`、
     `+0x28 table`，表项 `setentry{key,hash}` 16 字节，槽位数 = `mask+1`，空槽 key 为 NULL。

   **(c) 天赋锁存准入条件换成语义验收**，见下面待办 #7 的补充。
7. **找一个稳定的天赋来源** —— 现在的锁存只是绕开了 `genius_id_lv_lst` 读不出的问题，
   **不是解决了**。用户的判断是"天赋这种东西不会换来换去，读不稳就是位置没找对"，
   这条不要当成已完结。把可能性拆清楚，别再含糊地说"间歇失效"：

   | | 说法 | 判断 |
   |---|---|---|
   | (a) | 位置错了，数值碰巧像天赋 | **已排除**（2026-09-21 名字交叉印证） |
   | (b) | 名字对，但这是**临时缓冲**：塞进去 → 应用成效果 → 清空，权威状态在别处 | **已排除**（2026-09-22 注入实测，见下） |
   | (c) | 就是权威存储，只是**冷页被换进 zram** 读不到 | **仅剩它** |
   | ~~(d)~~ | ~~名字和位置都对，是我们的读取方式读不到（split-table）~~ | **2026-09-22 已排除，见下** |

   ### ★★ 2026-09-22 收尾：(d)-1 split-table 排除，只剩 (c)

   **下面那句"下一步就查 split-table"已经查完了，结论是否定的。** 跨进程实测：

   ```
   CivilianUnit    [实例dict] ma_keys=0x7B78B10190  ma_values=0x0  dk_kind=1  combined
   MyButcherUnit   [实例dict] ma_keys=0x7B78C9BA00  ma_values=0x0  dk_kind=1  combined
   ```

   `ma_values = 0`、`dk_kind = 1`（CPython 3.11 的 `DICT_KEYS_UNICODE`，combined），
   **不是 `kind == 2` 的 split table**。而且同一次**跨进程裸读**就把天赋读出来了：

   ```
   CivilianUnit(木偶师)   genius_id_lv_lst  14 项  [[9,1],[11,3],[13,3],[16,1],[17,1],[19,3]...]
   MyButcherUnit(本机监管) genius_id_lv_lst  18 项  [[1,1],[4,1],[6,1],[7,1],[9,1],[11,3]...]
   ```

   18 项跟注入探针进程内读到的 `len=18` 完全一致。

   **所以"读不出天赋"不是结构性的，是间歇的测量问题**，剩下的解释基本只有
   (c) zram 冷页换出。这也说明 `PyGenius.h` 那套"锁存 + 准入校验"方向是对的 ——
   它绕开的确实是偶发读失败，不是在掩盖位置错误。

   > 边界：这局是 1v1，每个类只有**一个实例**样本。skill 自己记过"同一个类不同实例
   > 可以一个 split 一个 combined"，所以严格说是"这两个实例上排除了 split"。

   ### ★★ 已替换（2026-09-22）：增量累积 + 二次确认

   下面那条"语义验收"锁存已经**废弃**。现在 `PyGenius.h` 的 `读天赋()` 按 uid 增量合并：
   - 每条 `[id, 等级]` 要在**两个不同轮次读到相同值**才确认；等级按配表校验
     （id 1~40；`id%8 ∈ {3,5,6,7}` 且 ≤32 的可 1~3 级，其余只有 1 级）
   - 列表长度 `ob_size` 记为 n；**确认数 == n 才算完整**；n 变了或确认数 > n 就整份重来
   - 空列表不动记忆；记忆只在 `unit_mgr` 地址变化（换局）时清
   - 显示三态：未知（不画）/ 部分（已确认的大天赋 + `?`）/ 完整（一个大天赋都没有写"无"）
   - **2026-09-22 补：一轮读全直接判完整**（合法且不重复的条数 == n），不等第二轮；
     与已确认值冲突则清空、本轮值只当候选。起因：用户报"天赋全不显示、不如锁存版"，
     现场 `VmSwap 1.1G` / `VmRSS 390M`，天赋 list 头和元素数组页都被换出；代码逻辑逐行审过无错。
     天赋页是**冷页**（开局后游戏不再访问），换出后驱动读不回来，所以必须趁热一次拿下 ——
     纯"两轮确认"在页正在被换出时比锁存版更脆。内存恢复后不改代码也自己好了。
   - **潜在 BUG（未修、未实测）**：换局靠 `unit_mgr` 地址变化判断，scudo 可能把新一局的
     UnitManager 分配到同一地址 → 记忆不清 → 沿用上一局同 uid 的天赋（表现是显示错，不是不显示）。
     修法：记忆项再记一下单位实例地址，实例变了就清。
   - 绝处逢生多一个"未知"态：**只有表完整时才能断言"没带"**
   废弃原因：旧规则把"读全了没有"和"一般人怎么带"混在一起判，少带大天赋 / 没带 26 的人
   永远锁不上，而且"没带"和"读失败"返回同一个结果。

   ### （已废弃）锁存准入条件（2026-09-22 按用户要求改成语义验收）

   原来是"合格条目 >= 8"这种纯数量阈值。它挡得住随机垃圾，但挡不住**残表** ——
   页换出导致大天赋那几条恰好没读到时，条目数照样够多、却少了关键位，
   锁进去就是永久错误。现在改成：

   ```
   大天赋 = id 8 / 16 / 24 / 32 命中的位数
   求生者：大天赋 >= 2  且  必须有 26(绝处逢生)
   监管  ：大天赋 >= 2
   ```

   ⚠️ **代价**：真的没带绝处逢生的求生者会**永远锁不上**，天赋行一直不显示。
   实战里求生者基本人人带 26，可接受；哪天不成立了，放宽的就是这一条。

   ### 2026-09-22 注入实测：(a)(b) 已排除

   进程内探针同时取三条路径，结果完全一致且稳定非空：

   ```
   MyButcherUnit uid=1000005
     getattr        len=18   [[1,1],[4,1],[6,1],[7,1],[9,1],[11,3],[13,3],[16,1],[10,1],
                              [36,1],[17,1],[19,3],[21,3],[24,1],[18,1],[25,1],[26,1],[34,1]]
     实例 __dict__  len=18   完全相同
     类层描述符      None     ← 没有 property / data descriptor
     dict 条目数     997      (CivilianUnit 是 1299~1300)
   ```

   时间线 123 个样本、跨 245 秒、共 10 次检查，**一次都没有出现空值**。

   结论：
   - **(b) 临时缓冲 排除** —— 它不会被清空，一直是完整的
   - **(d)-2 property 抢在实例 dict 前面 排除** —— 类上根本没有描述符
   - **`genius_id_lv_lst` 就是权威存储**，位置和名字都对

   **所以问题 100% 在"我们跨进程怎么读"这一侧**，只剩 split-table（(d)-1）和 zram（(c)）两条。
   下面 (d)-1 的检查照做，现在它的嫌疑最大。

   **(d) 的具体机制，按可能性排序**：

   1. **split-table（共享键）dict** —— CPython 3.11 里实例 dict 常是 split 的：
      `dk_kind`(keys+0x0A) `== 2` 时，**`entries[i].me_value` 按设计恒为 NULL**，
      真值在 `ma_values`(**dict+0x28**) 指向的 `PyObject*` 数组里，下标就是 entry 序号。
      我们现在只读 entries 的 value —— 遇到 split 表必然读出空，而 `getattr` 透明处理。
      **这个机制产生的症状跟观察到的一模一样：键名好好的、值是空。**
      而且同一个类不同实例可以一个 split 一个 combined（删过属性/属性太多就会合并），
      正好对上 skill 里早就记过的"同一个类不同实例 dict 形状不一样"。
   2. **data descriptor / property** —— 类上有同名 `property` 时它**优先于**实例 dict，
      `getattr` 走的是 property、我们读的是实例 dict 里那份可能早已失效的缓存。
   3. **采样相位** —— 他在 `UnitManager.tick` hook 里读，每帧同一个时点、持 GIL；
      我们是异步 100/500ms 打点，撞在 list 重建的窗口里。这是 (b) 的精确版本。
   4. **zram + 驱动静默返回 0** —— 只影响跨进程读，进程内访问会把页换回来。这是 (c)。
   5. **freelist 复用** —— 解引用时对象已被回收重用；进程内不存在这个问题。

   **下一步就查 1，而且工具早就有了**：`ma_values`(dict+0x28) 非 0 = split table 这件事
   `idv-reverse-resume/python-layer.md` 第三节已经记过，`py_attrdbg.py` 本来就会打印 dict 头。
   **以前只是从没拿它对着 `genius_id_lv_lst` 跑过**，一直在猜 (b)/(c)。
   跑一次，看 `dk_kind`(keys+0x0A) 和 `ma_values`：
   **非 0 或 kind==2 → 坐实 (d)-1**，改读 `ma_values[序号]` 即可，
   而且会连带修好所有"值读不出"的属性，不止天赋。

   **`genius_probe.py` 还能把 (b)/(c) 分开**：读不到 `ob_size` → (c)；
   `ob_size` 真的是 0 → (b)；能稳定读到完整内容 → 之前的观察全是测量问题。
   **先跑这个再谈别的**，不要跳过它去猜。
   已排除的：`skill_mgr` 的 `passive_skills` / `leader_skills` / `relative_skill_set`
   （都是技能 id 集合）。还没试的方向：
   - `<uid>_psv_sid_<n>` 那套属性修正项挂在哪个管理器上
   - `genius_show_outline_lst`（一直读出 `[]`，但名字对得上，也许在别的时机有值）
   - `unit_mgr` 或某个全局管理器上有没有一份"全场配装"的表
     （像 `units_by_type` 那样一次性拿全场的），比逐个单位读更可能是持久的
   - 先摸清 `genius_id_lv_lst` 到底什么时候非空：用 `py_tick.py` 的指针差分
     看它被重新赋值的节奏，能不能跟某个游戏事件对上
8. ~~**道具真假判据**~~ —— **2026-09-22 完全结案：`+0x6D & 0x40`**，见第六点五节。
   手持 / 掉地上的真道具都是 `0x50`，废弃模型是 `0x10`，已实测
10. ~~把大天赋改走 player_data_list~~ —— **2026-09-23 已落地但方案改过一次**：
    局内仍以 `unit.genius_id_lv_lst` 为权威（实时、且含 26；`final_genius` 里没有 26），
    花名册只在"一条都没读出"时兜底并标成不完整。**特质绝不用快照兜底**。
11. **准备阶段显示问题：2026-09-24 修复**（最终产物 `rduvwfos.sh` md5 `06c2797c…`，**编译成功但手机断开未推送、未上机**；
    版本演进和每版的坑见六点七节末尾「落地过程」表）。
    `oisdbrwc.sh` 的遗留 BUG：准备阶段那行只拼了 `GeniusLine` 的 `pre`+`post`，漏了中间的 `flywheel` 段，
    "双弹飞轮"只显示"双弹"，`rduvwfos.sh` 已改成三段都拼。以下是更早的记录：
    ★ `leaodntc.sh` 上机"换几次天赋后变成 0 条"：**内存压力**（VmSwap 1.1G > VmRSS 675M）。
    `uid2pos` 里的 eid 对象（ObjectId / int）是进房时建的冷页，几分钟后被换出，驱动读不到 → 每轮现拼键全失败。
    `final_genius_dict` 本身一直是热的（有人换天赋就被改写）。修法：**每个房间只建一次"座位→键字符串"缓存**
    （面板实例变 = 换房间才清），再缓存匹配到的键对象指针（下一轮先比指针，不读字符串），
    某轮读不到就沿用上次的天赋；读全了才覆盖（含空列表 —— 对面换天赋途中会短暂是 `[]`）。
    诊断工具 `_scripts\fgd_check.ps1`（进程内 dump + PC 侧按 C++ 读法复查，输出 `*_fgd_fail.txt` / `_mem.txt`）。
    uid2pos 被原地改（有人进出房间）不会触发重建 —— 用户 2026-09-24 确认实际不会发生，**不用处理，别再提**。
    ★★ **最终数据源 = `g_avatar.final_genius_dict`**（监管视角 60 秒差分：对面真人求生者 60 秒换了 16 次天赋，
    只有它每次都跟着变；`eid_2_player_info` / `player_data_list` 全程停在进房值，只有 `status` 变 —— 都是快照。
    工具 `_scripts\prepdiff60.ps1` + `cmd_prepdiff.py` + `prepdiff.py`，报告在 `captures\cmd\prepdiff_0924_124109\`）。
    键是 `str(eid)`：人机十进制、真人 ObjectId 的 24 位小写 hex。**ObjectId 布局**：basicsize 24、唯一槽 `__id`
    → 对象 `+0x10` 是 bytes，bytes `+0x10`=长度 12、`+0x20` 起原始 12 字节（PC 侧读内存验证与 `str(oid)` 一致）。
    座位从 `UIRoomWait.uid2pos` 取键对象、逐个拼串去 `final_genius_dict` 查。
    ⚠ 动态字符串**不能用 `PyCore::find_key`**：它的驻留缓存保存 `name` 指针（只允许字符串常量），要自己遍历 + `str_equals`。
    以下是中间两版（`nmreqobt.sh` 用 c_skill_data、`jvbpeldh.sh` 用 eid_2_player_info）的记录：
    落地内容：只在 `UIRoomWait.role == 1`（我是监管；2=求生者，两阵营都实测过）时收集并显示；
    ★ **我是监管时 `c_skill_data` 是空列表**（它只装本阵营，求生者视角下的队友），第一版 `nmreqobt.sh`
    用它，上机面板显示"求生者天赋0条"。监管视角的数据源是 **`UIRoomWait.eid_2_player_info`**
    （`{eid: {role_type, pid, final_genius, ...}}`，进房快照；对面求生者进房后改天赋会不会同步，未验）。
    座位号来自 `UIRoomWait.uid2pos`，其键与 `eid_2_player_info` 的键是**同一 Python 对象**（监管视角 4/4 实测；
    求生者视角下与 `c_skill_data` 的 `row[0]` 也是同一对象），C++ 直接比指针；显示格式 `1号[…]  2号[…]`，按座位排序。
    **教训**：功能是"我当监管时显示"，数据验证却全是在我当求生者时做的 —— 验证必须在功能生效的那个视角下做。
    **准备阶段监管辅助特质的显示已删除**（用户不要了，`roster_hunter_trait()`/`roster_at()` 一并删）。
    实测对照（2026-09-24 准备房间）：座位1 pid94 邮差、2/3 pid78 先知 `[16,32]`，4 本人 pid3 幸运儿 `[8,24]`，
    与用户报的"双弹大心脏 ×3、飞轮搏命"完全一致。
    现象两个：准备阶段**求生者天赋不显示**、**监管特质显示的是上一局的**。同一个根因：
    `try_refresh()` 假设"局外 `unit_mgr` 不存在"，只在 `!is_obj(um)` 分支里发布花名册/`c_skill_data`。
    但实测**大厅和准备阶段 `unit_mgr` 都在**（`units_by_type` 键 69/100/1007），于是走局内分支，
    `count == 0` → `return false`、**`g_active` 不翻转** → 绘制侧一直读上一局局内最后发布的那份
    （花名册是上一局的、`civ_size()==0`）。大厅显示旧特质也是它。
    修法：`read_civilian_skill_rows()` 找到 `UIRoomWait` 就置原子标志；`count==0` 且标志为真时照样发布；
    绘制条件加"`UIRoomWait` 存在"。局内中途读失败（count==0、无面板）行为不变。
    （旧记录里怀疑的 `g_civ_n = 0` 位置问题早已修好，不是原因。）
    佐证数据：大厅 `player_data_list` 仍是上一局（`captures\cmd\112108_lobby.txt`），
    进准备房间立刻换成本房间（`112819_prep1.txt`）。
12. **监管特质实时源：低优先级，不深究**（用户 2026-09-24）。用户听说**准备阶段监管天赋不下发**给求生者，
    所以对方在准备界面改特质后我们只能显示进房时的快照（会滞后）。日后若要做，
    拆成"准备阶段监管换天赋/换特质"单独实验（需要真人监管的房间）。
13. **天赋/特质要独立的折叠框**（用户 2026-09-23 提出，未做）：现在天赋信息混在基础信息和绘制设置里，
    要单独开一个折叠框专门显示天赋与特质。
9. `py_unittypes.py` 在大厅里会崩（`units_by_type` 取不到时把 `None` 塞进 `%X`），
   加个空值早退就好。`py_chain.py` 同样情况会报"units_by_type 里没有键 N"，那个是正常提示
