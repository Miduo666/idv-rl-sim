# 约瑟夫镜世界（photo world）—— ESP 去重 + 世界相对白色鬼魂

2026-10-22 建。解决用户报的"约瑟夫局里镜像密码机进度/人物天赋/骨骼都被额外算一次、关了骨骼还有射线指向鬼魂"。
**核心是先用第五人格静态脚本 + 一次 probe2 把机制坐实，再改叠加层。** 探针 `_scripts\cmd_joseph.py`，
实测存档 `逆向存档\2026.0917_b6f53566\captures\joseph_out_2.txt`（= 第一次那份，两次内容一致）。

## 一、机制（静态源码坐实，不是猜）

- **约瑟夫镜世界在代码里叫 "photo world"（照片/灰世界）**，不叫 mirror。约瑟夫 = The Photographer，相机机制。
- **不生成克隆单位。** `ClientUnits\PhotoUnit.pyc` 的 `_switch_photo_world(self, in_photo, ...)` 是遍历
  `unit_mgr.get_civilian_units/get_generator_units/get_butcher_units/...` 对**已有单位**挨个调
  `switch_photo_state(in_photo)`；`_switch_photoer_model` 给约瑟夫自己换"灰模型"（`create_gray_model`）。
- **真身与镜像是成对的两只独立单位，都在同一个 `units_by_type` 键里**（密码机都在 `[3]`、求生者都在 `[2]`），
  靠一对互指的 uid 字段区分。这就是"额外算一次"的根。
- `units_removed_but_model_by_type` 实测是**空 dict**，不是这条路（当初静态以为是它，错）。
- 静态来源：`all_pyc\ClientUnits\{BaseUnit,GeneratorUnit,CivilianUnit,ButcherUnit,PhotoUnit,FuncComponent\DualModelComponent}.pyc`。
  用 **Python 3.11**（`C:\Users\31297\AppData\Local\Programs\Python\Python311\python.exe`）+ `scratchpad\pyc_dis.py`
  读 co_names/co_consts（⚠ NXS 解包后字节码 name-index 与 co_names 对不齐，**dis 反汇编会 IndexError 崩**，
  只能读名字/常量表，别指望完整反编译）。
- BaseUnit 上的 photo 属性/方法：`in_photo_world` `in_photo_uid` `out_photo_uid` `is_in_photo` `check_in_photo`
  `switch_photo_state(in_photo, photo_unit)` `show_photo_world` `_update_photo_unit`。GeneratorUnit 也继承。
- ⚠ **命名陷阱**：若辰拆解里的 `in_photo`（`sub_412220`，读 uid+in_photo）是"**开局合照**区分人机"的，
  跟约瑟夫镜世界**同名不同义**，别混（见 ruochen-teardown.md 第226行）。

## 二、★ 判据（2026-10-22 probe2 实测，权威）

训练局、约瑟夫、`PhotoUnit.is_active=True`（但 `_players=[]` → 当时没人"进入"镜世界视角）：

| 键 | 总数 | 构成 |
|---|---|---|
| `[3]` 密码机 | 14 | 7 真 + 7 镜像 |
| `[2]` 求生者 | 8 | 4 真 + 4 镜像 |
| `[1]` 监管 | 1 | 只有约瑟夫本人（**无镜像双胞胎**）|

成对互指（实测逐位对上）：
```
真身:  out_photo_uid = None      in_photo_uid = <镜像uid>
镜像:  out_photo_uid = <真身uid>  in_photo_uid = None      ← 这个就是"镜像/鬼魂"
约瑟夫本人: 两个都是 None（photographer 不入对）
```

> **★ 判镜像 = `out_photo_uid` 读出一个 >0 的 uid。** 真身是 None。非约瑟夫局这俩属性恒 None（或不存在）→ 判据恒 false，零副作用。
> 这是整套功能的唯一硬判据，已坐实。

## 三、落地（2026-10-22，产物 `yfuvtpnm.sh` md5 `0e1de650`，已推 `/data/`，**未上机视觉验证**）

用户最终要的不是"全过滤"，而是**按世界相对着色**（原话）：
- 约瑟夫局（监管是约瑟夫）—— **我当求生者或监管都要触发**。
- 我在主世界 → 镜像里的人画**白色鬼魂**；我在镜像 → 主世界的人画白色（对称翻转）。两边的人都显示，只是"另一个世界"的白。
- 镜像密码机/大门/进度**全部不画**（含固定信息 HUD），只留真实世界 7 台 + 真门（= "只隐藏镜像那份"）。
- "另一个世界"的人**不画天赋**（避免重复）；骨骼用白色。

改了 4 个文件（英文标识符）：
- **`PySelf.h`**：
  - `is_photo_ghost(d,dk)` = `out_photo_uid`>0 的判据（共用序号缓存 `g_i_outphoto`）。
  - Snapshot 加 `body_mirror[MAX_BODIES]`（与 body[] 对齐）+ `in_mirror`；`add_body(res,sp,mirror)` 去重时打标。
  - `collect_units` 里对每个单位算 `is_mirror=is_photo_ghost(...)`，照常收进本体集合（镜像也要画），只是打标；
    `hunter_body` 不认镜像。
  - try_refresh 里读 **anchor（g_cam_ctrl.unit）** 的 `in_photo_world`/`out_photo_uid` → `res.in_mirror`。
  - 暴露 `self_in_mirror()` / `body_is_mirror(obj)` / **`is_other_world(obj)`**（= body_mirror != in_mirror）。
- **`PyProgress.h`**：密码机/大门循环里 `is_photo_ghost` 的跳过（真实世界进度/门保留）；
  镜像密码机的 `model+0x20` 场景对象收进黑名单 `g_mirror_gen[2][]`，暴露 `is_mirror_generator(obj)`
  （否则镜像密码机场景对象还会被 `is_real_generator` 画成空"[密码机]"标记）。
- **`draw_Gui.cpp`**：
  - 骨骼循环 `bcol`：`is_other_world(Ms[u])` → `BotBoneColor`(白)。
  - 主循环 `otherworld=is_other_world(data[i].obj)`：名字/方框白、`show_draw_Genius && !otherworld` 跳天赋。
  - 固定信息求生者天赋 HUD（C 块）：`is_other_world` 跳过（否则 4 真 4 镜像重复）。
  - 密码机分支加 `&& !PyProgress::is_mirror_generator(data[i].obj)`。
  - **`ShouldSkipEntity` 放行**：`if (PySelf::is_other_world(obj.obj)) return false;` —— 镜像模型 `+0x70`(visible)
    在对面世界常为 0，会被 `IsGhostEntity` 在 `inform_ghost` 关时整个丢掉；必须显式放行才能画成白色。
- 早先那条"`collect_units` 里 `is_photo_ghost` 一律 continue"的改法**已撤回**（跟"按世界着色"冲突）。

安全性：非约瑟夫局 `out_photo_uid` 恒 None → `is_photo_ghost`/`body_mirror`/`in_mirror`/`is_other_world` 全 false
→ 新逻辑恒不触发，普通局行为一字不变。已编译通过（产物随机名构建）。

## 四、★ 还差一步 / 待办：`in_mirror` 翻转信号没采到真值

"我在主世界 → 镜像白"这半稳（镜像判据实测坐实）。
**"我在镜像 → 主世界白"的翻转**靠 anchor 的 `in_photo_world` / `out_photo_uid`，是**推断写的、没实测过**：
两次 probe2 抓的时候都没人在镜世界里（`PhotoUnit._players=[]`、所有单位 `in_photo_world=None`），
而且第二次其实是注入丢了、读到的是第一次的旧输出（`TIME` 一致）。

**下次要做**：让约瑟夫**真的进镜世界**（或求生者被拉进相中世界），**此时**跑 `cmd_joseph.py`，看：
- `PhotoUnit._players` 是不是变成 `[我的uid]`（enter 往里 append）；
- anchor（约瑟夫）的 `in_photo_world` 是不是从 None 变成真值；
- 求生者被拉进去时，`g_cam_ctrl.unit` 是不是切成了带 `out_photo_uid` 的那只镜像单位。

据此在 `PySelf.h` try_refresh 的 `res.in_mirror` 那段改用正确信号（现在读的是 `in_photo_world`+`out_photo_uid`，
`_players` 方案需要先定位 PhotoUnit —— 扫 units_by_type 找类名含 "Photo" 的单位）。
上机视觉确认：约瑟夫进镜世界后颜色应翻转（主世界人变白、镜像人变正常色）。

## 六、★ "拍照了/镜世界激活"信号 —— 2026-10-22 反编译坐实（静态，未活体）

目标：没拍照时镜世界入口关闭、显示镜像内容无意义，要门控。静态全链解完（`PhotoManager.pyc` / `PhotoUnit.pyc` / `butcher/photo/PhotoComponent.pyc`，`pyc_names.py` 读 co_names/co_consts）：

**约瑟夫拍照是有生命周期的技能，服务端 `PhotoManager`（挂约瑟夫身上的 Photo 组件）管理：**
- `create_photo` → `activate` → `create_and_add_unit(PHOTO)` 建 **PhotoUnit** + 存 `_photo_uid` + 开 `_life_time` 计时器；
- 计时器到 → `_photo_timer_callback` → `remove_photo` → 销毁 PhotoUnit + 进 CD（`_cold_time`/`_end_time`/`_start_cold_time`）；
- **`PhotoManager.is_active()` = `_photo_uid` 有值 = 当前有一张生效照片**（权威服务端标志）。
- **入口门控**：`PhotoManager.enter_photo(uid)` 里是 `is_active and can_enter_photo and ...` → **没生效照片进不去**，正是用户说的"没拍照入口关闭"。

**客户端（叠加层能读的）：**
- **PhotoUnit 只在拍照后才存在**（activate 创建、remove_photo 销毁）。`is_active()` 读 `_time`/`_players`；
  实测 capture `_time=10013` 即已激活（所以我们那两次 capture 其实都是**已激活**态，不是"idle"——第四节的"idle"判断要修正）。
- `PhotoUnit.enter(uid)`/`leave(uid)` = 把 uid 进出 `_players`；`in_photo(uid) = is_active and uid in _players`。
- 镜像双胞胎（out_photo_uid）在 `PhotoUnit.create()`/`remove()` 里建/拆（`switch_photo_state`/`update_photo_unit`/`clone_all_posters_to_photo`）。

**★ 给叠加层的两个信号（静态推出，待活体确认 PhotoUnit 的 key 与 `_time`/`is_active` 语义）：**
1. **"拍照了/镜世界激活" = units_by_type 里存在一个 PhotoUnit 且 is_active（`_time` 有值）**。没照片→没 PhotoUnit。门控镜像显示就看它。
2. **"我在不在镜世界"（= 待办 #4 缺的 in_mirror 翻转信号）= 我的 uid 在不在 `PhotoUnit._players`**。
   `enter` 会 append、`leave` 会 remove，约瑟夫自己进镜世界也在里面（`JOSEPH_ENTER_PHOTO`/`JOSEPH_LEAVE_PHOTO`）。**比现在 try_refresh 读 anchor 的 `in_photo_world`/`out_photo_uid` 干净、权威**，下次改 in_mirror 用这个。

**★ 2026-10-22 用户现场观察坐实**：**没拍照时，现有读取方案照样能读到镜像双胞胎** → 即 **twins（out_photo_uid 配对）开局就持久存在、与拍照无关**（用户直觉对，我静态倾向的"只在 PhotoUnit 活着时存在"错）。推论：
- `out_photo_uid>0` 判据是**常开的、本身不门控** → 没拍照也画镜像 = 要修的 bug，**确定要加激活闸**；
- 修正机制：`PhotoUnit.create()` 不是建立 uid 配对（那是静态骨架），而是**切换镜世界显示/可进入状态**（switch_photo_state/灰模型/show_photo_world），拍照只是"点亮"已有配对。

**★ 2026-10-22 坐实(叠加层诊断版 `uaqpsclf.sh` 上机读面板「镜世界:」)**：
- **PhotoUnit 开局就持久存在**（不是拍照才建；twins 和 PhotoUnit 都是开局就有的静态骨架）。所以"PhotoUnit 存不存在"**不能**当门控。
- **激活判据 = `PhotoUnit._time`**：**没拍照 = `None`；拍照后 = `game_time`（实测 10028）**。照片生命周期结束后 `remove()` 应把它复位回 None（未单独验，但 is_active 读 `_time` 的语义支持）。
- 这跟静态 `PhotoUnit.is_active()` 读 `_time`/`_players` 完全一致。

**→ 门控写法定死**：`photo_active = (units_by_type 里有 PhotoUnit 且其 `_time` 读出一个数、非 None)`。
- `!photo_active` → 镜像双胞胎（`out_photo_uid>0`）整体不收/不画（方框/名字/距离/骨骼全不要）——这就是"没拍照不显示镜世界"。
- `photo_active` → 维持现有镜像绘制。
诊断字段来源：`PySelf::scan_photo_unit` 已经在读 `_time`/`_players`，改成同时发布 `photo_active` 即可。

**in_mirror（我在不在镜世界，待办 #4 的对称白翻转）仍差一个样本**：需要**真的进入相中世界**时读 `PhotoUnit._players`，确认我的 uid 会进列表（拍照但没人进时 `_players=0`）。门控本身不需要它，是额外增强。

## 七、骨骼取消（2026-10-22，draw_Gui.cpp 骨骼循环）

镜像双胞胎是静止死物、游戏按逻辑 tick 低频更新 → 骨骼"一顿一顿"，画它没意义。骨骼循环加
`if (!is_self && PySelf::body_is_mirror(Ms[u])) continue;`（放在 read_unit 前，省掉驱动读）。
**只针对约瑟夫镜像双胞胎**（`body_is_mirror` = out_photo_uid>0），伊斯人幻影等会动的鬼魂 out_photo_uid=None 不受影响。
镜像仍保留主循环里的白色方框/名字/距离（天赋本就 `!otherworld` 跳过）。平滑方案用户否了（见第四节上面那段，不加 EMA）。

## 八、★ 激活门控 + in_mirror + 镜像绘制 落地（2026-10-22，产物 `cyqoesgx.sh` -O3，编译通过，**设备未连未推未上机**）

一次把门控、in_mirror、镜像绘制样式全落地（`PySelf.h` + `draw_Gui.cpp`）。前置产物链：骨骼取消 `whblvzqj` → 诊断版 `uaqpsclf`（面板「镜世界:」坐实 `_time` None/数字）→ 本版 `cyqoesgx`（取代前两版）。

- **`PySelf.h` 新增 `scan_photo_unit(ubt, um)`**：扫 units_by_type 找类名含 "Photo" 的 PhotoUnit（键找到后缓存 `g_photo_key`，之后每轮只读这一个；没找到=非约瑟夫局，全扫节流 500ms；换局 um 变→作废）。读 `_time`→`g_photo_active`（数字=true/None=false）、读 `_players`→`g_photo_players[]`(uid 列表)。面板 `镜世界:` 显示 `key=.. _time=.. _players=.. active=..`。
- **门控**：`collect_units` 的 `add_body` 加 `if (!(is_mirror && !g_photo_active)) add_body(...)` —— 没拍照时镜像双胞胎不收进本体集合 → 绘制侧 1594 的 `!is_body` 跳过 → 方框/名字/距离/骨骼全不画。拍照后才收。
- **in_mirror 改走 `_players`**：`res.in_mirror = self_in_players(res.uid)`（我的 uid 在 PhotoUnit._players 里；实测进镜世界后 `_players` 0→1）。**删掉旧的读 anchor `in_photo_world`/`out_photo_uid`**（`g_i_self_inphotoworld`/`g_i_self_outphoto` 两个字段一并删）。这关闭了第四节的待办 #4（in_mirror 信号没验到真值）。
- **镜像绘制样式**（`draw_Gui.cpp` 主循环，`otherworld` 块）：① 方框默认画(白)、**不受 `show_draw_Rect` 开关控制**（`if(otherworld){画}else if(show_draw_Rect){…}`）；② 距离默认画（`show_draw_Distance || otherworld`）；③ **不画射线**（`&& !otherworld`）；④ 名字白(本就)、⑤ 天赋不画(本就 `!otherworld`)、⑥ 骨骼不画(第七节 `body_is_mirror`)。
- **对称**：我在主世界→镜像人白；我进镜世界(in_mirror)→主世界人白。骨骼只按 `body_is_mirror`(=镜像双胞胎)取消，与 in_mirror 无关（镜像永远是静止死物）。
- **上机要看**：面板 `镜世界:` ——开局没拍照应 `_time=none active=0`、此时镜像人全不画；拍照后 `_time=数字 active=1`、镜像人出白框+名字+距离、无射线无骨骼；我进相中世界 `_players` 该含我 uid、主世界人翻白。

## 九、★ 改为"按身份着色"模型（2026-10-22，产物 `rtkangdf.sh` -O1，编译通过，**未连未推未上机**）

用户否掉了第八节那套"按我所在世界翻转(is_other_world)"的逻辑，改成**按身份固定**，更合理。取代 `cyqoesgx`。

**最终规则（约瑟夫局 = 场上有 PhotoUnit，`PySelf::is_joseph_match()`）：**
- **镜像投影**（`body_is_mirror`，out_photo_uid>0）→ **永远白框**；不画骨骼/射线/天赋，画 白框+名字+距离。
- **真实求生者 → 永远绿框；真实监管(约瑟夫) → 永远红框**（不管谁在哪个世界）。
- **真人名字后缀**：该真人**自己**当前在镜世界(它的 uid ∈ `PhotoUnit._players`)→「镜像」，否则「现实」。投影不加后缀。
- **约瑟夫局永远画方框、永远不画骨骼**，无视 `show_draw_Rect`/`show_draw_Bones` 开关。
- **门控保留**：没拍照(`_time=None`)时投影不收进本体集合 → 全不画（第八节的闸）。

**实现要点：**
- `PySelf`：`scan_photo_unit` 另设 `g_photo_present`(有 PhotoUnit=约瑟夫局)；`Snapshot.body_in_photo[]`(每个真人 uid∈_players)；
  `collect_units` 收本体时读 `unit.uid`(`g_i_body_uid`)判 in_photo；新接口 `is_joseph_match()` / `body_in_photo_world(obj)`。
- `draw_Gui.cpp`：骨骼循环加 `&& !is_joseph_match()`(约瑟夫局整体不画骨骼)；主循环用 `joseph`+`echo`+`body_in_photo_world`
  取代 `otherworld`：方框 `if(joseph){投影白/监管红/求生绿,永远画}else if(show_draw_Rect){原逻辑}`、名字后缀、距离 `||echo`、天赋 `!echo`、射线 `!echo`；
  ShouldSkipEntity 放行 + 天赋HUD 过滤改用 `body_is_mirror`。`is_other_world` 仅剩骨骼色一处(约瑟夫局不跑、非约瑟夫无投影，无害)。
- **in_mirror(self) 现已基本不参与着色**(改按各单位自己的 in_photo)；只 is_other_world 还引用它，实际走不到。

**上机要看**：约瑟夫局 —— 投影全白框、求生者绿框、约瑟夫红框，名字带「镜像/现实」且随各人进出镜世界变；永远有框、永远无骨骼(拨开关无效)；没拍照时投影不出现。
**用户待验**：求生者视角、约瑟夫在另一个世界时，会不会出现第二个约瑟夫框(他的 another_model 灰模型理论上已被 `is_stale_model` 过滤，没专门验过)。

## 五、工具

- `逆向存档\_scripts\cmd_joseph.py`：约瑟夫局 probe2，dump ubt 键+数量 / `units_removed_but_model_by_type` /
  PhotoUnit.is_active+_players / 每个单位的 model + `in_photo*`/`out_photo_uid` + 名字含 photo/gray/model 的额外属性。
- `scratchpad\pyc_dis.py`（会随会话清掉，可重写）：Python 3.11 加载游戏 .pyc 读 co_names/co_consts，
  参数给方法名子串。记住 dis.dis 会崩，只用名字/常量。
- 静态全量脚本在 `逆向\第五人格_脚本解包_反作弊\all_pyc\`（见 SKILL.md 顶部）。
