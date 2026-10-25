# 天使第五公益内核 — 逆向拆解存档

> 对象：别人做的第五人格公益外挂「天使第五」，用户要逆它学架构（同 007 / 若辰 的性质）。
> 分发目录：`C:\Users\31297\Desktop\逆向\天使第五公益内核\`。
> 本分析目录：`…\天使第五公益内核\_分析\`（我写的东西放这）；解包产物在 `…\_extract\`（不可信，隔离）。
> 首轮静态拆解日期：2026-10-22。**目前只做了静态字符串 + ELF 结构 triage，还没反编译任何函数。**

## 一、它是什么 / 怎么打包的

- 分发文件 `天使第五.sh`（35MB）= **makeself 风格 gzip 自解压脚本**。
  头部 `#!/system/bin/sh` + `CRC32=44`，载荷从第 44 行起 gzip 压缩。
  解包命令（已验证）：
  ```bash
  tail -n +44 "天使第五.sh" | gzip -cd > tianshi_main.bin
  ```
  运行时解到 `$TMPDIR/gztmpXXX`（默认 `/data/local/tmp/`）、chmod 777、执行、5 秒后删临时目录。
- 解出的 `tianshi_main.bin` = **91.6MB arm64 PIE ELF**（ET_DYN，`e_machine=0xB7`）。
  - `.text` 14.8MB，`.rodata` 27MB（大头是内嵌字体 + 各种静态库的只读数据）。
  - **完全 strip**：只有 `.dynsym`（~277 条），无 `.symtab`。函数名没了，要靠字符串 xref 定位。
  - 依赖：`liblog libandroid libEGL libGLESv3 libz libdl libm libc`。
    → **渲染走 OpenGL ES（libEGL/GLESv3）**，不是用户自己那套 Vulkan。
  - `.comment` 里混了伪造编译器串（`[AnGCC] by…`、`Pass01`、多个 clang 版本）——
    就是它宣传的「独家隐藏随机特征」混淆，别当真实编译信息。真实是 Android clang。

## 二、核心架构（静态证据）

### 1. LinYu 内核驱动（`.ko`）——「独家隐藏 / 无敌稳定」的真正底座

构建路径字符串 `/__w/LinYuDriver/LinYuDriver/src/core/linyu_supercalls.c`（`/__w/` = GitHub Actions CI）。
ELF 里**内嵌了多份预编译 `.ko`**，按运行内核版本挑一份加载，覆盖：
`5.10.252 / 5.10.245 / 5.15.202 / 5.15.202_android13_r00 / 6.1.166 / 6.6.127_4k / 6.12.52_4k / 6.12.76_4k`
（`_4k` = 4KB 页内核变体）。

驱动能力（从 `[LinYu]` 日志串逆出）：
- **内核级触摸注入**：hook evdev / `input_inject_event` / `input_event`（kprobe 或 fops inline hook 两种模式，
  `linyu_install_input_hook_fops` / kprobe mode），**MT-slot 预留**（`mtslot: need at least 2 slots`、
  `reserved slot is active`、`finger tracking initialized with dynamic buffers`）。
  → 触摸事件从**真实 input 子系统**发出，app 层分不出真假。这对应面板里「独家隐藏触摸 / 内核触摸」。
- **进程隐藏**：`hide_proc` + `filldir64 inline hook` + `release_task kprobe`
  → 把外挂进程从 `/proc` 目录遍历里抹掉。**这正面解决用户 2026-10-15 那个痛点**
  （网易反作弊扫 `/proc/<pid>` 发现外部读进程 → 弹「检测到修改客户端」）。
- **supercall 内存读写**：`linyu_supercall_work_fn` / `linyu_supercalls_init`，**劫持 syscall（见 `sys_ioctl`）
  做特权内存读写，不开 /dev 节点**（无节点 = 少一个被扫的特征）。
- **陀螺仪 hook**：`gyro: inline hook installed`。
- **ARM64 原生指令 patch 后端**：`ARM64 native instruction patch backend ready`
  → 可在内核里直接改游戏代码段（对应内存功能里「无视墙体 / 突破60FPS / 冲刺加速」那类）。
- **设备授权**：`linyu_device_auth_verify` + `auth_key`（**驱动自带设备级授权**，不是网络）。
- **ghost_region** 可执行内存分配器（`arm64_ghost_region_reserve/activate/sync_icache/destroy`，
  源 `src/debug/arm64_ghost_region.h`）——给注入的内核 shellcode 用的隐藏可执行区。

### 2. Embree（Intel 光追 BVH）——「PhysX 遮挡 / 碰撞」的真身

`.rodata` 里大量 Embree 符号（`tri_accel/quad_accel/builder/traverser/accel_mb/
max_leaf_size/instancing_block_size/subdivision surfaces/motion blur triangles…`）。
→ 它把地图几何建成**三角 BVH**，用**光线求交**做真·遮挡判定。
对应面板「模型骨骼遮挡变色 / 模型附近碰撞 / 模型准心碰撞 / PhysX 参数：附近范围·准心范围·
附近三角上限·准心三角上限」。**这就是用户 SKILL 里想要、若辰靠自建碰撞网格+射线做的那套——这里用的是 Embree。**

### 3. 渲染 / UI
- ImGui + OpenGL ES（EGL/GLESv3）。
- 内嵌 **FreeType**（海量 BDF/Type1/CFF/PostScript 字体串）——自带字库，对应「更换字体库」日志。
- 帧解码：lz4/zstd 相关串（`workSpace buffer is not large enough` 等）。

### 4. 玩法读取层（Python 对象图，和用户同一个游戏内嵌 CPython）
- RTTI 残留类名 **`CopycatIdentityRosterRow`** + 串 `copycat_index` / `copycat_indexcamp_id`
  → 模仿者身份用的是**和用户一样的 `copycat_index` / `identity_id` 路子**，自己维护一张身份簿
  （`CopycatIdentityRosterRow` 向量）= 用户的「身份簿锁存」。
- **出生区 / 区选（用户的未解待办！）**：字符串里有
  `UICustomBirthArea`（区选 UI）、`role_born_group` / `gen_born_group` / `cave_born_group` /
  `hook_born_group`（求生者/密码机/地窖/狂欢椅的出生点组）、`has_select`…
  → 它**能读到出生区选择**，字段就是这几个 `*_born_group`，挂在区域系统上。
- 大量地图/场景字段名：`front_door_name/state`、`side_door_floor_1/2_name/state`、
  `fullmap_doorway_x/z`、`fullmap_door_marker`、`fullmap_path`、`treasure_room`、`safe_room`、
  `basecamp_name`、`room_type`、`match_type`、`scene_flags`、`room_outline`、`UIInsidePersonaMap`、
  `UICustomBanPickSelect/Ob`、`UIMatchBan(Ob)`（禁选/ban-pick 阶段 UI）。
- 场景 prop 类名一大串（`prop_wz_*` 疑狂欢之椅系列道具、`prop_un_diaoxiang` 雕像、`monster_*` 摸金怪物等）。

### 5. 网络 / 设备指纹（与「无任何网络验证」宣称有出入，待证）
- `.rodata` 有 `POST /%s HTTP/1.1` + `Host: %s` + `application/x-www-form-urlencoded` +
  `User-Agent: Mozilla/4.0(compatible)`，导入表有 `socket`。→ **有 HTTP POST 能力**。
- 紧邻一堆硬件指纹读取：`/sys/class/mmc_host/mmc0/mmc0:0001/cid`（eMMC CID）、
  `/sys/block/mmcblk0/device/cid`、`/sys/class/scsi_device/.../serial`、
  `/proc/device-tree/serial-number`、`/sys/firmware/devicetree/base/chosen/serial-number`。
- 面板有「显示卡密剩余时间 / 删除卡密」。→ **存在卡密 + 设备指纹机制**；可能是统计、投屏（「投屏电脑」）
  或设备绑定授权。**是不是真「无网络验证」要反编译 POST 调用点才能下结论**，先别替它背书。

## 三、对用户自己工具的价值（按价值排序）

1. **进程隐藏对抗 /proc 检测**（filldir64 hook）——用户最大痛点的现成解法。
2. **出生区 / 区选数据**（`*_born_group` + `UICustomBirthArea`）——用户的未解待办，这里直接给了字段名。
3. **内核触摸注入 + MT-slot 预留**——比用户 uinput 方案干净（见 skill `touch-inject-arbitration`）。
4. **Embree 做真遮挡**——用户的遮挡/骨骼变色待办。
5. **supercall 无 /dev 内存读**——又一条反检测读内存通道。

## 四、复现 / 工具

- 解包：见第一节 `tail -n +44 | gzip -cd`。
- 字符串全集：`llvm-strings -n 5 tianshi_main.bin`（437k 行，本轮导到 scratchpad 分析，未长期落盘）。
- llvm 工具：`E:\android-ndk-r27d-windows\android-ndk-r27d\toolchains\llvm\prebuilt\windows-x86_64\bin\`。
- 深挖反编译：REA MCP（`open_binary` 这个 91MB 的 `_extract\tianshi_main.bin`）按字符串 xref 定位函数，
  或 IDA（`C:\Users\31297\Desktop\IDA Pro 8.3\idat64.exe`，91MB 全量分析要很久，建议只分析目标函数）。

## 四点五、区选 / 出生点读取链（2026-10-22 深挖，静态坐实）

**结论：出生区选择是客户端可见的，挂在房间/对局对象上，字段就是一张 10 项反射表。**

- 解包二进制 file offset == VA（.rodata/.text/.data 都是 off==vaddr），方便定位。
- `role_born_group` 等不是 ADRP 直接引用，而是 **`.data` 里的 `const char*` 全局**，
  由 `.rela.dyn` 的 `R_AARCH64_RELATIVE`(type 0x403) 在加载时把 .rodata 字符串 VA 写进槽位。
- **房间元数据反射表**：`.data` 槽 `0x2f4f048` 起、连续 10 项 `const char*`，前后干净（就这 10 个）：

  | 槽位 VA | 字段名 | 含义 |
  |---|---|---|
  | 0x2f4f048 | `role_born_group` | **求生者出生点组 = 区选结果** |
  | 0x2f4f050 | `cave_born_group` | 地窖出生点组 |
  | 0x2f4f058 | `guuid` | 对局/房间 guuid |
  | 0x2f4f060 | `gen_born_group` | 密码机出生点组 |
  | 0x2f4f068 | `hook_born_group` | 狂欢椅出生点组 |
  | 0x2f4f070 | `match_type` | 匹配类型 |
  | 0x2f4f078 | `room_type` | 房间类型 |
  | 0x2f4f080 | `scene_id` | 地图 ID |
  | 0x2f4f088 | `rain_flag` | 雨天标志 |
  | 0x2f4f090 | `night_flag` | 夜晚标志 |

- 这 10 个字段是**同一对象的属性**（guuid/match_type/room_type/scene_id/rain/night 都是房间/世界级元数据），
  所以 `*_born_group` 也是**房间对象的属性**，不是 region_mgr（RegionManager 是局内的）。
- 配套读取的 UI 面板表（`.data` 槽 0x57482c0 起）：`UIMatchBan`/`UIMatchBanOb`/`UICustomBanPick`/
  `UICustomBanPickOb`/`UICustomBanPickSelect`/**`UICustomBirthArea`**/`UIInsidePersonaMap`/
  `UICharacterSelectPanel`，加通用控件名 `btn/button/item_btn/skill_btn/node/root_node/skill_item`
  （它遍历 UI 节点树取按钮）。→ **区选界面 = `UICustomBirthArea`**。

**对用户的直接价值（接 [[idv-reverse-resume]] 那条未解待办「出生点/区域选择」）**：
用户之前只扫了 `UIRoomWait` 顶层属性和 `cur_world`（WorldMatchRoom 无 region_mgr），没命中。
这个工具证明数据在客户端，**应该去读房间/对局对象上名为 `role_born_group`/`gen_born_group`/
`cave_born_group`/`hook_born_group` 的属性**（和 guuid/match_type/room_type/scene_id/rain_flag/night_flag
同对象），以及 `UICustomBirthArea` 面板。下次用 probe2 直接按这些名字 getattr 验证即可。
（没继续反编译出精确读取函数：该 const char* 表被寄存器索引遍历 + 走 get_attr，
页 0x2f4f000 同时是个大全局配置块、立即数 LDR 对不上，再挖性价比低。字段名+源对象已足够指路。）

## 四点六、UICustomBirthArea 真实数据模型（2026-10-22，从游戏 pyc 源反出）

天使只按名字读 `role_born_group`/`UICustomBirthArea`，但**没读真正的选点数据**。真模型从游戏脚本源反出
（`桌面\逆向\第五人格_脚本解包_反作弊\all_pyc\` 的 `entities/logic/BanLogic.pyc` + `ui/UICustomBirthArea.pyc`，
本机 Python311 `marshal.loads(data[16:])` 反序列化、`dis`/walk co_consts 提结构，脚本在本会话 scratchpad）：

- **`UICustomBirthArea`**（csb `ui/dm65ui/res/custom_birth_area.csb`）= 区域选择面板。做的事：
  地图图 + 可点格子（`gen_area_item`/`area_item_dict`/`on_area_item_click`→`on_select_zone`，四角 world 坐标
  `left_up_pos`… 从 `scene_config`+`birth_point_area_info` 来，按 `map_z_flag`/`map_rot_angle` 旋转适配充电口方向）；
  求生者列表 `update_c_chars`(CharList) + 监管 `update_b_chars`/`update_hunter_item`(CharListHunter)，含头像/名字/皮肤/特质；
  阶段驱动 `update_stage`/`update_view`，倒计时 `update_left_times`；点击 `on_click_area_item`→`on_select_zone`→
  `call_soul_method('bp_civilian_select_zone'/'bp_butcher_select_zone', slc_zid)` 上报服务器，确认走 `bp_*_confirm_zone`；
  画别人选点 `update_c_frame_items`/`update_b_frame_items`（`process_frame_item` 分 `img_face_bg_mine`/`_other`）；
  换区 `on_swap_zone_*`；预知 `check_civilian_pre_know_butcher`。**所有数据取自 `GK.g_avatar.get_ban_info()['info']`。**
- **数据模型**见 skill `idv-reverse-resume` 的「出生点/区域选择」节（已写入）：`ban_info['info']` 下
  `civilian_select_zone_dct`（求生者选点 pid→区id）/`butcher_select_zone_dct`/`*_confirm_zone_dct`/`civilian_swap_zone_dct`，
  阶段 `bp_stage`∈{CIVILIAN_PICK_AREA,BUTCHER_PICK_AREA,CONFIRM_PICK_AREA}。服务器 RPC `on_other_select_zone`
  → `update_ban_info` 合并，客户端不按角色过滤。
- **天使没读这些**（二进制 0 处引用 `select_zone_dct`/`ban_info`/`bp_stage`）→ 它的"区选信息" ≠ 监管盲选窗口内的实时选点，
  只是 `role_born_group` 进局出生组。**能不能真做到取决于服务器在 CIVILIAN_PICK_AREA 是否给监管端下发 civilian_select_zone_dct（A/B），只有活体能定，设计指向 B=不下发）。**

## 五、下一步（待定方向，等用户选）

候选深挖线（都要 REA 反编译对应函数）：
- A. 出生区读取链：xref `role_born_group`/`UICustomBirthArea` → 反推它从哪个对象读、怎么映射 3x4 格子。
- B. LinYu 驱动 supercall/touch/hide 的用户态调用约定：xref `[LinYu]`/`supercall` → 看 ioctl 魔数和命令结构。
- C. Embree 遮挡：xref PhysX 参数串 → 看它怎么喂几何、怎么发射线。
- D. 把内嵌的多份 `.ko` 抠出来单独逆（驱动本体）。
- E. POST 调用点 → 坐实有没有网络验证 / 投屏是什么协议。
