---
name: esp-read-robustness
description: 给第五人格(或任何内存读取型 ESP/外挂)加两套"不随游戏热更失效"的工程地基——① 每条读取链的「每阶段失败诊断」(failure_stage/consecutive_failures/primary_reason,热更失效一眼定位断在哪环,不用从头逆);② 「domain 域选择 + 记录理由」(从多个候选 world/unit_manager 里选当前活跃的并记 selection_reason/uses_battle_world,根治"准备/大厅/局内分不开")。逆商业外挂 007(第五人格 ESP)§8.D 得来,是可直接照搬的 schema 和设计模式,跟具体偏移无关。要给 IdentityV ESP 加健壮性、或热更后维护读取链、或解决阶段判定混乱时读这个。配套 idv-reverse-resume、007 SKILL §7/§8.D、touch-inject-arbitration。
metadata:
  type: reference
---

# ESP 读取健壮性 —— 每阶段失败诊断 + domain 域选择(逆 007 得来)

> 来源:商业外挂 `007-free.sh`(第五人格 ESP,见 [[007-skill]] = `C:\Users\31297\Desktop\逆向\007\SKILL.md` §7/§8.D)。
> 2026-10-15 建。**这是跨功能、不随热更失效的工程地基,比任何单个游戏功能更值得抄。** 全是 schema + 设计模式,不含游戏偏移。

## 零、为什么这才是真·高价值
游戏功能(砸板/透视/治疗)会随热更偏移失效、要反复重逆;而这两套是**地基**:
- 失败诊断 → 热更一失效,**看一眼"断在哪阶段"就知道改哪**,不用从头逆整条链。
- domain 域选择 → 给"我现在在准备/大厅/局内/淘金"一个**权威判据**,叠加层按阶段切换该画什么,不再靠脆判据猜。

对应你 [[idv-reverse-resume]] 的两个长期痛点:热更维护成本、"准备/大厅/局内分不开"待办。

---

## 一、每阶段失败诊断(failure-stage instrumentation)

### 1.1 007 的完整 schema(六条读取链共用一套字段,直接照抄)
007 给 `camera` / `cooldown.flywheel` / `gold_rush.read` / `lobby_hunter` / `view` / `auto_skill.touch` **每条读取链**都挂同一套诊断字段:

| 字段族 | 键(007 原名) | 含义 |
|---|---|---|
| 阶段 | `stage` / `failure_stage` / `failure_stage_code` | 断在第几阶段(枚举 + 数字码) |
| 结果态 | `outcome` / `status` / `status_code` / `source_status` | 这次读取整体结果 |
| 原因 | `primary_reason` / `terminal_reason` | 主因 / 终因(两级) |
| 连续失败 | `consecutive_failures` | 连着失败几次(判"偶发 vs 真失效") |
| 失败对象 | `first_failed_object=0x…` | 第一个读失败的对象指针(直接拿去 devread 看) |
| 失败细节 | `failed_attribute` / `failed_operation` / `failed_axis` / `failed_x/y/z` / `failed_integer` / `failed_voxels` | 具体断在哪个属性/操作/坐标轴 |
| 探针 | `matrix_probe` | 关键中间值探针(相机那条用) |
| 计数 | `entry_count` / `invalid_count` / `truncated_count` | 读到几条 / 几条无效 / 截断几条 |
| 错误组 | `error_code` / `error_source` / `error_text` / `auxiliary_error_code` | 错误四元组(view 那条) |
| 尝试 | `tap_attempts` / `panel_tap_attempts` / `unavailable_attempts` | 尝试次数(自动化那条) |
| 新鲜度 | `positions_age_ms` / `update_age_ms` / `camera_age_ms` / `sample_age_ms` | 数据多久没更新了(判过期) |
| 代际 | `generation` / `snapshot_generation` / `domain_generation` / `runtime_epoch` | 按代判新旧,挤掉计 `*_dropped_publications` |

### 1.2 典型阶段划分(从键名反推一条读取链的"几环")
```
根指针 → unit_manager → 遍历 entries(entry_count/invalid/truncated)
      → 每对象属性(failed_attribute/failed_operation)
      → 坐标读(failed_x/y/z + failed_axis)
      → 发布快照(generation + *_dropped_publications)
```
失效时 `failure_stage` 落在哪一环,就知道是**根偏移变了**(stage=根)、**属性偏移变了**(stage=属性 + failed_attribute)、还是**只是这一帧对象没映射**(first_failed_object 指到 scudo 预留区)。

### 1.3 怎么套你的 read chain(设计模式)
- 每条链不要只回 `bool 成功/失败`,回一个 **diag 结构**:`{ stage枚举, primary_reason, consecutive_failures, first_failed_object, age_ms }`。
- 面板/日志展示这个 diag(007 能 `[Diagnostic] 导出文件`,你也可以写 `/sdcard`)。
- **对你的直接收益**:
  - 热更失效从"从头逆"变成"看 stage 定位一处"。
  - 配合你 SKILL 已记的教训——"[[android-re-toolkit]] §六:多值同时为 0 先查因果依赖,别当多处独立失效"——`failure_stage` 正是把"真正断在哪一处"显式化,从机制上避免那次"三个值全 0 以为三处全废、实际只坏一处"的误判。
  - `first_failed_object` 指针直接喂 `devread.py` 复查,省去猜。

---

## 二、domain 域选择 + 记录理由

### 2.1 007 的完整键(rodata 地址已定位)
| 键 | 地址 | 含义 |
|---|---|---|
| `domain.current_world=0x` | `0x38951` | 当前世界指针 |
| `domain.battle_world=0x` | `0x39f70` | 对局世界指针 |
| `domain.selected_world=0x` | `0x3b05d` | **最终选定**的世界 |
| `domain.selection_reason=` | `0x39aea` | ★ **为什么选它**(枚举,运行时码) |
| `domain.uses_battle_world=` | `0x405e0` | ★ bool:是不是对局世界 |
| `domain.current_world_type=` / `battle_world_type=` / `selected_world_type=` | `0x410d9`/`0x410f4`/`0x3ddd7` | 世界种类(枚举) |
| `domain.{battle,game_kernel,local,selected}_unit_manager=0x` | `0x3b076`/`0x3ddf3`/`0x3f14f`/`0x3f12f` | 四个候选 unit_manager + 选定的那个 |

(`=0x` 的是指针;`_type=` / `selection_reason=` / `uses_battle_world=` 是数字码,**枚举值→含义留动态确认**:hook 007 或自己打印。)

### 2.2 它解决你什么痛点
第五人格客户端同时存在**多个"世界/unit_manager"候选**(大厅 / 准备 / 对局 / 淘金),不同阶段活跃的不是同一个。你 [[idv-reverse-resume]] 的待办"准备/大厅/局内分不开"、以及 [[idv-replay-genius]] §573 被推翻过的旧说法("units_by_type 没玩家单位 ⇒ 读不到")——**根因都是没做这层世界选择,用脆判据猜阶段**。

007 的做法:**枚举所有候选 world/unit_manager → 按规则选一个当前活跃的(selected)→ 记录 selection_reason(为什么) + uses_battle_world(是不是对局)+ world_type(哪种世界)。**

> ⚠⚠ **对齐你的既定立场(别被带偏)**:[[idv-reverse-resume]] §(约837-878行)记着两条,照它来:
> 1. **你已明确否决"用 `world_type` 当阶段判据"** —— 有多个大厅、多个对局地图,这字段各不相同。所以 **007 的 `world_type` 那条不要照抄**,它只能当辅助信息,不能当权威阶段判据。
> 2. **"局内 vs 局外"你已经解决**(靠有没有 `units_by_type` 键 1/2),等价于 007 的 `uses_battle_world`,**这条你已有同款,不用再抄**。
> 3. **真正还没解决的只有"大厅 vs 准备"**。007 可能靠 `current_world` 指针 / 哪个 `unit_manager` 活跃(对象身份),而不是 `world_type` 来区分 —— **这正是动态时要确认的点**:看 007 在大厅 vs 准备两个阶段 `selected_unit_manager` / `current_world` 指针是不是不同对象。

### 2.3 设计模式(套你的读循环)
```
每轮扫描前,先做"选 world":
  1. 枚举候选 unit_manager:battle / game_kernel / local / selected
  2. 按有效性/优先级选一个当前活跃的 → selected_unit_manager
  3. 记 selection_reason（telemetry + 调试,失效时知道为什么选错了）
  4. uses_battle_world(bool) 区分"对局中 vs 非对局"
  5. world_type 标明当前阶段（对局/准备/淘金/大厅）
叠加层按阶段切换该画什么:
  - 对局(你已有的"键1/2存在"= uses_battle_world) → 画 ESP 坐标/骨骼/进度
  - 非对局 → 再分 大厅 vs 准备(这步你还没解,靠 selected_unit_manager/current_world 对象身份区分,动态确认)
  - 准备/选点阶段 → 画选点预览(见 [[007-skill]] §8 的 预览玩家1-4 / picker)
```
**收益**:把"选哪个 unit_manager + 为什么"显式化(selection_reason),叠加层在局内读不到对象时能区分"真偏移失效"vs"只是没选中活跃 world",不再误判。**注意**:权威判据用"对象身份/键存在性"(你现用的),`world_type` 只作辅助,别当判据(见上 ⚠⚠)。

---

## 三、落地优先级(建议)
1. **先上 domain 域选择** —— 受益最大最急,直接关掉"准备/大厅/局内分不开"这个长期待办。给读循环加"选 world + world_type"前置。
2. **再给每条 read chain 加 failure_stage/primary_reason/consecutive** —— 热更维护利器,一次加终身受益。
3. **枚举实际取值动态确认** —— `selection_reason`/`world_type`/`failure_stage` 的数字→含义,hook 007 或在你自己代码里打印对照。

## 四、复现
```bash
f="/c/Users/31297/Desktop/逆向/007/007-free.sh"
strings -n5 "$f" | grep -oE '[a-z_]+\.[a-z_.]*(stage|outcome|reason|status|failed[a-z_]*|consecutive|attempts|invalid|truncated|error[a-z_]*|probe|count)[a-z_]*=?' | sort -u   # 诊断 schema 全量
strings -n5 "$f" | grep -oE 'domain\.[a-z_]+'   # domain 全量
```
地址表见 §2.1;rodata 地址 == 文件偏移(见 [[007-skill]] §5.1)。IDA 库 `C:\ida007\s007.elf.i64`;字符串地址表 `C:\ida007\out_rodata.txt`。
