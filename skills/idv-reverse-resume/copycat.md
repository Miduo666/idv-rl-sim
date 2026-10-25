# 模仿者模式（身份局 / Copycat）—— 隐藏身份读取与叠加层显示

> 2026-09-24 建立。两局注入实测 + 代码落地。若辰对应的逆向记录见 [`ruochen-teardown.md`](ruochen-teardown.md) ⑦。
> 三阵营：**侦探团 / 模仿者 / 中立**。

## 一、结论（两局实测，数据 `逆向存档\2026.0917_b6f53566\captures\cmd\copycat_0924_153905` / `_155412`）

| 项 | 结论 |
|---|---|
| 模式判定 | `g_world_mgr.cur_world` = `WorldBattleCopycat`（wt=80，scene 82/83）；UI 有 `UIBattleCopycat*` |
| 玩家单位 | `units_by_type[1088]` `CopycatPlayerUnit` ×12，**不在键 1/2**（实例字典约 699 条，比普通求生者小） |
| **身份** | **`unit.identity_id`**，进局约 2 秒后赋值（之前是 None），整局不变（开会/死亡都不变） |
| 冗余来源 | `unit.params['identity_id']`、`unit.combat_unit.components[1007].identity_id`（= 若辰说的"组件里的身份"） |
| **别人的身份** | **全场 12 人真身份都下发给客户端**。两局都 12/12 有值、构成都是 7×1xx / 3×2xx / 2×3xx；第二局本人是中立(301)，照样读到 3 个模仿者 |
| **号码** | 游戏里的号码 = **`copycat_index + 1`**（用户确认：index 4 = 5 号本人、index 9 = 10 号死者） |
| **阵营** | **没有独立字段**（若辰的 `camp*`/`camp_type`/`identity_type` 这一版全不存在）。按号段：1xx 侦探团 / 2xx 模仿者 / 3xx 中立 |
| 死亡 | 原单位留在 1088（`model.visible=False`），另生成 `[1089] GhostCopycatPlayerUnit`：同 `unique_id`、`identity_id=None`、`copycat_index=-1`、有 `dead_reason`（如 `'ghoul_kill'`）/ `kill_anim_src_uid` |
| `unique_id` | 字符串（账号 uid 纯数字，如 `'<账号uid_A>'`），PyCore::read_str 能读 |
| 自身 | `g_cam_ctrl.unit` = 本人的 `CopycatPlayerUnit`，锚点照常可用；`unit_type` 不是 1/2 |
| 其它键 | `[1210] CopycatDirectorCloneUnit`（导演局才有，identity=None）、`[1211] CopycatDirectorPuppetUnit`、`[1203] CopycatGhoulUnit` 食人鬼（地图生物，会杀人）、`[19] PosterUnit`、1092~1214 场景交互物（楼梯/电梯/磁铁/电话亭/矿车/棺材/司南……） |
| 干扰物 | `CopycatMagnetUnit` 的模型是 `chr\boss\spkantan\spkantan.gim` —— 类名含 `boss`，会被按类名当成监管、也会被类名兜底的预知监管报出来 |
| 本人历史 | `g_avatar.copycat_advance_data.last_camp_lst`（如 `[1,1,1,1,2]`），阵营编号同号段 |

**名字表**（若辰 `sub_394ED4` 跳转表，只实测了本人两项 114 掮客 / 301 流浪汉）。
**101 = 侦探**（2026-09-26 整表解码：若辰先把名字预设成"侦探"再按 `identity-101` 跳转，只有 101 那格不改名字；
细节见 [`ruochen-teardown.md`](ruochen-teardown.md) ⑦。~~旧记录"101 取对象自带名"是错的~~）：

```
101侦探 102哨兵 103治安官 104猎人 105香料师 106锁匠 107银行家 108修士 109演说家 110拳击手 111灵媒 112学徒
113密探 114掮客 115药剂师 116巡林员 117执灯人 118评论家
201神偷 202千面人 203阴谋家 204烟火师 205怪盗 206催眠师 207地下医生 208处刑人 209指挥家
301流浪汉 302送货员 303愚人 304棋手 305清洁工 306顾问 307降灵师 308导演
```
叠加层字体（OPPOSans 裁剪版）已查过覆盖以上全部字。

## 二、代码（`IdentityV`，产物 `arfxcuoy.sh` → `cxoytfzv.sh` → `poylhvni.sh` → **`utyzmidc.sh`（md5 `998286ed…`，2026-10-16 已推送 `/data/`，未上机）**）

> **★ 2026-10-16 最新（utyzmidc.sh）修了两件事，见第四点一节**：① 假面舞会的 position 读取改成 6 候选回退链 + 把硬校准降成非阻塞；② 新增食人鬼/导演单位的收集与绘制。下面是更早 `cxoytfzv.sh`/`poylhvni.sh` 的结构，仍然有效。

> `poylhvni.sh` 这版新增：101 侦探入表；**按 `unit.position` 绘制**（见第四节）。下面是 `cxoytfzv.sh` 时的结构，仍然有效。

### `PySelf.h`
- `check_lobby()`：键 1088 也算"有玩家"。**不改的话这个模式被判成局外 → 人物整类不画**（跟开关无关，一直生效）。
- `collect_copycat()`：扫 1088，每人读 `model+0x20` / `identity_id` / `copycat_index` / `unique_id`，每项可单独失败（留 0）；
  扫 1089 取鬼魂的 `unique_id` 认死者。活人进本体集合，死者不进。`another_model` 照样进废弃黑名单。
  **放在 `try_refresh` 的锚点之前**：开会阶段锚点常读不到，身份簿照样要更新。
- **身份簿（锁存）** `CopycatBook`：按号码记 `{known, body, identity, dead}` + `self_seat`。
  - 读到就覆盖（新值永远赢 —— 所以万一换局没清干净，新一局第一次读到就纠正）；读不到沿用
  - 死亡只置不撤；`unit_mgr` 地址变了清空；界面开关关掉清空（`set_copycat_book()` 每帧同步）
  - 双缓冲发布，**不依赖锚点成功**；`book_mark_self()` 在锚点成功后标出"我"
- 接口：`copycat_active()`（快照里有 1088 单位）、`copycat_book()`、`copycat_book_ready()`、
  `copycat_identity(obj,&id,&seat)`（**查簿子**，死者/不认识的模型返回 false）、`copycat_camp()`、`copycat_identity_name()`。

### `draw_Gui.cpp`
- 独立折叠框「模仿者模式」，里面一个「模仿者」开关；**与「预知监管」互斥**（勾一个自动取消另一个）。
  开着时列出簿子：`N号 身份  (我)  已死`，按阵营着色，已死灰色；顶上 `已记录 X 人，身份已知 Y 人`。
- 开关开着：名字换成 `N号 身份`，文字 + 方框 **侦探团蓝 / 模仿者红 / 中立黄 / 未读到白**；**不画射线**。
- 开关开着且簿子非空：**按簿子过滤**（只画簿子里的活人），不再依赖本体集合 —— 开会时本体集合读不全，
  退回按类名画会把尸体、鬼魂、石像全画出来。
- 模仿者局里不显示预知监管（`!PySelf::copycat_active()`），挡掉磁铁误报。
- 共用配色函数 `copycat_color(identity)`。

## 三、为什么需要锁存：开会阶段页被换出

用户观察：**游戏在负载较低时会把页换出去，模仿者的会议正好属于这个阶段**。会议期间 Python 堆页进 zram，
驱动读不到 → 身份、模型指针、锚点全读不到。机制同 SKILL 主文件「内存压力造成的偏移失效假象」一节。
所以身份必须在进局后页还热的时候（约 2 秒赋值后）读到并锁住。

## 四、假面舞会（石像模型）—— 2026-09-26 改成按 `unit.position` 画（学若辰），待上机

**现象**（用户 2026-09-24 报）：假面舞会玩法里所有人都变成同一个石像模型，身份显示失效。场景数组里人物模型从 12 个变成 24 个
（12 个原模型 + 12 个石像）。

**原因**：身份按"场景对象 = 簿子里的 body"配对，石像是另一个场景对象，对不上；石像类名多半不含 `player`，
根本不进阵营 1/2 的分类。

**若辰怎么做的（2026-09-26 查二进制）**：**没有任何舞会/石像的专门处理**（搜不到 masquerade/statue/dancer/舞会/石像），
它天生不受影响 —— 根本不按模型配对，位置读 Python 单位的 `position`（再依次回退 `visual_position/logic_position/pos/
world_position/puppet_position`）自己投影，身份读 `identity_id`。详见 [`ruochen-teardown.md`](ruochen-teardown.md) ⑦。

**我们的改法（`poylhvni.sh`）**：
- `PySelf.h` `collect_copycat()` 顺带读每个活人的 **`unit.position`**（`+0x10/+0x14/+0x18` = X/高度/Y，照 `read_number`
  做"读指针 → 读对象 → 再读指针 + refcount>0"，最多三次），按号码存进**独立双缓冲** `g_pos`，每轮都发布、**不依赖锚点**；
  单次读失败沿用上次值 300ms；换局(`unit_mgr` 变)清空。
- **类型校准**：玩家身上的 position 布局没单独验过，所以第一次读到的值必须跟该人场景对象坐标(`body+0x28 → +0xa0`)
  相差 ≤ 2.0 单位才记下这个对象类型(`g_pos_type`)，之后只认这个类型。日志 `[模仿者] position 校准通过`。
  **一直校准不上 = 布局不对**，绘制自动退回按场景对象画(旧行为)，不会画错位置。
- `draw_Gui.cpp`：大门之后、实体循环之前新增一段，遍历身份簿活人(跳过自己的号码、贴身 <1 米)、按坐标投影，画 `N号 身份`
  + 方框 + 距离（同实体循环那套方框算法、同阵营配色、不画射线）。实体循环里凡是**坐标拿得到的号码就跳过**，只给拿不到的兜底，不会画两遍。
  石像不在簿子里，照旧被簿子过滤挡掉。
- 面板 `自身:` 行多了 `坐标N`（N = 当前有坐标的号码数），没校准时带 `(未校准)`。

**上机要看**：面板 `自身:` 应为 `… 身份12 坐标11`（自己也算在内时 12）且没有 `(未校准)`；日志有 `[模仿者] position 校准通过`；
舞会时方框和名字应仍跟着人走。若 `(未校准)` 一直不消失，先抓一次 `cmd_copycat_masq.py` 看 `position` 的类型和字段。

**旧线索**（来自 full dump，舞会没发生时也在；改成按坐标画之后已不需要，留档）：
- 每个玩家 `combat_unit.components[3]` = `ModelRefComponent`，上面挂 `MasqueradeModelRefHandler`
  （`common_cs.combat_core.components.unit.ModelRefComponent`）
- 系统 `CopycatMasqueradeSystem`（`combat_unit.core.system_instances['systems_copycat.CopycatMasqueradeSystem']`）
- 世界上有 `dancer_room_component`（`DancerCSRoomComponent`），可能相关
- 两次采样**都没碰上舞会**（全程没有单位换模型），所以还不知道石像挂在哪

**探针**：`逆向存档\_scripts\cmd_copycat_masq.py`（单次，列每人所有模型属性的文件名/visible/id、
components[3] 及其 handler 的全部字段、舞会系统字段）。舞会前、舞会中各跑一次：
```powershell
cd "C:\Users\31297\Desktop\逆向存档\_scripts"
.\send_cmd.ps1 cmd_copycat_masq.py 舞会前
.\send_cmd.ps1 cmd_copycat_masq.py 舞会中
```

**（已被上面按坐标画的方案取代，仅在校准失败、必须退回按模型配对时参考）拿到数据后的两种改法**：
- 石像换进了 `unit.model` → 簿子每轮会更新 body，基本自动好；只需让绘制把石像类名归成角色（阵营 2）
- 石像挂在别处（比如 ModelRefComponent 的 handler）→ 簿子每格再存一个"舞会模型"body，`copycat_identity()` 两个都认；
  石像类名同样要进角色分类
- 都要注意：舞会可能正赶上低负载换页，石像指针也要趁热读、进簿子锁存

## 四点一、2026-10-16 落地（`utyzmidc.sh`，md5 `998286ed4eea4c14145c09e872a64429`，已推 `/data/`，**未上机**）

用户报：普通模仿者局正常，但**假面舞会 + 导演局不生效**（石像被过滤、导演/食人鬼不画）。逆若辰二进制对照后发现我们两处"做得不足"，照若辰补齐：

### 根因（调研结论）
1. **假面舞会被过滤**：我们按坐标画那条路（`draw_Gui.cpp` 的 `if (copycat_mode)` 段）只在 `copycat_seat_pos()` 成功时画，而它卡在两件事上——① **只读了 `position` 一个字段**（若辰读 6 个候选依次回退），舞会时 `position` 失活就整个读不到；② **硬校准**：`read_position` 里"position 必须跟场景坐标 `body+0x28→+0xa0` 相差 ≤2.0 才认"，校准不过 `g_pos_type` 恒 0、对所有人返回 false → 退回实体循环的模型配对 → 石像场景对象不在簿子 → `cc_filter` 跳过 → 全场消失。
2. **导演/食人鬼被误杀**：`collect_copycat` **只扫 `[1088]`**，`[1203]食人鬼 / [1210]导演分身 / [1211]导演傀儡`根本不收；`cc_filter`（实体循环）在 copycat 模式下"不在簿子的 camp1/2 player/boss 一律 `continue`"，把这些没进簿子的单位整类抹掉。

### 若辰的过滤条件（反汇编 + 字符串确认，对照用）
- **完全不按 unit_type 过滤**：遍历碰撞场景所有单位，身份从 `combat_unit.components[...].identity_id` 读，阵营靠类名关键字兜底（`civilianunit/hunterunit/mycivilianpuppetunit/mirrorcivilian`…）。
- 二进制里**搜不到 ghoul/director 任何字符串** → 若辰没为食人鬼/导演做特判，靠类名宽进。计数串 `copycat_players=`/`copycat_fields=`。
- 位置读 6 候选链、**不做场景坐标校准**（直接信任 position + sanity bounds）。

### 改动（`PySelf.h` + `draw_Gui.cpp`）
| 改动 | 位置 | 说明 |
|---|---|---|
| **position 6 候选回退链** `position→visual_position→logic_position→pos→world_position→puppet_position` | `PySelf.h` `read_position` + `POS_ATTRS`/`g_cc_i_posattr[6]` | 舞会时 `position` 失活就试下一个。任一候选读出合法 Vector3 就用 |
| **硬校准 → 非阻塞软校验** | `PySelf.h` `read_position` | 首次读到就锁定 Vector3 类型（便宜的一致性闸），**不再要求跟场景坐标对上才画**；body 可读时只打一条日志 `[模仿者] position 锁定 attr=… 场景坐标一致/不一致`。这是假面舞会被过滤的真正根因 |
| **收集额外单位** `[1203]食人鬼/[1210]导演分身/[1211]导演傀儡` | `PySelf.h` `collect_copycat` + `g_extra`/`EXTRA_TYPES`/`ExtraUnit` | 没号码没身份、进不了按号码的簿子，单列一套按 position 画。普通局这些键不存在、`read_list` 返回 false，收不到东西 |
| **绘制额外单位** 食人鬼**橙框**、导演类**紫框** + 固定标签 | `draw_Gui.cpp` copycat 段（按坐标画那块之后） | 同一套投影/方框算法、不画射线 |
| **cc_filter 没动**（有意的） | — | 它正确挡掉尸体/鬼魂/石像的模型配对；假面舞会靠 position 路径、食人鬼/导演靠 extra 块，放宽反而把垃圾放回实体循环。保留是对的 |

**导演本人**：若在 `[1088]` 带 identity 308 → 现有代码当"导演"身份显示（号段 3xx）；若只以 1210/1211 存在 → 被当"导演分身/傀儡"画。两种都不漏（用户定调"信任若辰、不纠结导演本人"）。

### 上机验证点（下一局模仿者/导演局）
- **假面舞会**：方框/名字跟着人走、不再整屏消失；面板 `自身:` 的 `坐标N` 不掉。
- **日志 `[模仿者] position 锁定`**：看锁的是哪个 `attr`（多半 `position`）、"场景坐标一致/不一致"——**不一致也能画**，但记一下（说明玩家 position 布局和密码机不同，回头要查）。
- **导演局**：食人鬼橙框、导演紫框出现。⚠ 若食人鬼/导演类名含 `player/boss`，实体循环 `cc_filter` 会跳过它（不双画）；若不含，可能和 extra 块**双画**——届时跑一次 `cmd_copycat_full.py` 看类名再定。
- **普通模仿者局**：与原来完全一样（extra 收不到，`en=0`）。
- ⚠ 这些类型键 1203/1210/1211 取自本文档第一节（copycat.md），**存档里两局都没碰上导演/舞会**，键值未在活体复核过；上机若 extra 收不到，先 `cmd_copycat_full.py` 确认导演局真实键。

## 四点二、2026-10-18 导演局上机：extra 块两个 bug（待活体数据，未修）

用户实打了一局**导演局**，报两件事（普通模仿者局 / 假面舞会状态见下方「状态总览」，模仿者本身已确认可用）：

1. **导演傀儡 `[1211]` 被画成紫框** —— 它其实就是**本机自身**，本该被自身过滤掉。
   **根因确认**：`draw_Gui.cpp` 的 extra 块（约 1127–1156）收 `[1203/1210/1211]` 后**无条件按 position 画**，
   `PySelf.h collect_copycat` 收集时特意传 `body=0`（不做模型配对），绘制时**完全没有** 1088 号码簿块那两道自身闸
   （`self_seat` 跳过 + `d<1.0f` 贴身跳过）。**是 extra 块漏写自身过滤，不是判据错。**
2. **其他人全被盖成固定标签"导演"** —— `EXTRA_TYPES[1]={1210,1}` → label 1 = **固定串"导演"**。
   导演局里其他玩家大概率就是以 `[1210] CopycatDirectorCloneUnit` 实例存在，于是**一律盖固定标签**、与各自真实身份无关。
   **架构假设错了**：`utyzmidc.sh` 把 1210/1211 当"罕见、无身份的特殊单位"写死标签，而**存档两局从没碰上导演局、这假设从没活体验证过**。
   若辰的做法（§四点一）本就不特判 unit_type、身份统一从 `combat_unit.components[...].identity_id` 读 —— 天然不会把 1210 全标"导演"。

**为什么不能盲改 #2.2**：要让 1210 走回"读 `identity_id`+`copycat_index` → N号 身份"，前提是确认 **1210/1211 身上到底有没有
`identity_id`/`copycat_index`/`position`**。导演局字段布局一次没活体看过，盲写第二次还是赌。

**探针**：`_scripts\cmd_director.py`（2026-10-18 新建，定向、非广度）。导演局进局 2 秒后跑：
```powershell
cd "C:\Users\31297\Desktop\逆向存档\_scripts"
.\send_cmd.ps1 cmd_director.py 导演局
```
输出：模式判定 / **哪个单位是 self（g_cam_ctrl.unit）** / 全部 `units_by_type` 键+类名+数量 /
`1088·1210·1211·1203·1089` 每单位的 `identity_id·copycat_index·is_self·position·model·combat_unit 组件身份`。

**修法（2026-10-18 已落地，产物 `mgednvix.sh`，md5 `098890e0d6ff47e04f851129b5674be9`，已推 `/data/`，未上机）**
—— 全部改在 `PySelf.h`，`draw_Gui.cpp` 一行没动（1210/1211 并入号码簿后，现有绘制循环含自身过滤天然就对）：

1. **components 形状先用汇编钉死**（REA 在本机不可用，用 `llvm-objdump` 读 `若辰正式版(4).sh` @`0x3B60F4`）：
   若辰 `getattr "components"`（兜底 `"_components"`，两字符串常量已核对）→ **枚举整个集合逐个遍历**（begin/end + 24 字节步长）→
   找带 `identity_id`(0x2f85b) 的组件。**整段没有 `0x3ef`/1007 立即数 → 若辰不按定键索引，是遍历**。
   所以 copycat.md §一记的 `components[1007]` 只是活体落点，不是若辰做法。
2. **新增 `read_identity(d, dk, allow_component)`**：先直读 `unit.identity_id`；`allow_component` 且直读为 None 时走
   `combat_unit` → `components`(/`_components`) → **遍历 value 取第一个能读出合法 `identity_id`(100~399) 的组件**（dict 为主、list 兜底）。
3. **`collect_copycat` 从只扫 1088 扩成扫 `{1088, 1210, 1211}`**：导演类 `allow_component=true`（直读 None 才遍历组件；1088 维持纯直读、零回归、不触发遍历开销）。
   都按 `model+0x20`=body、`copycat_index`=号码、`identity`、`position` 进号码簿。
4. **1210/1211 从 extra 块移除**，`EXTRA_TYPES` 只剩 `1203` 食人鬼（橙框）。于是导演局其他玩家按 `N号 身份`+阵营配色画（#2.2 解决）；
   **1211 导演傀儡=自身** → 进号码簿后被 `book_mark_self`（body==anchor，导演局 `cam.unit` 就是傀儡）的 `self_seat` 或绘制侧贴身 `<1m` 过滤掉（#2.1 解决）。
5. `check_lobby`/状态行/`copycat_active` 都认 1210/1211（`is_copycat_player_type`），导演局不会被误判成局外。

**上机验证点（下一局导演局）**：
- 其他玩家显示 `N号 身份名`（不再全是"导演"）；导演傀儡（自身）不画方框。
- 面板 `自身:` 应为 `正常 模仿者局 … 身份N 坐标M`；食人鬼仍是橙框。
- 日志关注 `[模仿者] position 锁定`。⚠ 若其他玩家显示 `N号`（无身份名）→ 组件遍历没读到 `identity_id`：
  说明导演局组件布局不同，这才是真需要 `cmd_director.py` 的那一次（看 1210 的 `combat_unit.components` 里身份挂哪）。
- ⚠ 若 1210 **没有** `copycat_index`（进不了号码簿、整个不画）→ 退一步改成不按 seat、用独立列表按 position 画 `身份名`（无号码）。

## 状态总览（2026-10-18 用户确认）

| 玩法 | 状态 |
|---|---|
| 普通模仿者局（号码+身份+阵营配色+身份簿锁存） | ✅ **可用，无问题**（原待办 #14 关闭） |
| 假面舞会 | ⏳ 还没测（`utyzmidc.sh` 的 position 6 候选 + 非阻塞校验，未验证） |
| 导演局 | 🔧 两个 bug 已按若辰修（`mgednvix.sh`，md5 `098890e0…`，已推 `/data/`，**未上机**），见「四点二」。身份改走 `combat_unit.components` 遍历（汇编确认若辰不定键 1007、是遍历） |

## 五、工具（`逆向存档\_scripts\`）

| 文件 | 作用 |
|---|---|
| `copycat300.ps1` | 5 分钟采样总入口：开始/中途/结束投 `cmd_copycat_full.py`，其余连续投 `cmd_copycat_tick.py`，结束出报告。已设 UTF-8 解码（早期两局玩家名有乱码丢字） |
| `cmd_copycat_tick.py` | 轻量快照：玩家单位上名字命中关键字(ident/camp/role/copycat/dead…)的属性 + 值落在身份号段的整数；排除场景物件(scene/electric/generator/gate) |
| `cmd_copycat_full.py` | 广度搜索（1.5 秒上限）：单位 / 世界 / 可疑 UI 面板 / GK 顶层 / DM 配表名 |
| `copycat_report.py` | 时间线报告：字段覆盖（别人有没有值）、会变的字段、不变的字段 |
| `cmd_copycat_masq.py` | 假面舞会专用，见上 |
| `cmd_director.py` | 导演局定向快照（2026-10-18），见「四点二」 |

方法论再次验证：**不猜字段名**，关键字 + 值域（身份号段）双向扫，第一次采样就命中。
