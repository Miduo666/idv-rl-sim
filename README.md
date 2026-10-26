# idv-rl-sim

第五人格（`com.netease.dwrg`）逆向资料 + 强化学习模拟器。私有仓库。

**主线（2026-10-24 起）**：游戏客户端的 `common_cs` 里带着服务端逻辑，还自带"本地服务端"模式（`MODE_CS`，新手局在手机上本地对 AI 跑完一局）。
在标准 CPython 3.11 里无引擎跑这套逻辑 → 自建 1v4 模拟器 → 强化学习。权威记录在 [`SKILL.md`](SKILL.md) **§9**。

## 目录

| 路径 | 内容 |
|---|---|
| `SKILL.md` | 本项目主档：脚本离线解包(§1–4)、反作弊静态分析(§5–7)、字节码还原 + 模拟器(§9，**从这里开始读**) |
| `drivers/sim/` | 模拟器：`simcore.py`(内核) / `sim1v4.py`(1v4 对局) / `run1v4.py`(入口) / `natives/`(引擎原生模块的 Python 替代) / `pseudo.py`(3.11 字节码→伪源码) 等，清单见 SKILL §9.2、§9.9 |
| `drivers/` | 解包、反混淆、交叉引用等脚本（顶部路径常量是当时的绝对路径，换机要改，见 SKILL §3） |
| `tools/` | 第三方解包工具（NeoXtractor-IDXWPK）与辅助脚本 |
| `analysis/` | 反作弊分析的文本产物 |
| `skills/` | 第五人格相关的其它 SKILL 快照（权威版本在本机 `~/.claude/skills/` 与 `逆向\` 下，这里是 2026-10-26 的副本） |
| `scripts/probe/` | 进程内探针 / 命令脚本（本机 `逆向存档\_scripts\` 的副本，去掉了内存转储 `.bin`、运行日志、pyc） |
| `scripts/pull_manifest.sh` | 从设备拉资源清单 `Documents/thd/`（SKILL §9.5.2） |
| `data/scene_classify.tsv` | 场景资源包全量分类结果（SKILL §9.5.1） |

### `skills/` 各是什么

| 目录 | 内容 | 与模拟器的关系 |
|---|---|---|
| `idv-replay-genius` | 录像文件(pickle)解析、天赋/辅助特质/技能冷却、`genius-table.md` 全表 | 编成配装、真人对局离线数据 |
| `idv-reverse-resume` | ESP/骨骼绘制的偏移与热更恢复流程、注入通道、设备标识调研 | 活体探针、资源导出时要用的注入与反作弊注意事项 |
| `esp-read-robustness` | 读取链分阶段诊断 + 世界域选择 | 无直接关系 |
| `touch-inject-arbitration` | 自动触摸注入的仲裁设计 | 无直接关系 |
| `android-re-toolkit` | 本机 adb/frida/IDA 工具链与通用坑 | 从设备拉资源时要用 |
| `007`、`tianshi-angel` | 两个商业外挂的拆解档案 | 无直接关系 |

## 没有入库的东西与复现

不入库：`all_pyc/`、`std_pyc/`、`extracted_scripts/`（游戏脚本）、`res_pull/`（地图碰撞/导航资源）、`intl_tid/`（国际服文本），以及 `drivers/sim/idx.tsv`。

1. 解包得到 `all_pyc/`：SKILL §4（apk 里的 `script.idx` + `script*.wpk`）。热更版脚本在设备 `res/script1.wpk`，最终要按文件覆盖（SKILL §9.5.1）。
2. 转成标准 3.11 pyc：`python -I drivers/sim/convert_all.py drivers/sim all_pyc std_pyc`（SKILL §9.1）。
3. 重建名字索引：`python drivers/sim/make_idx.py`（`idxq.py`、`usage.py` 依赖它；重建出的索引比旧版多收录一些长字符串，不影响查询）。
4. 地图资源 `res_pull/resdump_1025_015456/res_recovered.zip`：只能从设备进程内导出（SKILL §9.5.3–9.5.4，注入有封号风险）。
   设备场景包 `res_pull/scene_pkg/`（`scene.idx` + `scene2~5.wpk`，1.76GB）从设备拉（SKILL §9.5.1），里面有导出包缺的导航/tilecache（SKILL §9.10）。
5. 编译导航库（官方 Detour v1.6.0）：`python drivers/sim/natives/detour_c/build.py`，需要 git + g++（Windows 用 mingw）；源码拉到 `tools/_deps/`，产物在 `drivers/sim/natives/bin/`，都不入库。

## 脱敏

`skills/` 和 `scripts/` 里的账号 uid、Android ID(SSAID)、虚拟 IMEI/IMSI、UDID、`DeviceId` 已替换成 `<账号uid_A>`、`<SSAID_旧机>` 这类占位符；本机原文件未改。

## 协作约定

- 需要游戏处于特定状态的探针、注入、叠加层启动：写好脚本、给出命令，由使用者自己在合适时机运行。
- 新方向 / 设计选择先给结论和方案，确认后再写代码；只做点名的项，调研中的旁支发现记进 SKILL。
- 模拟器的垫片（服务端房间/单位接口）每条注明调用处与推断依据；推断不出的值不要编。

## 现状（2026-10-26，详见 SKILL §9.6、§9.10）

军工厂 1v4：1 监管 + 4 求生者都挂人机行为树、每帧在跑，整图交互物齐全。
- **碰撞层完成**：`drivers/sim/colworld.py`（numpy 碰撞内核）+ `natives/physx_collision.py`（接游戏 `CollisionManager`），射线/扫掠/静态测试/路径相交、过滤语义、球/盒子/胶囊三种形状都有调用处依据；自测 `t_colworld.py`、`t_physx.py`。
- **服务端模式 AI 孤岛完成**：`python run1v4.py 1 300 --server-ai`，人机 AI 走服务端完整逻辑。
- **导航层完成**：官方 Detour v1.6.0 接 `scene_detour`（`natives/detour.py`），自测 `t_detour.py`。普通导航与 tilecache 资源缺，暂回退到 AI 导航。
- **修机站位已重建**（共用层 `get_pos_for_ai`，录像旁证，SKILL §9.11）；**主循环补全**（`world.init()`、`move_relate_handle`，SKILL §9.12）：**5 个人机角色都能自主移动**，监管已在追人。
- **当前阻塞**：交互动画（修机/翻窗/踩板/救人）的根运动位移数据只在引擎动画资源里，方案待定（SKILL §9.12.3）。待办清单见 SKILL §9.6.3。之后才是 RL 动作/观测接口。

本机运行（Windows，`drivers\sim` 下，不要加 `-I`）：先 `python natives\detour_c\build.py`，再 `python t_detour.py`、`python run1v4.py 1 300 --server-ai`，完整命令见 SKILL §9.6.5。

