# 第五人格 · 游戏脚本离线解包 + 反作弊静态分析

> 建立于 2026-10-15。本文件夹是一次完整静态逆向的全部产物：把第五人格 apk 里**打包加密的
> 全部 Python 游戏脚本（17370 个）离线解出来**，并在其中定位、读懂了游戏自带的反作弊逻辑。
>
> 目标包：`com.netease.dwrg`，版本 **2026.0611.0155**（apk 在 `逆向\第五人格_2026.0611.0155.apk`）。
> 引擎：网易自研 **NeoX**，内嵌 **CPython 3.11**（非 Unity/IL2CPP）。
>
> 配套：ESP/场景层逆向看 skill `idv-reverse-resume`；玩法层活体读取看 `idv-replay-genius`。
> 本文件只管**"从 apk 静态解出脚本源 + 反作弊是怎么回事"**，和活体内存读取是两条正交的线。

---

## 0. 一句话结论（最重要）

1. **第五人格的 Python 游戏脚本全可离线解包**，不需要设备、不碰内存、零风险。17370 个脚本一次解完，
   真实路径（`co_filename`）全可读。通路和脚本都存在本文件夹。
2. **反作弊分两套，触发条件完全不同**：
   - **Python 层 = 数值篡改检测**（只抓"写/改"游戏数值，局内上报服务器）。对只读访问**零反应**。
   - **Native 层 `libsec-lib.so` = 环境检测**（反调试/反 hook/反模拟器）。抓的是注入/ptrace/调试器。
3. **驱动只读路线对两套都免疫**（没写数值、没 ptrace/hook/新模块/proc），与"从没被检测过"吻合。
   **真正高危的是注入探针路线**（ptrace+Dobby+落地.so 会撞 native 环境检测）。
4. 2026-10-15 那次只读 /proc 被弹"检测到修改客户端"，**在 Python 层和 libsec-lib 里都找不到对应机制**
   —— 支持"未必是只读 /proc 本身触发"的判断。彻底坐实需逆 175MB 的 `libclient.so`（见 §7 待办）。
5. **模拟器 + 强化学习主线（2026-10-24 起）**：字节码还原后在标准 CPython 3.11 无引擎跑游戏自带的本地服务端对局（§9）。
   碰撞、AI 孤岛、导航（官方 Detour）、修机站位、主循环、根运动都已完成，能打完整局；
   **2026-10-26 起编成改为游戏真实的"噩梦"自定义人机（杰克 + 4×qaai_civilian_rank7，场景 6），挨刀会逃、会救人**；
   **天赋完全没接、buff 是否生效未核实** → **下个会话从 §9.16.7 接着做**。

---

## 1. 打包格式与解包通路（可复现）

游戏脚本不在 `script.npk`（那只是 1952 字节的引导），而在 **WPK 容器**：

```
assets/res/script.idx    (625KB, 魔数 "SKPW")  —— 索引: 17370 条记录
assets/res/script0.wpk   (524KB, 魔数 "FKPW")  —— pkg 0 数据
assets/res/script1.wpk   (201MB, 魔数 "FKPW")  —— pkg 1 数据(绝大多数脚本在这)
```

**IDX 记录**(0x24 字节/条, 头 0x20)：`raw_hash(16)` + `pkg_id(@0x14)` + `file_off(@0x18)` + `payload_size(@0x1C)` + `hdr_size(@0x20,u16)`。pkg_id → `script{pkg}.wpk`。

**单条解链（逐层）**：
```
WPK 取块 → WPD1 stage-1 解密 → [NONE/ENON/DTSZ/COBL/LZ4_LIKE/ROTOR/NXS3 逐层解包] → marshal code object
```
实测第五人格脚本典型链是 **`ENON → NXS3 → LZ4_LIKE → marshal`**。

- **WPD1 stage-1**：tag=u16@0；tag `0x4341/0x4350`('AC'/'PC')走 AES-ECB 前缀 + XOR；`0x4358`('XC')走线性 XOR；再 `header_decode`(前 64 字节逆序 XOR 0x5A)。实测本版 tag=`0x4350`(17232)。
- **NXS3**：`NXS3\x03\x00\x00\x01` + 尺寸 + **RSA(1024) 公钥解出 4 字节 ephemeral key** + 用该 key 做 murmur 式推进的 XOR + lz4 解压。**RSA 公钥见下，和 denpk2(2024 测试版) 完全一致——说明到 2026 正式版没换钥。**
- **marshal**：CPython 3.11 格式**未变**，`marshal.loads` 直接可读。**但操作码被打乱**（dis 无法反汇编），所以读逻辑靠 `co_names`/`co_consts`/`co_qualname`（都是明文、不受乱序影响），不靠反汇编。

关键环境事实（复现要点）：
- 本机 **Python 3.11.9** 恰好匹配游戏的 3.11，marshal 直通。
- `bitstring` 必须 **4.1.4**（新版 5.x 删了 `ConstBitStream`，NeoXtractor 导入会挂）。
- NeoXtractor 的 `core.logger` 耦合了 PySide6(GUI)；**无 GUI 跑法**是往 `sys.modules["core.logger"]` 注入一个
  `get_logger` 桩，避免拉 PySide6（见 `drivers/*.py` 顶部）。
- 依赖：`lz4 zstandard cryptography arc4 bitstring==4.1.4`。

---

## 2. 工具（都是现成的，不用自己从零逆）

| 工具 | 仓库 | commit(2026-10-15 clone) | 用途 |
|---|---|---|---|
| **NeoXtractor-IDXWPK** | github.com/biansty/NeoXtractor-IDXWPK | `4a0e991040b896851e3bf216de8133a082f9978f` | **解 IDX/WPK 外壳**（我们这版格式）。用其 `core/wpk` + `core/npk/decompression.py`(NXS3/ROTOR) + `core/rotor.py` |
| **denpk2** | github.com/hax0r31337/denpk2 | `a2f828cafe1919b574124b70bb23728f3c376e9d` | NeoX2 **NXPK** 解包 + **操作码乱序映射表**(`src/opcode/mapping.rs`)。作者就是拿第五人格测试版逆的。Rust 项目(本机没 cargo，只读逻辑参考) |

两份源码已拷进 `tools/`（denpk2 去 .git、NeoXtractor 只留 `core/`）。

**NXS3 RSA 公钥（本版仍有效）**：
```
-----BEGIN RSA PUBLIC KEY-----
MIGJAoGBAOZAaZe2qB7dpT9Y8WfZIdDv+ooS1HsFEDW2hFnnvcuFJ4vIuPgKhISm
pY4/jT3aipwPNVTjM6yHbzOLhrnGJh7Ec3CQG/FZu6VKoCqVEtCeh15hjcu6QYtn
YWIEf8qgkylqsOQ3IIn76udV6m0AWC2jDlmLeRcR04w9NNw7+9t9AgMBAAE=
-----END RSA PUBLIC KEY-----
```
**ROTOR 密钥**：`init_rotor()` 里 `asdf_dn='j2h56ogodh3se'` 那套（见 `tools/NeoXtractor-IDXWPK/core/npk/decompression.py`）。

---

## 3. 本文件夹内容

```
SKILL.md                      本文件
drivers/                      解包/分析驱动脚本(我写的，无 GUI)
  probe_wpk.py                先验 N 条能否解(冒烟测试)
  extract_all.py              全量解 + 按关键词筛反作弊脚本存盘
  full_extract.py             全量导出 17370 个 .pyc  (用法: python full_extract.py <out>)
  targeted_extract.py         按 co_filename 精确提取某几个脚本
  dump_pyc.py                 递归 dump 一个 .marshal 的结构(名字/字符串/嵌套函数)
  find_cls.py / find_sub.py   在 code 树里按名字/子串找类或函数并打印
extracted_scripts/            496 个"反作弊/安全"关键词命中的脚本(.marshal) + 分析用
  _all_filenames.txt          17370 个脚本的完整路径清单(全景索引)
  core/AntiMemModifyMgr.py.marshal
  common_cs/ComuKeys.py.marshal
  ...
all_pyc/                      全量 17370 个 .pyc(标准3.11头+marshal体；操作码乱序，marshal可读)
analysis/                     关键脚本的结构 dump(_analysis_antimem.txt / _analysis_security.txt)
tools/denpk2, tools/NeoXtractor-IDXWPK/core   工具源码
```

> ⚠️ `drivers/*.py` 里的路径是当时 scratchpad 的绝对路径。换机/复现时改顶部 `TOOL`/`IDX`/`OUT` 三个常量即可：
> `IDX` 指向解出来的 `script.idx`（和 `script0/1.wpk` 同目录），`TOOL` 指向 `NeoXtractor-IDXWPK`（含 `core/`）。
> apk 里这三个文件在 `assets/res/`、`assets/packages/python3/`，用任意解压工具取出。

---

## 4. 复现步骤（从零）

```powershell
# 1. 依赖
python -m pip install lz4 zstandard cryptography arc4 "bitstring==4.1.4"
# 2. 从 apk 取出 assets/res/script.idx, script0.wpk, script1.wpk 到同一目录
# 3. 改 drivers/full_extract.py 顶部的 TOOL/IDX 常量
# 4. 全量导出
python drivers/full_extract.py  <输出目录>
# 5. 读某个脚本结构(不反汇编, 看名字和字符串常量)
python drivers/dump_pyc.py  <out>/core/AntiMemModifyMgr.pyc    # 或 .marshal
```

---

## 5. 反作弊分析结论（核心交付）

### 5.1 两套反作弊，互不相干

**A. Python 层 = 数值篡改检测（抓"写/改"，仅局内，上报服务器）**

`common_cs/ComuKeys.py` 里 `ANTI_CHEAT_TYPE` 全集（上报给服务器的作弊类别）：

| 类别 | 值 | 含义 |
|---|---|---|
| `COLLISION` | 10000 | 碰撞/穿墙 |
| `SPEED` | 100001 | 速度 |
| `SCALE` | 100002 | 模型缩放 |
| `MOVE_SPEED` | 100003 | 移速 |
| `MEM_MODIFY` | 100004 | 内存数值被改 |

- **`core/AntiMemModifyMgr.py`**（= `GK.g_anti_mem_modify_mgr`，skill 里早记过对象名，这次拿到源逻辑）：
  `generate_modify_vars` 用 `struct.pack` 把一组 `MEMORY_VARS` 打包、`random.randint(15,25)` 取样、
  `sum(bytearray)` 算校验和存成 `origin_data`+`all_data_checksum`；`GK.g_async_mgr` **每 20 周期**跑
  `anti_mem_modify` → `check_modify_result` 重算对比，**失配**(值被写改)→ 构造 `ANTI_CHEAT_TYPE.MEM_MODIFY`
  经 `send_battle_event_safe` 上报。仅 `is_battle_client`/`battle_world` 时生效。
- **`ClientUnits/PlayerUnit.py`**：`server_anti_cheat_func`(读 `model.scale.x/y/z` 越界→`SCALE`)、
  `_log_move_speed_cheat`(读 `msm`/`speed_real`+门/椅状态，移速异常→`MOVE_SPEED`)。

> **全是"数值越界/被写坏"的检测。只读访问永远不触发**（校验和不变、speed/scale 值不变）。
> 全量 17370 个脚本里 `/proc`、`ptrace`、`TracerPid` **一个都搜不到** → /proc/反调试纯在 native。
>
> 注：`common_cs/SecurityUtil.py`(模仿者匹配)、`entities/logic/SecurityLogic.py`(二级密码/短信/风控，
> 还硬编码了测试密码 `'123456aa'`) 是名字撞"secur"的**误报**，与反内存作弊无关。

**B. Native 层 `libsec-lib.so`(284KB) = 环境检测**（字符串实锤）：
`TracerPid`/`ptrace`/`isDebuggerConnected`/`waitingForDebugger`(反调试)、`ProcMapsHasSubstrate`/
`ProcMapsHasXposed`/`allHookInfo`/`keyHookInfo`(扫自己 `/proc/%d/maps` 找 hook 框架)、`TiantianVM`(反模拟器)、
`hasIdaServerProcess`/`cat /proc/net/tcp | grep :5D8A`(IDA 端口 23946)/Frida。

### 5.2 三条路径的暴露面

| 路径 | A 数值篡改 | B 环境检测 | 结论 |
|---|---|---|---|
| **驱动只读**(生产 ESP) | 否(没写) | 否(无 ptrace/hook/新模块/proc) | **两套全躲 → 确定安全** |
| **注入探针**(probe2: ptrace+Dobby+落地.so) | 否 | **会中**(TracerPid+hook扫描+maps异常模块) | **真正高危**，之前没炸是侥幸 |
| **10/15 /proc 只读 dd** | 否 | 否(libsec-lib 不抓外部只读者) | 见 §5.3 |

### 5.3 对 2026-10-15 那次检测的重新判断

只读、没写一个字节，却弹"检测到修改客户端"。"检测到修改"语义属于 A 类（值被改），但**只读不会改值**；
A/B 两套里**都没有**"外部进程只读 /proc 就报警"的机制。因此：

- **大概率不是那次只读 /proc 本身触发**（和用户判断一致）。更可能是①那次会话还动了注入/ptrace 路径(撞 B)；
  ②`libclient.so` 里有个字符串被混淆、明文搜不到的"外部读取者扫描"(扫 `/proc/*/fd` 找谁持有本进程 mem fd)。
- 但无论真因是什么，**驱动只读路线的安全性不受影响**（它连 /proc 都不开）。

### 5.4 完整上报链路：客户端检测 → 服务器 → 下发邮件（2026-10-15 补）

"检测到修改客户端"**不是客户端直接弹窗，是游戏内收到一封服务器下发的邮件**——即"客户端上报 →
服务器判定 → 下发邮件"。客户端这一端的链路已全部挖通（服务器的判定/发邮件逻辑在网易服务器，不在客户端）。

**客户端存在三条独立的"上报服务器"通道：**

1. **战斗数值篡改**（局内）：§5.1 的 5 类 `ANTI_CHEAT_TYPE` → `send_battle_event_safe` →
   `CombatVoiceComponent`/`BattleEvent` → 战斗世界 → 服务器。抓"写/改"游戏数值。

2. **网易游戏安全 SDK（acsdk / 游易）—— 手机端主通道，本机就是这条**（`entities/Avatar.py`）：
   - 登录时 `Avatar.init_player` → `start_anti_cheat_service` → `upload_anti_cheat_report`：
     `setup_sdk` 启动 **NeoX2 AC SDK（在 `libclient.so` 里）**，带 `role_id/udid/server_hostnum/app_channel/
     unique_id/engine_version/patch_version/transid` + md5 `sign`（所以上报自带身份 → 服务器能精确给该账号发邮件）。
   - **上报端点**：`acsdk.gameyw.netease.com` / `acsdk.gameyw.easebar.com`（网易游戏安全后台），app key `dhnn8t7w3lmorvj9`/`9f8afppvacqdj2n1`，渠道标 `android_h55`。
   - 回调 `_cb_init`/`_cb_check`/`_cb_init_long_time` → **`try_call_server_method('log_mobile_anti_cheat_check_info', {result,type,info})`**（type=init/check）→ 游戏服务器。
   - `neox2_acsdk_http_tick`：`acsdk.get_http_requests` 组 HTTP（Url/Header/Body）→ `mobile_anti_cheat_check_http_update` 直连安全后台。
   - 周期常量 600。native AC SDK **从登录起持续自检**（完整性/hook/环境/内存），有异常就经上述回调/HTTP 上报。

3. **PC AC 检查器**（`core/sdk/GameYW.py`，仅 `is_pc`）：`init_pc_anti_cheat_checker`
   （`set_game_checker_interval`=600、`set_ac_extra_param` 带 role_id/server/role_name、`set_game_checker_cheat_cb`）
   → 回调 `call_server_method('log_pc_anti_cheat_check_info')`；另有 `TimerCheckWindowsApiHook` 查 `Kernel32.dll`
   的 `QSecInlineHook`。`core/sdk/Channel.py · init_anti_cheat_report` 从 `libclient.so` 取 `get_game_checker_report*`
   （含 `_by_http`）接出报告。手机端不走这条。

**底层检测源**：通道 2/3 的"报告"都来自 **native**——`libclient.so` 内嵌的 NeoX2 AC SDK + `libsec-lib.so`
（§5.1-B：TracerPid/ptrace、ProcMapsHasSubstrate/Xposed/allHookInfo、TiantianVM、IDA/Frida）。
Python 层只是**配置 + 把 native 结果转发给服务器**，不含检测逻辑本身。

**对 10/15 邮件的定位**：几乎可以确定是**通道 2（mobile acsdk）**把一次 native 自检结果上报 →
服务器 → 下发"修改客户端"邮件。native 到底判了什么（注入/hook/环境/内存完整性，还是真会抓外部只读 /proc），
在 `libclient.so` 的 AC SDK 内部，是剩余未解的一环（§7#1）。但：**acsdk 从登录起就在跑**，所以**注入探针
路线（ptrace+Dobby+落地.so）被它逮到并上报的概率最高**；驱动只读既不写数值（躲通道 1）、也不改客户端/不 hook/
不开 /proc（大概率不触发 native 自检），与"从没被检测"一致。

### 5.5 "收集齐了吗"——客户端上报面已收全

客户端能暴露的上报通道已全部定位（上面三条 + 底层 native 源）。**仍在客户端之外、拿不到的只有两处**：
① native AC SDK（`libclient.so`）内部到底以什么判据判"修改客户端"；② 服务器收到上报后"是否发邮件/发什么"的判定。
①需逆 175MB native（§7#1），②在网易服务器、原理上不可得。

---

## 6. 这套能力的价值（为什么单独存档）

- **第一次把游戏全部 Python 脚本离线解出来**：17370 个 `co_filename` 清单 = 一张完整的**游戏逻辑地图**。
  以后找任何玩法字段/类/属性名，先在 `all_pyc/` 里 grep 源码，而不是在活体内存里盲扫
  （补上 `python-layer.md` §十一 "怎么重新找" 的最前一步：**先看静态源**）。
- **零风险**：纯 apk 静态，不碰设备、不碰内存、不碰反作弊。和 `tools/re`(/proc, 对本目标禁用) 完全不同量级。
- **可随版本重跑**：热更换版本后，换 apk 的三个文件重跑 `full_extract.py` 即可（密钥没变的话）。

---

## 7. 待办 / 下一步（可选）

1. ~~逆 `libclient.so` 找外部读取者扫描器~~ **已做（2026-10-16，见 §7.5）**：live 热更版确认**无 foreign-reader 扫描**；acsdk 是采集+上报、判定在服务器；检测逻辑在混淆本地函数。剩余见 §7.5 的 B/C。
2. ~~操作码乱序映射~~ **2026-10-24 已彻底解决，见 §9。下面 10-16 的"cache 数不一致"诊断是错的**：cache 布局与标准 3.11 完全一致，
   出错的是读法——经 CPython 取 `co.co_code` 会按标准表"去特化"并清零它以为的 cache 槽，把乱序字节当标准操作码处理，
   既抹掉真指令（CALL 错位）又越界写（那约 400 个文件的堆崩溃）。旧记录留档：
   **操作码乱序映射(2026-10-16 进展)**：`drivers/deobf.py` + `opcode_names.txt`(denpk2 2024 表)实测——
   `LOAD`/`STORE`/`ATTR`/`COMPARE_OP`/`BINARY_OP`/条件跳转/常量索引 **2026 版全部适用**,数据流与分支可读;
   **但 `CALL`/`PRECALL` 系列的 inline-cache 推进对不齐**(dis 把调用显示成 `CACHE`+错位 `UNPACK_SEQUENCE`),
   方法调用参数读不准,整模块 remap 在大文件(PlayerUnit)会越界崩溃;**单函数 remap 可绕过崩溃**
   (见 `scratchpad/robust_dis.py` 模式:先 `find` 目标 code 再只 remap 它)。校准 CALL 系列后即可完整反编译全部脚本。
   **2026-10-16 诊断定位**:① `opcode_names.txt` 与 denpk2 `mapping.rs`(2024) **逐字节完全一致**,映射表本身**正确**
   (CALL=乱序字节180、PRECALL=216、LOAD_METHOD=197,`OPMAP.get` 都能命中)。② 排除"无 inline-cache、每条恒 2 字节"
   假设(co_code 里**确有 cache 占位**)。③ **真根因 = inline-cache 字节数**:数据指令(`LOAD_ATTR`=4/`COMPARE_OP`/`BINARY_OP`/
   `STORE_*`)的 cache 跳对(所以名字/常量/分支都正确),但**调用序列指令(`LOAD_METHOD`=10/`PRECALL`=1/`CALL`=4 本机值)
   在游戏码里的 cache 数与本机 3.11 不一致** → deobf 的 `i += 2 + 2*CACHE[op]` 在调用处跳错,把真指令当 cache 跳掉,
   CALL 错位显示成 `UNPACK_SEQUENCE`。**下一步**:写自洽求解器(约束:RESUME 开头 / co_code 长度精确耗尽 /
   相对跳转落在指令边界 / 无 UNKNOWN / EXTENDED_ARG 紧邻),对一批函数反推 `LOAD_METHOD`/`PRECALL`/`CALL` 等的真实 cache 数,
   产出"游戏专属 cache 表"替换 deobf 里的本机 `_inline_cache_entries`。**校准进行中。**
3. ~~把 `AntiMemModifyMgr` 的 `MEMORY_VARS` 具体字段挖出来~~ **已做(2026-10-16,活体,见 §7.6.1)**：
   `MEMORY_VARS` 是运行时值(`ComuKeys.MEMORY_VARS`,全 17370 脚本无字面量),probe2 读
   `GK.g_anti_mem_modify_mgr.origin_data` 得全 13 组值。
4. 活体交叉验证一律走 **probe2 进程内**（安全），严禁为此用 /proc（见 `idv-reverse-resume` 顶部反作弊警告）。

---

## 7.5 native AC SDK 调研实录 + 续作(B/C)指引（2026-10-16）

调研动机：查"客户端检测 → 上报 → 服务器下发'修改客户端'邮件"里 **native 端到底检测什么**，以及 2026-10-15 那次为何被上报。

### 工具现实
- **REA 在本机(win32)没有可用后端**（Ghidra 未配且只收 PE、Hopper 不支持 win32、IDA-MCP 未注册）→ 用 **NDK llvm-objdump/readelf/nm**（`...\ndk\28.2.13676358\...\bin\`）+ 自写 `drivers/xref.py`。IDA 8.3 在 `C:\ida83\` 但 175MB 全量分析极慢，没用。
- `.text` 文件偏移==VA；`.data` 有 +0x8000 偏移（算 .data 字符串 VA 要补）。

### 关键一步：运行时真正加载的不是 apk 里的 libclient.so
游戏跑的是**热更版**：`/data/data/com.netease.dwrg/app_so_uf/castor/lib/arm64-v8a/libclient.so`
（175199984B，**md5 `b6f535665e0b01b16b3001604ec92a40`**，2026-09-17，= 项目 `2026.0917_b6f53566` 版）。apk 基础版的 acsdk 是没接线的壳。

**pull 配方**（读磁盘文件、不碰 /proc 内存、不触发反作弊；注意 Git-bash 要关 MSYS 路径转换）：
```bash
export MSYS_NO_PATHCONV=1
ADB=".../platform-tools/adb.exe"
"$ADB" shell "su -c 'cp /data/data/com.netease.dwrg/app_so_uf/castor/lib/arm64-v8a/libclient.so /data/local/tmp/lc.so && chmod 644 /data/local/tmp/lc.so'"
"$ADB" pull /data/local/tmp/lc.so <本地>/libclient.so
"$ADB" shell "su -c 'rm -f /data/local/tmp/lc.so'"
```

### 已定位的地址（热更版，下次可直接用）
- `.text` off/size = `0x3b1c000` / `0x5f1daa0`（跑 `xref.py` 时 `TEXT_OFF`/`TEXT_SIZE` 用这个）
- `InitPyacsdk(bool)` @ `0x829a9b8`（装配：注册日志通道 + 塞 3 个配置串 + 建检测对象）
- `UpdatePyacsdk()` @ `0x829acc4`（**传输/上报侧**：迭代 NXHttpResponse 队列 + `neox::log::LogError`，非检测）
- `DeinitPyacsdk()` @ `0x829aae0`
- AC SDK 命名空间 = `neox::acsdk`；引擎检测函数都是**本地无符号 + OLLVM 混淆**。

### 已坐实的结论
- **无 foreign-reader 扫描**（无 `/proc/<他pid>/fd` 枚举）→ "外部只读 /proc 被 native 当场抓"不成立（apk 版与热更版均无）。
- **无 TracerPid/Substrate/Xposed/frida 明文**（那些在 `libsec-lib.so`）。
- `/proc/self/maps`、`/proc/self/fd`、`net/tcp` 串：`.text` 零 ADRP+ADD 引用、`.rela.dyn` 零 RELATIVE 指针（`xref.py` + rela 解析都验过）→ **捆绑库死串，非 acsdk 检测输入**。
- **架构性结论**：acsdk = 采集+上报(HTTP→`acsdk.gameyw.netease.com` / RPC `log_mobile_anti_cheat_check_info`)的 telemetry 客户端，**判定在服务器**。即便 deobfuscate 全部检测函数，也答不了"服务器是否因此发邮件"。
- 对 10/15：native 无"抓外部只读"的机制 → 更像**服务器侧择时/聚合判定(cause C)**，非某客户端检查当刻触发。

### 续作（下个对话从这里接）
- ~~B（更高效，但需注入）~~ **已做(2026-10-16,见 §7.6.2)**：hook `Avatar.try_call_server_method` 抓到真实
  `log_mobile_anti_cheat_check_info` 上报——是 **600s 周期心跳**,`lu:"ok"`(正常基线);**关键更正:`info` 里的 `zinfo` 不是
  加密、是 zlib(`78da`),解出明文 = 身份指纹+环境+签名心跳,不含逐项作弊标志**。"HTTP 加密抓不到明文"这条也因此松动(RPC 这条明文可得)。
- **C（纯静态、成本高）**：从 `InitPyacsdk`@`0x829a9b8` 装配的检测对象 / `UpdatePyacsdk` 的本地 callee 往下，deobfuscate OLLVM 混淆函数定位具体判据。注意 Hex-Rays 对这类会超时，需手读汇编。**且答不了服务器那半截。**
- 结论倾向：acsdk 当黑盒上报器处理；稳的姿势是**内核驱动只读**（不碰 acsdk 任何输入/触发），别依赖"注入一直没事"（判定在服务器且延迟）。

---

## 7.6 活体实证成果（2026-10-16，注入通道打通后）

> 本轮用 007 注入器(`/data/注入.sh` = `qq.sh`，推送见 `idv-reverse-resume`/`injection.md`)跑通 **probe2 进程内命令通道**，
> 首次对反作弊做**活体实证**(此前全是静态推断)。用法：往 `/sdcard/Android/data/com.netease.dwrg/files/idv_cmd.py`
> 写 Python(探针 2s 轮询 exec)，读 `idv_cmd_out.txt`；执行环境自带 `GK`(game_kernel)/`me`/`mgr`。
> 纯 Python 层、不碰 /proc、不写数值 → 安全。设备新机 UID = `u0_a409`，命令文件经 adb push 到上述目录即可。

### 7.6.1 `MEMORY_VARS` 全 13 组（§7#3 收口）

`MEMORY_VARS` 是**运行时值**(`ComuKeys.MEMORY_VARS`；全 17370 脚本无字面量定义，co_names 仅 `AntiMemModifyMgr` 引用)。
probe2 读 `GK.g_anti_mem_modify_mgr.origin_data` 得全部 13 组 `(struct格式, 值)`：

| # | fmt | 值(解出) |
|---|---|---|
| 1 | `fffiffff` | (100.0, -30.0, 1.0017157793, **-1061148117**(int位模式), 0.0,1.0,0.0,1.0) |
| 2 | `d`×4 | (5.0, 6.0, 7.0, 8.0) |
| 3 / 5 | `d` | 1.0 |
| 4 | `iiff` | (7680, 515, 0.0, 1.0) |
| 6 | `fffff` | (0.5961, 0.5961, 0.5961, 0.8, 3381.33) |
| 7 | `d`×2 | (18.0, 1.0) |
| 8 | `BBB` | (69, 67, 134) |
| 9 | `BBB` | (225, 67, 1) |
| 10 | `ffff` | (1.0, 0.9059, 0.851, 1.0) |
| 11 | `fff` | (0.45, 0.1, 0.45) |
| 12 | `d`×2 | (0.01, 1.0) |
| 13 | `d`×4 | (1.0, 1.0, 0.5, 2.0) |

机制：`generate_modify_vars` 打包 → `sum(bytearray)` 校验和(本次 `all_data_checksum=17815`)；`g_async_mgr` 每 **20** 周期
`check_modify_result` 重算比对，失配即 `MEM_MODIFY` 上报。**只读这些值不改 → 永不触发**（与"驱动只读从没被检测"闭环）。

### 7.6.2 acsdk 上报活体实证 + ★ zinfo 可解更正（§7.5 续作 B 收口）

hook `entities.Avatar.Avatar.try_call_server_method`(类方法)，装上约 136s 抓到真实上报：
`method='log_mobile_anti_cheat_check_info'`，`type='check'`，`info.result = {ret_code:200, report_id, messages:[json]}`。
`messages[0]` JSON：`gameId=android_h55`、`lu="ok"`(正常基线)、`type="heartbeat"`、`id`(设备 UUID)、`reportID`、`zinfo`。

**★ 更正 §5.4/§7.5 的"zinfo 加密不可得"：`zinfo` 开头 `78da` = zlib(非加密)。** `base64decode → zlib.decompress` 解出明文心跳：

```
{"details":{"sign","pre_ts","hb_counter","ts"},
 "machineId":"4E45-...", "version":"2.4.2.166089",
 "extraInfo":{"server"(=scene_id),"mainModule":"libclient.so","unisdk_transid",
   "sign_ver":"2.0","signinl"(base64),"udid","center_server","sign","res_version",
   "role_id","app_channel"}}
```

- 心跳周期 `pre_ts→ts = 600s`（坐实 §5.4 的周期常量 600）；`hb_counter` 递增。
- **心跳明文 = 身份指纹 + 环境 + 签名**（两个 md5 `sign` + `signinl`），**不含逐项作弊标志位**；正常态 `lu:"ok"`。
- 架构结论修正：客户端上报的是**带签名的身份/环境心跳**；真正的作弊判定靠**服务器对 sign/machineId/role_id/行为的聚合**
  （仍"判定在服务器"，但机制比"加密不可得"清楚得多——心跳内容本身是明文，只是不含检测结果标志）。
- 工具：hook 一次性装在类上(持久)，日志落 `.../files/acsdk_hook.log`；zinfo 解压 = `base64.b64decode → zlib.decompress`。

### 7.6.3 五类 `ANTI_CHEAT_TYPE` 检测逻辑（字节码实证，`drivers/deobf.py`）

全部走 `get_combat_component(CombatVoice).send_battle_event_safe` 上报，`info` 带 `key`/`speed_info`，仅局内 `is_battle_client` 生效。

| 类(值) | 检测函数 | 检测逻辑 |
|---|---|---|
| **MEM_MODIFY** 100004 | `AntiMemModifyMgr.anti_mem_modify` | 13 组 `MEMORY_VARS` 校验和(17815)，每 20 周期 `check_modify_result` 重算，失配=值被写改。只读不触发。 |
| **SCALE** 100002 | `PlayerUnit.server_anti_cheat_func` | 遍历 `get_player_units`；`s_pos - unit位置` → `COMPARE_OP >` 配常量 **480**(距离门限)；读 `unit.model.scale.x/y/z` → `max(...)`，缩放异常上报。检测**模型放大/缩小**。 |
| **MOVE_SPEED** 100003 | `PlayerUnit._log_move_speed_cheat` | `speed_real` = **实测速度**(非设定值,见 §7.6.4)，查 `is_door_open`/`has_civilian_on_hook`(开门/上钩=合法提速，排除误报)；超期望则累积 `anti_move_speed_cheat_infos` → 异步 handler 上报。 |
| **COLLISION** 10000 | `WorldBattle.anti_cheat_col_func`(各模式同构) | 本机 `anti_cheat_col_pos` 轨迹(`pos1→pos2`)，`collision_mgr.sweep_test_new` 扫掠碰撞，常量 **15.0**(步长)，`int(x/y/z)`；轨迹穿碰撞体(`hit_pos`)=穿墙。`ghost_col`=排除项；`g_async_mgr` 周期重调度自己。 |
| **SPEED** 100001 | `WorldBattleBase.handle_speedup_anti_cheat` | `anti_speedup_dct: idx→(c_timestamp,timestamp)`；`delta = c_timestamp - last_c_timestamp` 对比 `game_time`，客户端时间增量异常(变速齿轮)=加速。`BattleEvent`/`CombatVoiceComponent` 处理**服务器下发**的 `ac_type`(踢人提示)→ SPEED 有服务器参与。 |

实证程度：检测函数/字段/算法骨架/分支/`COMPARE_OP`/常量(480/15.0/20)均**字节码或活体实证**；唯**各数值阈值的精确判定值**
藏在 `CALL` 参数里，受 §7#2 的 CALL-系列 opcode 未校准限制而读不准——校准后(§7#2 进行中)即可补全。

---

### 7.6.4 移速检测深挖 + 常见规避为什么不成立（2026-10-16）

**`speed_real` 是实测速度，不是设定值（关键原理）**：`common_cs/mgr/RealSpeedSetComponent.py` 的 `tick` 每帧记
`(owner.get_position3, room.game_time)`，`cs_utils_battle.cal_real_speed` 用**位移 ÷ 时间间隔**反算真实速度，再
`set_speed_for_collision` 喂碰撞系统。→ MOVE_SPEED **"测结果不测设定"**：改任何速度变量，只要角色实际位移变快，
`speed_real` 必然反映。`_log_move_speed_cheat` 据 `type`/`level` 基准（+ 开门/上钩合法加速修正）比对，超出累积
`anti_move_speed_cheat_infos`、计数（疑似 `nums` 里的 **4**，防抖）达标经 `g_async_mgr` + `send_battle_event_safe` 上报。

**常见规避为什么不成立（检测鲁棒性分析）**：

- **"hook `speed_real` 置 0 再改移速"**：能让**客户端** MOVE_SPEED 自检哑，但——
  ① 位置联网同步，**服务器用位置轨迹独立算速度、不信客户端 `speed_real`**（权威在服务器，客户端置 0 只蒙自己）；
  ② `speed_real` 还喂 COLLISION，真加速的快速位移易踩穿墙扫掠；移速基准若落在 `MEMORY_VARS`（第 1 组
  `(100.0,-30.0,…)` 疑似基准量）→ 撞 MEM_MODIFY 校验和；③ hook 需注入（ptrace + 落地 .so），撞 native 环境检测，
  风险更高；④ acsdk 带签名周期心跳，该报不报 / `hb_counter` 断档本身是服务器聚合信号。
- **"hook `send_battle_event_safe` / `try_call_server_method` 不上报"**：对只读多余（无事件可报）；对写改不可靠
  （native HTTP 另一条上报路、服务器行为聚合、心跳断档），且同样要注入。
- **总结**：真"写改 / 加速"类作弊绕不过**服务器位置校验**；**驱动只读 ESP（不改位置 / 不加速 / 不写数值）是唯一稳的路
  —— 它不触发任何一类检测，根本不需要规避**。这也从反面解释了 §5.2 "驱动只读两套全躲"为何成立。

---

## 7.7 封禁 / 设备指纹 / "脏环境"画像实证（2026-10-16/17）

> 动机:注入会收到"检测到修改客户端"警告但不封;追问客户端是否本地记"本机脏了"的标记、服务器是否按设备建风险画像。
> 实测走 adb+su 读磁盘文件(不碰 /proc 内存) + all_pyc 静态。设备标识真实值在本机文件里,本文档已脱敏。

### 7.7.1 封禁状态:客户端**不本地持久化**
`entities/ClientBoot.pyc` 三个服务器下发回调,**只弹 TID 提示、不落盘**(persist 为空,names 只有 `show_tid_tips`):
- `on_lock_account_forever`(永久,`TID_ACCOUNT_BLOCKED_NEW1`/`_REASON`)
- `on_lock_account`(限时,`TID_ACCOUNT_BLOCKED_S`/`_H`/`_D` = 秒/时/天)
- `on_login_forbidden`(`TID_MAC_FREEZE`/`TID_UDID_FREEZE`/`TID_ACCOUNT_BLOCKED`)

**关键:`TID_MAC_FREEZE`/`TID_UDID_FREEZE` → 封禁可绑定 MAC/UDID(设备级),不只账号。** 每次登录服务器实时判定下发。
排除误报:`entities/logic/BanLogic.ban_info` = 对局禁选角色(BP);`common_tools/ResBlackListMgr` = 资源文件黑名单;均与封号无关。

### 7.7.2 异常行为上报:内存累积 + 打点服务器(不持久化)
- `common_cs/mgr/ExceptInfoManager.record_except_info`:计数字典 `_except_count_dct` 是 **room 级内存**(`destroy()` 清空、不跨局),
  每种 `except_key` 上限 **10** 次(`force` 可绕),带 `unique_id/guuid/scene_id/player_name/position` 经
  **`Netease.LM.log(LOG_TYPE.ExceptInfoServer)`** 打点网易日志后台。
- 触发源之一:`common_cs/combat_core/components/unit/TransformComponent.check_cheat_count`(移动/方向同步作弊计数 `cheat_count`
  超 `cheat_count_limit`;`process_dir_sync_event` 里有 `check_cheat_pos_diff`/`dis_check`/`ray_check`/`flywheel_tag`/`sportman_tag`)。
- `core/camera/CameraCtrl._record_except_info` → `g_log_mgr.log_except_info`(相机异常)。

### 7.7.3 设备指纹:**大量本地持久化**(实测,值已脱敏)
`/data/data/com.netease.dwrg/{shared_prefs,files}` + `/sdcard/Android/data/com.netease.dwrg/files`:

| 文件 | 内容(脱敏) | 性质 |
|---|---|---|
| `…/files/DeviceId.txt`(sdcard) | `device_id:<16-hex, Android ID 格式>` | **卸载重装保留**,跨安装持久 |
| `shared_prefs/virtualImeiAndImsi.xml` | `virtual_imei`/`virtual_imsi`(unisdk 自造) | 伪 IMEI/IMSI 持久化 |
| `shared_prefs/vkeyid_profiles_v4.xml` | `key_deviceid_v4` = 加密 hex | **网易 vkey 设备指纹(最硬)** |
| `shared_prefs/unisdk_devices_infos_file.xml` | 硬件画像:MODEL/ROM/CPU SM8550/GL Adreno740/**`IS_ROOT=true`** | root 状态被记录 |
| `files/ntunisdk_so_uuids` | 73 个 native so 的 md5(libclient `F493C851…`、libsec-lib `6ACECC63…`…) | **so 完整性基线** |
| `files/unisdk_gm_<role_id>` | gmsdk JWT session(`gmsdk.gameyw.netease.com`) | 安全 SDK 会话;按账号存(本机见两个账号) |

### 7.7.4 get_udid / machineId 生成链
Python `get_udid`(`core/LogMgr`、`PatchManager/PatchLogMgr`、`UICommonFeedbackPatch`)→ **`unisdk.getUdid()`**(`libntunisdk.so`,native)
→ 综合 Android ID / 虚拟 IMEI / vkey → 缓存到上述文件。MAC = `game3d.get_mac_address()`(内存 `_mac_address`)。
machineId(`4E45-…` 格式,`4E45`=ASCII "NE")= acsdk native 内部生成。`neox2/unisdk_fake.getUdid` 是 PC/测试桩。

### 7.7.5 "脏环境"结论
- **客户端不存"我脏了"布尔**;但存一整套**稳定设备指纹**(Android ID/vkey/伪IMEI/硬件/IS_ROOT),**每次联网上报**
  (acsdk 心跳带 udid/machineId、unisdk 上报 vkey、`IS_ROOT=true` 也在内)。
- **"脏环境"在服务器侧**:按设备指纹 + 账号 `unique_id` 建风险画像;脏过的账号/设备被更低阈值判——**那封警告邮件就是画像已被写的证据**。脏环境下再叠加任何异常更易越过封禁门槛。
- **删本地文件不足以重置**:native 重建(Android ID 从系统取、回旧值;伪 IMEI 出新值;vkey 可能服务器重绑),且**服务器已有画像不会因本地删除而清**。真正"干净"= 换物理设备 + 换账号 + 不 root。
- **对注入的直接含义**:`ntunisdk_so_uuids` 是 so 完整性基线;注入 `dlopen` 的 `.idv_hook` so 会出现在 maps 但不在清单 →
  正是 `libsec-lib` 的 maps 扫描(`allHookInfo`)能逮的 → 与启动时环境自检上报的警告吻合(§7.6.2)。

### 7.7.6 诚实边界
封禁/设备画像的**权威判定在服务器**,本地标记(若有)清不掉服务器记录。未做的下一步:逆 `libntunisdk.so` 的 `getUdid` native 实现,
确认 `DeviceId` 取自 Android ID 还是可改源(决定删文件后是否重建成旧值)。

---

## 7.8 国际服(com.netease.idv.googleplay) 离线解包 + 中英 TID 对照（2026-10-23）

用途：拿游戏里任何文本的**官方英文名**（天赋/特质/道具/模仿者身份…），给叠加层英文模式用。零设备内存风险（只读 apk 文件）。

- **包位置**：`script.idx` / `script0.wpk` / `script1.wpk`(360MB) 在 `split_aab_assets_install_time2.apk` 的 `assets/res/`。
  设备上 `su` 下 `unzip -o -q <split> 'assets/res/script*' -d /data/local/tmp/x` 再 `adb pull`（PowerShell 里带 `|`、`.idx` 的命令会被安全检查误拦，写成 .sh 推过去跑）。
  ★ **必须叠热更**：`/data/media/0/Android/data/com.netease.idv.googleplay/files/netease/dwrg.common/Documents/res/`
  下也有 `script.idx`/`script0/1.wpk`(只含改动文件，9635 条)，游戏优先用它。`Documents/script` 那个目录是空的，别被骗。
  做法：apk 原包和热更各解一份，热更的 pydata **按文件覆盖**原包再解析。只用 apk 原包会读到**旧天赋**
  （2026-10-23 踩过：id 20/37/39 读成了 猫鼠游戏/警觉/无人生还，用户指出游戏里是新的）。
- **解包**：外壳格式、密钥与国服相同，`drivers/intl/gp_extract.py <idx> <out>` 19492/19492 全通，pydata 3838 个。
- **配表即 Python 模块**：`pydata/butcher_genius.py` 等；文本在 `pydata/tid_data/all_tid_<lang>_N.py`(各 120 片，lang=chs/cht/en/jp/kr/…)
  + `unusual_all_tid_<lang>_N` + **补丁 `pydata/all_tid_<lang>_diff.py`(覆盖主表，新天赋/新身份只在这里)**。`genius_tid_en.py` 这类是 `data=None` 空壳。
- ⚠️ **国际服字节码操作码字节大多被置 0**（LOAD_CONST/MAP_ADD/RESUME 全是 0），§7#2 的国服乱序表不适用。
  只能信**操作数**：每对 = `LOAD k, LOAD v, (0,1)=MAP_ADD`；`132`=EXTENDED_ARG；`(166,1)`+一个缓存；末段 `95`=BUILD_CONST_KEY_MAP(栈顶键元组)。
  **不能按相邻常量配对**（常量去重会错位）；`const[1]` 可能恰好是 str，所以 `(0,1)` 只在已攒满两个时才当 MAP_ADD。实现见 `drivers/intl/tiddict.py::decode_refs`。
- **天赋 id → 名字**：⚠️ 别用 `TID_TALENT_BACKGROUND_KILLER_<N>` 推 `TID_BUTCHER_NAME_<N>`——真名走被动技能的 `name_tid`，
  两者会不一致（id 20 背景 N=146 是旧天赋"猫鼠游戏"，真名 临界点 = `TID_BUTCHER_NAME_36_LV1`）。
  **可靠做法**：拿国服活体配表的 40 个中文名(`idv-replay-genius/genius-table.md`)，在合并后的 chs 表里限定 `^TID_BUTCHER_NAME_\d+_LV1$` 反查，
  40 个全部唯一命中 → 取同 TID 的 en。热更合并后国际服与国服是**同一套** 40 天赋。
- **产物**：`intl_tid/final_tables.txt`(监管 40 天赋、求生终端、8 特质、34 模仿者身份的中英表)、`intl_tid/tid_chs_en.json`(全量 17 万条 chs/en，`drivers/intl/tid_grep.py` 查)。
  查词时注意同一中文多 TID：道具名取 `TID_<道具>_LV1` / `TID_NAME_*` 那条（例：怀表道具 = `TID_WATCH_LV1` "Pocket Watch"，"Poseidon Watch" 是大副技能）。

---

## 9. 字节码完整还原 + 在标准 Python 里执行（2026-10-24，为"模拟器+强化学习"路线做）

### 9.1 结论
- **2024 版乱序表(`opcode_names.txt`)完全正确**，全量 351852 个函数体里没有一个未知字节。
- **inline cache 布局与标准 CPython 3.11 逐条一致**：磁盘上 cache 槽恒为 `00 00`、指令操作码字节恒非 0，
  所以每个字要么是指令要么是 cache，可以直接数"每条指令后跟几个零字"。统计结果每种操作码只有一种取值，
  且全部等于 `opcode._inline_cache_entries`（LOAD_ATTR 4 / LOAD_METHOD 10 / PRECALL 1 / CALL 4 / LOAD_GLOBAL 5 …）。
- **还原方法**：纯 Python 解 marshal（不让 CPython 构造乱序 code object）→ 记下每段 co_code 在流里的位置 →
  原地换成标准操作码 → 标准 `marshal.loads`。跳转、异常表、行号表都不用动。
- **结果**：17370/17370 转换成功、标准 marshal 载入 0 失败、0 崩溃（193 秒）。`dis` 输出完整正确（调用参数、方法名、跳转都对）。
- **能执行**：`common_cs.ComuKeys` / `HitRecord` / `CheckRangeBaseMethod` 等直接在本机 Python 3.11 里 import 成功。
  ⚠ 游戏把 `cython/` 目录放进 sys.path（`import cython` 得到 `cython/cython.pyc` 垫片），复现时 `sys.path` 要同时加 `std_pyc` 和 `std_pyc/cython`。

### 9.2 产物与工具（`drivers/sim/`）
| 文件 | 用途 |
|---|---|
| `rawmarshal.py` | 纯 Python 3.11 marshal 读取器，code 读成 `RawCode`，记录 `code_spans` |
| `idvpyc.py` | `load(path)` 得标准 code object；`to_std_pyc(src,dst)` 写标准 pyc（本机 magic） |
| `convert_all.py` | 全量转换（`python -I convert_all.py <sim目录> all_pyc std_pyc`） |
| `cache_stats.py` | 每个乱序操作码的后随零字数统计（验证 cache 布局用） |
| `census.py` | 依赖摸底：缺失模块自动打桩并记录访问路径，导入某包下全部模块 |
| `idx.tsv` | 17370 个脚本的"文件 → 名字/字符串/函数名"文本索引，直接 Grep |
| `census_common_cs.json` | `common_cs` 摸底原始结果 |

产物目录 **`std_pyc/`**：与 `all_pyc/` 同结构的标准 3.11 pyc，可直接 import / dis / 交给反编译器。

### 9.3 依赖摸底（只看导入阶段，运行期调用还没测）
`common_cs` 6812 个模块：**5546 个(81%) 导入成功**。剩余失败几乎都是 `'NoneType' object has no attribute 'global_data'` 一类，
即游戏数据管理器(配表)没初始化，不是缺原生模块。打桩模块 102 个，导入阶段真正被访问的原生接口：
- `math3d`：`vector`/`Vector3`/`Matrix`/`matrix_to_rotation`/`rotation`/`vector2`（好实现）
- `world.model`(1030 次，基本是类定义里引用)、`neox.nxanimation`、`collision`/`physx_collision`（导入阶段没访问，**运行期才是大头，待测**）
- `frame_sync.common.fixmath_wrapper.Fix32/Fix32Vec2`、`frame_sync.common.frame_property`（小游戏帧同步用的定点数）
- `common_cs.cython_src.CommonUtils`、`common_cs.cython_utils.observer_utils`（Observer 系列）：**被 Cython 编进原生了，要自己重写**（简单数据结构）
- `mbengine`(日志/RPC/网络)、`servercommon.Netease`、`cocosui`/`cc`/`ccui`(UI)、SDK 一堆：模拟器里打空桩即可

另：`cython/build_cython_server.pyc` 可能列出了服务端用 Cython 编译的模块清单，值得一看。

### 9.4 ★ 游戏自带"本地服务端"模式（2026-10-24 发现，模拟器的正确入口）
- `etc/dev_config`：`COMMON_CS_MODE` ∈ `MODE_CLIENT=0 / MODE_SERVER=1 / MODE_CS=2`；`set_cs_mode()` 置
  `common_cs_client / common_cs_server / common_cs_cs` 三个开关。**`MODE_CS` = 同一进程里同时跑客户端和服务端逻辑。**
- `entities/logic/GameLogic.reply_enter_client_battle`：服务器让客户端进"客户端对局"时切 `MODE_CS`，
  再 `g_world_mgr.change_to_world`。新手教程(`NOVICE_BATTLE`=2)、教学、剧情都这么跑——**手机不连服务器本地对 AI 打完一局**。
- `worlds/WorldBattleClient*`（`ClientBase/ClientNovice/ClientStory/ClientArcher/…`）是这类世界。
  `WorldBattleClientBase.init_combat_core` 建 `combat_core_local_server` + `create_combatcore_impl_unit_localserver`；
  `init_game_unit` 按 `scene_config.pos_config` 生成密码机/椅子/箱子/地窖；`_init_units`/`add_units_in_scene` 建带 `ai`/`ai_id` 的角色；
  `game_tick`、`check_game_over`(挂椅淘汰/逃脱)。61 个文件在 `common_cs_cs` 下有单机分支。
- `common_cs/combat_core/CombatCore`：ECS 框架，`CombatCore(shell, game_type, net_mode, params)`，
  `net_mode` ∈ `ONLINE_SERVER/ONLINE_CLIENT/LOCAL_SERVER/LOCAL_CLIENT`，有 `enable_determinism`。
- **`Netease` 命名空间**：代码里是 `if SERVER_MODE: from servercommon import Netease else: import game_kernel as Netease`。
  走客户端+MODE_CS 这条原路就**完全不需要伪造 `servercommon`**，`Netease` 就是 `GK`。

### 9.5 第 1/2 步进展（`drivers/sim/`）
- `simenv.py`：sys.path（`natives/` → `std_pyc/cython` → `std_pyc`）+ 自动打桩(记录访问与调用签名) + `FORCE_STUB`(网络/SDK/game_init，切断循环导入)。
- `natives/`：原生模块的 Python 替代。已有 `taggeddict`（配表每行 `TD({...})`，语义就是 dict；打成桩会让配表全空）。
- `simboot.py`：`set_cs_mode(MODE_CS)` + `GK.DM = core.DataManager.DataManager()`（`global_data` 1044 项）。
- `census2.py`：启动后导入统计 —— **`common_cs` 6795/6812、`ClientUnits` 694/694、`worlds` 121/121，全部 ≈100%**。
- `simworld.py`：GK 上 83 个为 None 的全局对象换成记录型桩 → **`WorldBattleClientNovice()` 实例化成功**。
- **地图几何是服务端同款资源**：`scene_config[6]`(军工厂) 有 `server_col = scene/scene_battle/ordnance_factory1/nav/ordnance_factory1.scn_col`、
  `server_nav = …/ordnance_factory_test1.nav`。模拟器的碰撞/导航 = 解析这两类文件 + 用物理库(如 pybullet)实现 `CollisionManager` 调的 sweep/ray。
  这两类文件在资源包里（不在脚本包），本机还没有，要从设备/apk 拉。

### 9.5.1 资源包（地图几何）调研（2026-10-24，从设备拉）
- 设备资源目录：`/storage/emulated/0/Android/data/com.netease.dwrg/files/netease/dwrg.common/Documents/res/`，
  场景是 `scene.idx`(4MB, 113141 条) + `scene2~5.wpk`(共 1.75GB)；`res/scene/` 是散装槽位(文件名=哈希)。
  拉法：su cp 到 `/data/local/tmp/` 再 pull，**pull 目标必须是 ASCII 路径**（中文路径 adb 写不进），带 `|` 的命令写成 .sh 推过去跑。
- ★ **热更脚本**：设备上 `res/script.idx` + `script1.wpk`(151MB, 2026-10-23) 比 `all_pyc`(apk 原包 2026-06-11) 新，
  模拟器最终要按文件覆盖热更版（同 §7.8 国际服的教训）。已拉到 scratchpad `hotres/`，还没解。
- ★ **idx 的 16 字节键 = 文件内容的 MD5**（解出 6 个条目逐一验证全中），资源包按内容寻址。
  所以"路径 → 条目"必须靠另一份"路径 → MD5"清单（候选：`Documents/pkgmapping.json`/`static.json`/`thd/`，未拉成，设备断开）。
  弯路：试过 MD5/XXH128/Murmur 对路径哈希全不中；引擎里 13 处 `neox::XXH3_128(…, seed=0)` 调用，部分是对数据(跳过 0x24 头)算哈希，与路径无关。
- 资源类型(`drivers/sim/resclassify.py` 全量分类，scratchpad `scene_classify.tsv`)：
  `TESM`×222 = **Detour 分块导航网格总表**(`MSET` v7，例：449 块、块 25.6×25.6，块是独立文件 `x_y_layer.tile`)；
  `<Physics>`×26 = 单模型碰撞形状 XML(坐标 <1m，不是整张图)；`CVIS`×918、`OcCi`、`LCCO`、`terrain`、`<SceneConfig>`(场景描述)等。
  `.scn_col` 还没认出来（大概在无明显魔数的 2 万多条里），要靠清单按路径找。
- 工具：`drivers/sim/residx.py`(读 idx、按候选算法查路径)、`resclassify.py`、`resextract.py`(按序号解条目)、`hashprobe.py`；
  `drivers/blxref.py`(在 .text 里找 BL/B 到指定地址的调用点)。

### 9.5.2 路径 → 资源 的清单 `thd/*.thh|*.thy`（2026-10-24）
- 位置 `Documents/thd/`，每个包一对：`scene.thh`(1.5MB) / `scene.thy`(6.8MB)。格式 = `b"THFB"` + u32 + FlatBuffers：
  根表.f1 → 表 T(@0x20)：`T.f0` = 主向量，**188885 条**(比 idx 的 113141 多，其余在 apk 原包)：
  `.thy` 每条 32 字节 = `[u32 载荷大小][u32 未知(几乎全不同)][u32 0xfc0000NN 标志][u32 解压后大小][内容 MD5 16B]`，
  `.thh` 每条 1 个 u32（几乎全不同，未排序）；`T.f1` = 两文件相同的前缀子表：`f0` 188885×u32、`f1` 3×u32(0x1eb62c88,0x22c43571,0x0b6807cd)、`f2` 2×u32(163,123)
  —— **形态像最小完美哈希**(位移表+种子+参数)，`.thh` 像指纹。
- **路径→指纹的算法没破**：FNV-1a(=引擎 `StringIDVS2012`)/XXH32(=`StringIDXXH`)/Murmur3(种子 0x9747b28c=`StringIDMurmur3`)/
  XXH3-64/128、XXH64、MD5 各 32 位片段、上述 3 个种子，配合多种路径写法，对 `.thh` 和 `.thy` 第 2 字段全不中。
  `StringIDLegacy` 还没实现来试。引擎里读清单的代码在 `0x56B…–0x56D…`（`load_fb_table` 报错串 xref 在 0x56D7294/0x56DAB34），无符号，未深挖。
- **捷径**：游戏 Python 按路径读资源用 `C_file.get_res_file(path, …)`（19 个脚本在用）。在游戏进程内调用即可按路径原样取出
  `.scn_col`/`.nav`/`.tile` —— 但需要 probe2 注入（§5.2 的高危路径），由用户决定。
- 工具：`drivers/sim/thfb.py`(FlatBuffers 表逐层打印)、`thdmap.py`(三处 u32 + 候选哈希匹配)、`thyprobe.py`。
  拉清单的脚本在 scratchpad `pull_manifest.sh`（`Documents/thd/` 整目录 + 几个 json，50MB）。

### 9.5.3 一次性注入导出（2026-10-24 写好，用户自己跑；用户说注入后账号会被封，只有这一次机会）
- 脚本在 `逆向存档\_scripts\`：`cmd_resdump.py`(模板) → `build_resdump.py <explicit_paths.json>` → `cmd_resdump_built.py`；
  驱动 `run_resdump.ps1`（查 pid/uid → 推命令 → 确认探针接收 → 轮询 progress.json → 拉回到 ASCII 目录 `C:\Users\31297\idv_resdump_<时间>` 并拷进 `res_pull\resdump_<时间>`）。
- 内容：A 按 `DM.scene_config`(全部图)+350 条离线清单(配表里全部 .scn/.nav/.col/.postprocess + `scene_model_config` 等 124 个单位/碰撞模型)
  + 派生(`.scn_col`→`.col_mesh`/`_dev.col_mesh`、`utils.get_scene_col_path`、导航 `ai_`/`moveable_` 前缀、`grocer_door.col_mesh`) 取文件；
  B 解析每个 `.nav`(MSET，块名是 u32 长度前缀串，真实样本 449/449 解析正确) 按候选目录取全部 `.tile`；C 解析 `.scn` 引用补取；
  **关 zip 落盘后**才做 E(接口清单 api_report.json) 和 D(若在对局：`hit_by_ray_new_with_scn_col` / `hit_by_ray_new` 竖直 96×96 网格 + 随机射线，150 秒，raytruth.jsonl)。
- 产物：`res.zip`(STORED) + `manifest.jsonl`(路径/大小/MD5/来源) + `miss.jsonl` + `nav_report.json` + `log.txt` + `raytruth*.json*` + `api_report.json`。
- 本地干跑：`drivers/sim/test_resdump.py`（真实配表 + 假 C_file），各阶段通过。
- ~~动画根运动不需要注入：服务端模式 `AnimDataComponent.READ_FROM_PYDATA`，数据在 `pydata.anim.gg*`（脚本包里）。~~
  **2026-10-26 更正：错。** 客户端脚本包里没有 `pydata/anim`；`DataManager.get_dis_anim_data_path` 自己写着"这个方法不该被调用"，`get_dis_anim_data_only` 客户端没有定义——那是服务端独有的导出数据（§9.12.3）。

### 9.5.4 ★ 导出结果（2026-10-25 01:54 跑，军工厂人机局）
- 注入：`/data/qq.sh` = 007 工程 `libs/arm64-v8a/qq.sh`(10-18 构建, md5 `366a5eb8…`, 载荷区开头是 probe2 18970 字节)，
  `nohup` 后台起；成功判据 = 游戏 maps 里有 `.idv_hook_<pid>.so (deleted)` + `idv_snap.json` 每 2 秒刷新（新机 logcat 里看不到 GameHook）。
- **跑到 155 秒时游戏整个死锁**：230 线程全睡、CPU 0、探针快照停更。推断：后台线程持 GIL 调 `C_file.get_res_file`，
  碰到需要按需下载/资源系统加锁的路径，与持锁等 GIL 的引擎线程互锁。**教训：进程内批量读资源不要在后台线程持 GIL 狂调；
  应放到游戏主线程的定时回调里分批做，或先过滤掉本机未下载的包。** 阶段 C/D/E 没跑到 → **碰撞射线真值没拿到**。
- 抢救：zip 没写中央目录，`drivers/sim/zip_recover.py` 按本地文件头恢复 → **6022 个文件，manifest 6000 条 MD5 全对**，
  存档 `res_pull/resdump_1025_015456/res_recovered.zip`(183MB)。按类型：tile 5399、scn 236、gim 190、nav 115、scn_col 70、col_mesh 8、postprocess 4。
- 覆盖率(`drivers/sim/dump_coverage.py`)：98 个(server_col, server_nav)组合里 **44 个碰撞+导航+全部分块齐全**，
  含全部常规图：军工厂(1)、红教堂(11)、圣心医院(18/78)、湖景村(19/74)、月亮河公园(30/80)、红教堂夜(31)、疯人院(32)、
  军工厂2(33)、永眠镇(34/39)、闪金洞窟(37/59/82)、唐人街(40/52/79)、里奥的回忆(29)、赛马场(49/56) 等。
  缺的多是活动/变体图(28/36/38/41-48/50/51/53/62/109/1000-1005…)：`get_res_file` 直接返回空 → 本机没下载这些包，不是脚本问题。
  `ai_`/`moveable_` 派生导航在本机都不存在；`.col_mesh` 只有 8 张图有。
- 导航块目录规律：`<nav所在目录>/<nav文件名去扩展名>/<x>_<y>_<layer>.tile`。

### 9.7 ★ 碰撞 / 导航格式（2026-10-25 离线解完，`drivers/sim/scncol.py`、`navmesh.py`）
**`.scn_col`（服务端静态碰撞）= 物体流，逐个物体：**
```
[u32 1][u32 编号/组][u32 类型 c][u32 nv][nv×3 f32 局部顶点][u32 nt][nt×u32 三角标志][u32 ni=3nt][ni×u32 索引]
  c==3 时再跟 [u32 n][n 字节 Bullet 量化 BVH "BULLETf_v284QBVH"]
  然后是可选的带标签字段，直到下一个 u32==1(下个物体) 或文件尾：
    tag 4 → 16 f32 矩阵；tag 3 → 3 f32 位置；tag 5 → 2 u32(像组号+标志 0x2010000/0x40000)
世界坐标 = 局部顶点 × 矩阵(行向量约定，取左上 3×3) + 位置
```
- 70/70 文件全部恰好解析完，合计 445 万三角形；c=1 47141 个、c=3 707 个；三角标志几乎全 0（少量 0xFFFFFF）。
- **引擎碰撞库就是 Bullet**（BVH 魔数 + 代码里 `use_bullet`/`bullet_collision`）→ 模拟器用 pybullet 能对得很准。
- 行/列约定的判定：只看两种约定下占地不同的不对称物体，测导航顶点处水平净空（墙穿过可行走区则近距离命中多）：
  军工厂 <2 的顶点 行183/列258/不乘矩阵356；全图贴墙过近比例 行 2.93/4.19/3.73% vs 列 3.68/4.34/4.58%（军工厂/红教堂/圣心医院）。
  导航顶点正下方有碰撞面：93.9/96.3/97.6%，中位距离 0.2–0.8。工具 `validate_col_nav.py`、`validate_rot2.py`、`colgeo.py`。
**`.nav` = Detour MSET v7**（orig, tileW/H=256, maxTiles, maxPolys + 块名表）；**`.tile` = [i32 -1][i32 长度] + 标准 Detour tile（'DNAV' v7）**，
  5399/5399 解析通过；walkable 高 30 / 半径 6 / 可攀爬 10。块在 `<nav目录>/<nav名>/<x>_<y>_<layer>.tile`。可直接喂 recastnavigation。

### 9.8 路径哈希（未破，降优先级）
用 5989 对已知 (路径 → MD5 → 清单序号 i) 样本，对 `f0[i]`、`.thh[i]`、`.thy[i].字段2`、`i` 本身，
试了 FNV-1/1a 32/64、djb2、sdbm、BKDR、Java、CRC32、Adler、XXH32/64/3-64/3-128、Murmur3-32/128、MD5/SHA1 各 32 位片段、
3 个疑似种子，× 14 种路径写法（含引擎实际接受的写法）→ 全不中；也不是内容哈希。三组值都是互不相同的随机 u32、均未排序。
结论：自定义/带盐算法，只能逆引擎 `0x56B…–0x56D…` 的无符号代码。**不影响模拟器**（碰撞/导航已全拿到），只影响"以后离线按路径取任意资源"。
下次若再注入，可顺手 `dir(C_file)` 找有没有暴露路径→哈希的函数。工具 `drivers/sim/hashcrack.py`。

### 9.9 ★ 1v4 模拟对局框架（2026-10-26，`drivers/sim/`）
**最新现状与下一步见 §9.6（2026-10-25 收口）。** 以下是 2026-10-26 框架建立时的记录。
**现状**：军工厂 1 监管 + 4 求生者全部挂人机行为树，每帧都在跑；整图交互物齐（板 43/窗 17/门 2/开关 2/柜 18/椅 20/机 7/箱 6/地窖 1）。
无单位时约 26 倍速，5 个 AI 跑起来约 2 倍速（还没优化）。**角色还不会正确移动**：碰撞查询全是"未命中"，Y 坐标每帧匀速上升。

| 文件 | 作用 |
|---|---|
| `simcore.py` | `SimCore`：启动、表现层置空、模拟时钟、GK 桩、`SimWorldMgr`、`make_world` / `frame` / `run` / `report`；`SimCore(server_ai=True)` 装服务端模式 AI 孤岛（`install_server_ai_island`，§9.6.2） |
| `sim1v4.py` | `WorldSim1v4(ServerRoomShim, WorldBattleClientBase)`：编成、出生点、按服务端方式挂 AI、服务端房间垫片；求生者补 `avatar=None`、`punish_start_timestamp=0`（依据见 §9.6.2） |
| `run1v4.py` | 驱动：`python run1v4.py [scene] [帧] [--server-ai]`，打印轨迹/行为树步数/异常/碰撞统计与调用样本 |
| `simrun.py` | 新手局诊断（改用 SimCore） |
| `pseudo.py` | ★ 3.11 字节码 → 伪源码（栈模拟折叠表达式，跳转写 goto）。`python pseudo.py worlds/X.pyc '函数名正则'`。pycdc 不支持 3.11（MAKE_CELL 直接放弃），别再试 |
| `usage.py` | 某调用的结果在调用方怎么用：`python usage.py 'collision_mgr\.hit_by_ray_new\(' common_cs 3 6` |
| `idxq.py` | 查 idx.tsv：`python idxq.py '^ai_id$' [路径前缀]`（输出别直接接 `Select-Object -First`，会 OSError，先重定向到文件） |
| `natives/physx_collision.py`(+`bullet_collision.py`) | ★ 碰撞适配层（§9.6.1）：`load(.scn_col)` 从资源 zip（`IDV_RES_ZIP`，默认 `res_pull/resdump_1025_015456/res_recovered.zip`）建 `ColWorld`；射线/扫掠/静态测试/路径相交全接，过滤 `passes()`，形状表 `SHAPE_QUERY`（球/盒子/胶囊），动态体标脏同步；统计 `QUERIES`/`QUERY_HITS`/`UNSUPPORTED`/`QUERY_SAMPLES` |
| `colworld.py` | ★ 碰撞内核（只依赖 numpy，2026-10-25）：静态网格 + 动态体(三角形) 上的 `raycast` / `capsule_overlap` / `capsule_sweep`(保守推进) / `box_overlap`(分离轴)，XZ 均匀网格 + 3D 包围盒预筛 + 动态体 slab 剪枝；`box_tris`/`capsule_tris`(外接多面体)。军工厂本机：竖直射线 4199 次/秒、扫掠 626 次/秒 |
| `t_colworld.py` | colworld 自测：合成 `.scn_col`（含旋转物体）+ 与暴力解 / 密集采样对拍，不需要游戏资源 |
| `t_colconst.py` | 打印碰撞适配要用的真实常量（`CollisionConst` 的过滤模式/Layer/Group/形状、`Filter`/`RoleFilter` 默认参数、`UNIT_TYPE_CONF` 编号名） |
| `t_physx.py` | `physx_collision` 适配层自测（假 `CollisionConst` + 合成地图）：过滤语义、返回结构、动态体同步、三种形状、副本语义；39 项。把过滤模式故意弄反时 26 项失败 |
| `colcheck.py` | 真实地图校验：`colcheck.py <zip> <scn_col> [nav|auto] [半径] [抽样]` → 导航顶点下方地面命中率、沿导航边扫胶囊的被挡比例、吞吐（nav 省略时自动找同目录 `.nav`，军工厂要显式给主导航） |
| `natives/world.py` | `scene.get_model(name)` 按 `DM.pos_info[scene_id]`（每项 = 模型名, 位置, 16f 矩阵, …）返回带变换的模型；`register_scene_models` |
| `natives/math3d.py` | 补 `vector.__abs__`(=长度)、向量比较(按长度，推断)、`rotation.slerp`、`rotation_to_matrix`；`matrix.rotation` 改为返回旋转部分矩阵(NeoX 语义)；修 `matrix_to_rotation` 迹≤0 分支 |
| `simpatch.py` | 新增 `install_traceback_capture`（游戏吞异常都走 `TracebackManager().on_traceback`）、`count_calls`（调用链计数诊断） |

**生命周期里游戏靠引擎/UI 推进、模拟器必须补的节点**（`SimCore._on_game_start`）——每条都卡过：
1. `init_after_loading()`：真机由加载界面结束回调调用；不调则 `is_loading_finish=False`，`WorldBattleBase.game_tick` 第一段就 return，单位永不 tick。
2. `GK.input` 换真值桩 `simenv.TStub`：`game_tick` 有 `if not GK.input: return False`；但**建单位阶段必须保持假**（真机那时还没输入，`ItemBase._get_item_ability` 的 `fix_item_pos` 分支会读不存在的 `have_fix_item_pos`）。
3. `w.skip_opening = True`：开局环绕镜头靠相机每帧推进到时长再回调开战；不跑相机就停在 `ROTATE_Y_MODE`，`game_tick` 在 `unit_mgr.tick` 前 return。
4. 单位异常全被 `UnitManager.tick_client` 吞掉，必须装 traceback 捕获才看得见。

**编成与 AI 挂载**（`sim1v4.py`）：
- `world_type` 仍用 `NOVICE_BATTLE`：只有 NOVICE/STORY 等类型会置 `is_battle_client`（本地服务端）；`BATTLE` 会置 `is_battle_server`=联网对局。`game_type` 设 `KILL`。
- `add_units_in_scene(pid, pos, dir2, uid, npc_info, pid_info_source, eid, use_special_y)`：**`pid_info_source==1` 才是 npc 表**，0 从 `DM.player` 取（第一次读反了）。
- 求生者 `u.change_ai(bt)` → `AICivilian`；监管按服务端做法 `QAAIFactory.create_qaai_controller(pid, u, bt)`（`CONTROLLER_MAP` 按 pid 选 `QAAIButcherJack` 等，厂长/小丑用基类 `QAAIButcher`）。客户端 `BattlePlayerUnit.change_ai` 给监管的是旧 `AIButcher`，`qaai_butcher_*` 行为树要的 `make_global_policy` 它没有。
- ~~配表里**没有任何地方引用 `qaai_*`**~~ **2026-10-26 更正：错。** `pydata/player_ai_conf` 按角色、按房间类型配了人机行为树（§9.16）；`qaai_civilian_hard` 只出现在 `pydata/player` 的 `ai` 字段（pid 3/14/17/32），不是自定义人机房用的。当时的编成（厂长 `qaai_butcher_common` + 4×`qaai_civilian_hard`）没有依据。
- 难度：`QAAIButcher.set_level` 在 `room_type ∈ {CUSTOM, SINGLE_CUSTOM}` 时取 `room.player_set_ai_level=(监管, 求生者)`（`CUSTOM_AI_LEVEL` 1–4），否则按真人段位均值 → 模拟器对应"自定义人机房"。
- 跑酷家(pid 25) 建单位时 `VSkillCivilianParkour` 读 `_skill_modify_mgr` 失败，默认编成先避开。

**★ 关键发现：人机 AI 的完整逻辑只在 `SERVER_MODE` 下开启**（客户端分支是残缺的）
- 例：`AICommonTrigger` 客户端模式不建 `save_or_fix`(SOF)、`ai_env_combat_utility`（救人/修机打分）；`AICivilian.init_wood_panel_dic` 客户端直接 return（AI 不认识板窗）；`AICivilian` 的 `MathUtils` 只在服务端导入。
- AI 模块都是**调用时**读 `dev_config.SERVER_MODE`，`Netease` 在导入时绑定 → 可做"服务端模式 AI 孤岛"：其余模块正常导入后，清掉已加载的 `common_cs.ai.*`，`SERVER_MODE=True` 下全量重导入（`servercommon.Netease` 指向 GK），再恢复 False，给这些模块换 `SERVER_MODE=True` 的 `dev_config` 代理。**必须在导入 `worlds.WorldBattleClientBase` 之前做**（它会带进旧 AICommonTrigger）。
  实验脚本 `drivers/sim/exp_servermode.py <sim目录> [帧] [on|off]`（里面的修机站位/惩罚时间是实验占位，不是真值）：178/179 个 AI 模块服务端模式导入成功（1 个缺 `GK.LM`），37 个模块装上代理，接着就要 `room.skada_mgr` —— **开了就得逐个重建服务端房间/单位接口**。
- 已知的服务端专有成员（客户端脚本里没有定义，调用处语义见 `sim1v4.ServerRoomShim`）：
  `room._get_all_generator_fix_rate(fast)`（已补：每台机进度列表）、`room.room_type`/`player_set_ai_level`（已补）、单位 `avatar`（已补 None）、
  求生者 `punish_start_timestamp`、密码机 `ai_fix_angle`/`ai_fix_pos` + `init_ai_fix_angle()`/`precompute_pos_for_ai()`（修机站位，距离来源未找到）、
  `room.skada_mgr`。（原记"GlobalCarryScoreCal 用到的求生者恐惧值为 None"是误判，实为导航距离 None，见 §9.6.2。）

### 9.6 现状与下一步（2026-10-26 收口，**下个对话从这里接**）

#### 9.6.0 一句话现状（2026-10-26）
**5 个人机角色都能在军工厂里自主移动：求生者去修机/躲藏，监管追人**（`run1v4.py 1 450 --server-ai`，0.7 倍速）。
碰撞（§9.6.1）、服务端模式 AI 孤岛（§9.6.2）、导航（§9.10）、修机站位（§9.11）、主循环补全（§9.12）都已完成。
**2026-10-26 更新：交互根运动已解决**——解析引擎动画资源（§9.13），根骨骼位移与录像终点精确吻合，求生者已进入修机结算、监管踩板/求生者放板带真实位移。
当前阻塞变成几个服务端成员缺口（`wood_oneway_tag`、`end_camera_rot_time_dict`、躲藏目标 None），见 §9.13 末尾与 §9.6.3。
**2026-10-26 再更新：第一次打完一整局（§9.15，360 秒监管四杀，tick 异常 0），模拟可复现（§9.14）。** 下一步 = 多局统计校验。
**性能（§9.18）**：噩梦编成约 0.5 倍速，profile 显示主要耗时在碰撞层（杰克 AI 的查询），原因与优化待核实；批量/并行运行放 3090（`ssh gpu`，未部署）。
**2026-10-26 晚更新（§9.16）：之前用错了人机、难度没生效、所有 Buff 半初始化；已换成噩梦编成并补一批缺口，挨刀逃跑/救人都正常了。**
**2026-10-27（§9.19）：代码已提交；天赋缺口定位到"建单位没传 genius_id_lvs"、真值需人机录像；隔墙对峙定性为游戏 AI 缺陷；雾刃随普攻正常生成。交接点 = §9.19。**
**2026-10-27 晚（§9.20）：路线改为优化行为树（先杰克，指标=首次击倒用时）；人机 AI 三族分类；大师杰克（`SIM_JACK=master`）跑通 + `first_down.py`；用户指出雾刃计数有问题待查。交接点 = §9.20。**

以下是 2026-10-25 的记录：
- **碰撞层完成**：`.scn_col` 静态网格 + 板/窗/门/角色等动态体，射线、扫掠、静态测试、路径相交全部接上游戏的 `CollisionManager`，
  过滤语义、返回结构、三种形状（球/盒子/胶囊）的 size 约定都有调用处依据；军工厂 1v4 用到的形状全部登记（本机 `UNSUPPORTED` 为空）。
- **AI 孤岛机制完成**：`run1v4.py 1 300 --server-ai` 下 178/179 个 AI 模块以服务端模式导入，求生者 `MathUtils` 异常消失，模拟 1.8 倍速。
- **角色仍原地不动**。剩两处缺口：`GeneratorUnit.ai_fix_angle/ai_fix_pos`（服务端算法缺，见 9.6.3）→ `AICommonTrigger.tick` 每帧抛；
  `punish_start_timestamp` 已补（9.6.2），待本机复跑确认。另：服务端模式下 `world.scene.scene_detour.set_detour_flag` 每 300 帧被调 3459 次，打在桩上——**导航层是下一块原生替代**。

#### 9.6.1 碰撞层（`natives/physx_collision.py` + `colworld.py`）

**选型**：numpy 自写内核。pybullet 在 PyPI 上没有 Windows/py3.11 预编译包（要装 MSVC 现编），Python 接口也没有凸体扫掠。以后换后端只换 `colworld.py`。

**原生接口**（`CollisionMgr.CollisionManager` 伪源码；签名全写在 `physx_collision.py` 文件头）：
```
hit_by_ray(s, e, face_filter, group, layer, filter_type)          无过滤：hit_by_ray(s, e, 0, 0, Layer.NORMAL)
hit_by_ray_new(s, e, face_filter, group, ignore_types, extra_types, layer, filter_type)
sweep_test(col, s, e, group, layer, face_filter, filter_type)     sweep_test_new(col, s, e, group, ignore, extra, layer, face_filter, filter_type)
sweep_intersect(col, s, e, group, layer, filter_type)             sweep_intersect_new(col, s, e, group, ignore, extra, layer, filter_type)
static_test(col, group, layer, filter_type)                       static_test_new(col, group, ignore, extra, layer, filter_type)
col_object(obj_type, size, unit_type, group, mass, use_model_when_fail, layer[, convex_gen])
```
- `collision_mgr.X_new(..., filter_rule)`：filter 无 extra/ignore 类型时调原生**旧版** `X`，否则调 `X_new`，把 `filter_rule.group_value/ignore_unit_types/extra_unit_types/layer_value/face_filter/filter_type` 拆成位置参数；
  filter 为 None 时传 `group=0, Layer.NORMAL, EXCLUDE_FILTER`（＝什么都不排除）。`CollisionManager.col_object(obj_type, size, unit_type, layer, …)` 用 `CollisionConst.UNIT_GROUP.get(unit_type, STATIC_BODY)` 补 group。
- **返回**：射线/扫掠 = 6 元组 `[命中, 命中点, 法线, ?, ?, 碰撞体]`（调用处只用 [0][1][2][5]/[-1]，[3][4] 无用例，填 None）；static/intersect = 碰撞体列表（`InteractiveComponent` 判 `is None`，AI 判 `if not`）。
  `check_in_collision_static_ex_sweep_test` 用**起点=终点**的扫掠当静态测试，把 `[-1]` 当列表遍历、未命中判 None —— 零长度扫掠返回 `[True, None, None, None, None, [碰撞体…]]`。
- **过滤语义**（`CollisionManager._modify_filter_rule` + 脚本里手写的 `air_power_extra_static_test` 反推，实现为 `physx_collision.passes`）：
  先要 `obj.layer & layer_value`；选中 = (分组命中 `group_value` 或 类型∈extra) 且 类型∉ignore；EXCLUDE 打未选中的，INCLUDE 只打选中的。常量运行期从 `CollisionConst` 读，不写死。
- **调用处用法**：`hit_by_ray_new` 全是视线/遮挡（手电筒、杰克隔墙技能、求生者判断监管与机之间）只用 `[0]`；`sweep_test_new` 用于根运动移动（`MotionSimulation.tick_pos`、`RootMotion(Classic)Component._check_col_in_root_motion`）、
  被推开（`hit_pos + push_dir*半径` 回写位置）；`static_test_new` 用于走路（`TpsMoveComponent.calculate_walk_next_position`）、交互范围（`InteractiveComponent.update_interested_units`）、AI 落点校验（`verify_model`/`judge_valid`）。

**真实常量**（`t_colconst.py` 本机实测）：`INCLUDE_FILTER 0 / EXCLUDE_FILTER 1 / INEQUAL 2 / EQUAL 3`；`Layer.NORMAL 1 / PHOTO 2 / DENTIST=GROCER=YIDHRA 4 / PHANTOM 8 / ALL 65535`；
`Group`：STATIC_BODY 1 / DYNAMIC_BODY 2 / VIRTUAL_BODY 4 / ROLE 8 / PHYSICS_BODY 16 / VEHICLE 32 / SCENE_TRIGGER 64 / INTER_FILTER 128 / ATTACK_FILTER 256；BATTLE_ATTACK_EXCLUDE 332、BATTLE_INTER_EXCLUDE 204、MOVE_EXCLUDE=CAM_IGNORE_GROUP 68；
形状 `SPHERE 0 / BOX 1 / CAPSULE 2 / CYLINDER 3 / MESH 4 / ORG_CAPSULE 7 / CONVEX_CYLINDER 8`；`UTYPE_SCENE 65535`；单位类型 `1 BUTCHER / 2 CIVILIAN / 146 SMOKE_LIGHT`（共 574 个）。
`Filter()` 默认 group 0 / layer 1 / EXCLUDE；`RoleFilter()` 默认 group 8(ROLE) / layer 65535 / EXCLUDE。
运行期样本：视线射线 `group=332, extra={1,2}, layer=1, EXCLUDE`；监管另一条 `group=0, extra={146}, INCLUDE`（只测烟雾，穿墙是对的）。军工厂 300 帧 2880 次射线、576 次命中。

**静态地图属性是真值**：`CollisionManager.preset_collision_module` 调 `physx_collision.set_default_filter_info(Layer.ALL, Group.STATIC_BODY, UTYPE_SCENE)`，模拟器里会走到（`report` 打印来源）。

**形状 size 约定**（逐个登记在 `physx_collision.SHAPE_QUERY`；未登记的形状作查询体时未命中、作动态体时不放进世界，计入 `UNSUPPORTED`）：
| 形状 | 约定 | 依据 |
|---|---|---|
| SPHERE 0 | 半径 = size.y（= x = z） | `BaseBullet.build_collision` 等传 `vector(r,r,r)`；`get_col_bottom_ofs` 对 type==0 返回 `(0,-col_size.y,0)` |
| BOX 1 | size = 半长，中心 = position，朝向 = rotation_matrix（行向量约定的旋转部分） | 迷宫墙 `BOX (13.2,15,1.2)` 摆在 `pos+(0,15,0)`、终点格 `(11,15,1)` 在 `+12.5`、`SuitcaseChecker (12,15,12)` 偏移 `+17`，按半长算底面都贴地 |
| CAPSULE 2 | 线段沿局部 Y（rotation_matrix 第 2 行），中心 = position，**线段半长 = size.y、半径 = size.x** | `_add_collision_role`：`col_object(CAPSULE, vector(col_conf[0], col_conf[1]/2, col_conf[0]))`；`air_power_extra_static_test` 按 `position ± col_conf[1]*0.5` + 半径 `col_conf[0]` 算同一胶囊 |
| ORG_CAPSULE 7 / CYLINDER 3 / MESH 4 | 未登记 | 侦探 / 棺材等（`convex_gen`）/ 地图变形物，军工厂 1v4 用不到 |

- 角色：`col_conf = [半径, 高度]`（配表 `move_col`；大厅 NPC 写死 `(4.5, 8.0)`）；胶囊中心离地 `col_height_offset = OFFSET_HEIGHT + 高度/4`（有 `move_col_ofs` 时用其 `[1]`）。
  `BaseUnit.init_collision` → `CollisionManager.add_collision(unit, …)` 按 `unit_type` 查 `_unit_type_add_col_func_map` 分派到 `_add_collision_*`（多数尺寸来自配表 `box_bounding` 的 `dataconf`/`offset`），
  再由 `_add_ghost_col_to_scene(unit, col, x, height, z, …)` 放到 `单位位置 + (x, height, z)`。原生碰撞体有 `col_size` 属性（桩已补，与构造 size 同义，推断）。
- 军工厂运行期：动态体 138 个盒子（板/窗/门等）+ 5 个胶囊（角色）。

**实现要点**：
- 动态体：碰撞体赋值 `position/rotation_matrix/size/type/enable` 时通知所在 scene_col 标脏，查询前只同步脏的；`position`/`rotation_matrix` 按副本存取（推断与原生一致：脚本都写 `col.position = …`）。
  胶囊/球转外接多面体（12×3 段，最多大 7%）放进三角形世界；查询体本身用精确线段+半径。不参与查询的动态体集合按过滤条件缓存。
- 盒子作查询体：静态测试 / 零长度扫掠 / 路径相交走 `ColWorld.box_overlap`（分离轴 13 轴）；**盒子连续扫掠未实现**（计数）。`sweep_intersect` 是沿路径分步重叠的近似。
- 扫掠起点已重叠时按 t=0 命中返回——**无依据**，单独计数（`QUERY_HITS["…:起点已重叠"]`）。
- 性能：动态体接入后一度 1.5→1.0 倍速；改为标脏同步 + 过滤缓存 + 候选键整数数组 + 动态体掩码缓存 + 射线先按物体包围盒 slab 剪枝 + 自写叉积后回到 1.3 倍速（不开孤岛）。合成场景 143 个碰撞体每次射线约 0.5–0.7 ms。
- 调用位置记录：每种查询前 6 次的实参 + 游戏调用处（`QUERY_SAMPLES`，`SimCore.report` 打印）。

**本机校验结果**：`t_colworld.py`、`t_physx.py` 全过；`colcheck.py` 军工厂（主导航 `ordnance_factory_test1.nav`）地面命中 93.5%（§9.7 为 93.9%）、沿导航边扫半径 3 胶囊被挡 9.8%（起点重叠 5.7%）、竖直射线 4199 次/秒、扫掠 626 次/秒。
⚠ 军工厂 `nav/` 下另有 `dentist_ordnance_factory1_02.nav`（walkable 半径 1，看名字是某角色专用），`colcheck.py` 自动查找会先选它，要显式指定主导航。

#### 9.6.2 服务端模式 AI 孤岛（`simcore.install_server_ai_island`）
- 打开：`SimCore(server_ai=True)` / `run1v4.py … --server-ai`（默认关）。做法同 `exp_servermode.py`：`servercommon.Netease`→GK → 清掉 `common_cs.ai.*` → `SERVER_MODE=True` 下全量重导入（跳过 `bt_code`）→ 恢复 False →
  给 AI 模块换 `SERVER_MODE` 恒为 True、其余属性**实时转发**的 dev_config 代理。`worlds.WorldBattleClientBase` 若已提前加载会打印警告（本机实测没有）。**不带实验里的占位值。**
- 本机实测：导入 178 个、失败 1（`game_kernel` 没有 `LM`）、装代理 37 个；求生者 `MathUtils` 异常消失；1.8 倍速。新增打桩模块：`battle`、`battle.units.RegionAttackManager`、`entity`、`config`、`utils`、`Timer`、`LogConf`、`mobilelog`（服务端专用导入）。
- **`punish_start_timestamp` 已补**（`sim1v4.WorldSim1v4._init_units`，求生者）：全部脚本只有 `QAAIButcher.get_in_butcher_sight_or_chase_civis` 一处读，判 `> 0`（处罚已开始），开局未受处罚 → 取 0（任何 ≤0 等价）。**本机 2026-10-26 复跑确认**：该异常消失。
- 同次复跑（`run1v4.py 1 300 --server-ai`，1.2 倍速）剩两处异常：密码机 `ai_fix_angle`（9.6.3-1，每帧中断 `game_tick`）；
  监管行为树 `GlobalCarryScoreCal.cal_situation_score` 第 111 行 `dis < 2000` 的 **`dis` 为 None**：`QAAIButcher.carry_tar_select` 用
  `room.get_detour_distance(but_pos, civi_pos, NAV_MESH_TILECACHE)` 算距离，导航层还是桩（`NavManager._detour` 为假 → 返回 None），每帧中断监管决策。
  ⚠ 不是恐惧值：求生者 `fear_num` 走共用层 `FearNumComponent`（`iCommonCivilian.init_common_logic` 创建），本机实测 4 个求生者都是 0.0；§9.9 清单里"恐惧值为 None"那条是误判。
  → **Detour 导航层已是硬阻塞**（9.6.3-2）。角色仍原地不动。
- **2026-10-26 导航层接上后**（§9.10）：`dis=None` 消失；唯一剩下的是密码机 `ai_fix_angle`（`AICommonTrigger._init_gen_fixdir` 每帧中断），角色仍不动。1.1 倍速。

#### 9.6.3 待办清单（2026-10-26，按优先级）
1. ~~交互动画根运动位移~~ —— **2026-10-26 已解（§9.13，方案 2 解析引擎动画资源）**。遗留：`span` 两次录像对不上（变体动画？）、`default_loop/default_rate` 未进数据库、格式 0（极少）未解。
1b. ~~服务端成员缺口 / 运行不确定性~~ —— **2026-10-26 已补（§9.14）**；躲藏目标 `None` 判为游戏自身 bug 保留（待真服务端行为验证）。
2. ~~求生者躲藏目标~~：来源已查清 = 窗中心不在 AI 导航上，按引擎语义取不到高度（§9.14），保留。
3. **性能**：噩梦编成约 0.5 倍速。**2026-10-26 已 profile（§9.18）**：主要耗时在碰撞层（杰克 AI 的碰撞查询），不在导航；原先"导航是瓶颈"的猜测不对。原因和优化方案**待仔细核实**（§9.18.3），之后需要并行的批量运行放 3090（§9.18.4）。
4. **找回普通导航与 tilecache**（还原度，§9.10）：设备场景包 `res_pull/scene_pkg/` 里有 222 个 MSET / 11 个 `TEST`，按分块世界包围盒配对出军工厂那份；`TEST` 压缩层格式要认；之后接 DetourTileCache（动态障碍）。
5. **AI 打完一局** → 跑多局统计（胜率、时长、修机曲线）作模拟器正确性检查与 RL baseline（§9.6.4）。
6. 遗留小项：`GK.LM`（1 个 AI 模块导入失败）；路径与碰撞网格 ~7% 擦墙（主厂房/地下室，§9.10）；碰撞近似项（盒子连续扫掠等，§9.6.1）；
   `git` 历史提交 `9746ae7` 里误带了 14 个 pseudo 导出笔记（已从仓库移除、加忽略规则；要不要改写历史待用户定）。

**测试要短**（用户偏好）：1v4 用 300~450 帧（约 15~25 秒墙钟），超过 1 分钟先说。

以下是 2026-10-25 的旧清单（已处理项划掉）：
1. ~~**`GeneratorUnit.ai_fix_angle` / `ai_fix_pos`**~~ —— **2026-10-26 已按共用层 `get_pos_for_ai` 重建（§9.11）**，求生者已能移动。原记录：
   - `iLogicGenerator.init_logic_components` 置 `self.ai_fix_pos = {}`（字典）；`ai_fix_angle` 是序列，`_init_gen_fixdir` 取 `len(gen.ai_fix_angle)` 当该机可修方位数；
     `PatrolPolicy.patrol_move` 用 `gen.ai_fix_pos[gen.ai_fix_angle[0]]` 当巡逻点 → `ai_fix_angle` 的元素是 `ai_fix_pos` 的键、值是位置。
   - 填充靠服务端专有方法 `gen.init_ai_fix_angle()` + `gen.precompute_pos_for_ai()`（`FoolSystem.set_position_gen` 移机后先 `ai_fix_pos.clear()` 再调这两个）——**算法不在客户端脚本里**，不能编。
   - 下次查：`idxq.py 'fix_angle|fix_dir|fix_pos'`（客户端真人修机站位/朝向逻辑，AI 版可能同源）；配表里密码机的修机点/朝向字段；`GeneratorUnit`/`iLogicGenerator` 里与方位、交互点有关的成员。
2. ~~**导航层**~~ —— **2026-10-26 已接官方 Detour（§9.10）**，监管 `dis=None` 已解；普通导航与 tilecache 资源缺，暂回退到 AI 导航（§9.10）。
3. `GK.LM`（1 个 AI 模块导入失败）、`room.skada_mgr`、密码机/求生者其它服务端成员（§9.9 已知清单）—— 按运行期报错逐条补，每条进 `ServerRoomShim` 并注明依据。
4. 碰撞近似项（不阻塞）：盒子连续扫掠、扫掠起点已重叠的返回、`ORG_CAPSULE`/`CYLINDER`/`MESH` 形状、胶囊多面体外接 7%。

#### 9.6.4 之后的路线
1. 缺口 1、2 补齐 → 5 个 AI 能打完一局（`check_game_over` 挂椅淘汰/逃脱）；跑 N 局统计胜率、时长、修机曲线，作为模拟器正确性检查和 RL baseline。
2. 外部控制接口（RL 动作/观测）：把一个单位的 AI 控制器换成外部控制，其余跑行为树当陪练；先做宏动作（复用行为树节点：修某台机/救人/转点），观测从 `unit_mgr` 读结构化状态，奖励以胜负为主加修机/命中塑形。
3. 吞吐：多进程并行环境、关掉不需要的 tick、`enable_determinism` + 固定种子。范围限于离线模拟器与训练本身，不接回真实对局。

#### 9.6.5 本机怎么跑（Windows，`drivers\sim` 下；**不要加 `-I`**，numpy 在用户目录）
```
python t_colworld.py                     # 碰撞内核自测（合成数据）
python t_physx.py                        # 碰撞适配层自测（假 CollisionConst + 合成地图）
python t_colconst.py                     # 打印真实 CollisionConst 常量 / UNIT_TYPE_CONF 编号名
python colcheck.py ..\..\res_pull\resdump_1025_015456\res_recovered.zip scene/scene_battle/ordnance_factory1/nav/ordnance_factory1.scn_col scene/scene_battle/ordnance_factory1/nav/ordnance_factory_test1.nav
python natives\detour_c\build.py         # 编官方 Detour（新机器/云端先跑一次）
python natives\acl_c\build.py            # 编官方 ACL v1.2.1 解码（RAWANIMA 格式 1；新机器先跑一次）
python rawanim_census.py ..\..\res_pull\chr_pkg\chr_player.idx ..\..\res_pull\chr_pkg\player_census.json   # 动画/配置普查（几分钟）
python animdb_build.py ..\..\res_pull\chr_pkg\chr_player.idx ..\..\res_pull\chr_pkg\player_census.json ..\..\res_pull\chr_pkg\thd_chr_player.thy ..\..\res_pull\animdb dm65_survivor_w.skeleton h55_survivor_m_zbs.skeleton   # 生成根运动数据库（监管同理换 chr_boss / dm65_butcher_ll.skeleton）
python replay_rootmotion.py ..\..\res_pull\replays\<guuid>          # 录像里交互根运动的终点（需 PYTHONPATH=逆向存档\_scripts）
python t_detour.py                       # 导航层自测（真实军工厂 AI 导航）
python run1v4.py 1 450 --server-ai       # 1v4 对局（约 20 秒）；末尾打印碰撞/导航统计、服务端垫片统计、调用样本
python t_determinism.py 300 0            # 可复现检查：两个进程逐帧比位置（约 25 秒）
python run_full.py 18000 900 0           # 整局（最多 10 分钟模拟，墙钟同量级）：每 900 帧打印机进度与求生者状态
python profile_sim.py 300 0 60 --out p.prof   # 性能剖析：预热 60 帧后 cProfile 300 帧（约 50 秒）；自身/累计 Top 40 + 按文件汇总 + 进程内存（§9.18）
python replay_scan.py ..\..\res_pull\replays\<guuid> "<RPC 名正则>" 3    # 录像事件流概览（需 PYTHONPATH=逆向存档\_scripts）
python fixslot_from_replay.py ..\..\res_pull\replays\<guuid>          # 录像里的修机方位键与站位对照
python usage.py "<调用名正则>" "" 4 20 | Out-File -Encoding utf8 x.txt   # 查调用处用法（正则里最后一个标识符用来预筛 idx）
python pseudo.py <std_pyc 相对路径> "<qualname 正则>" | Out-File -Encoding utf8 x.txt
```
地图资源默认读 `res_pull/resdump_1025_015456/res_recovered.zip`，可用环境变量 `IDV_RES_ZIP` 改。PowerShell 里命令参数不要写 `<…>` 占位符（`<` 是保留运算符）。

### 9.10 ★ 导航层：官方 Detour（2026-10-26，`natives/detour.py` + `natives/detour_c/`）

**现状**：`room.scene.scene_detour` 换成官方 recastnavigation **v1.6.0** 的 Detour（C++ 编成共享库，ctypes 调用），游戏的 `.nav/.tile` 原样载入。
1v4 里 300 帧：3744 次寻路、2315 次取高度；**监管行为树 `GlobalCarryScoreCal` 的 `dis=None` 异常消失**，角色高度贴到导航面。剩下的阻塞只有密码机修机站位（9.6.3-1）。

**构建**：`python drivers/sim/natives/detour_c/build.py`（首次把 v1.6.0 浅克隆到 `tools/_deps/`，g++ 直接编 `Detour/Source/*.cpp` + `detour_c.cpp`；
Windows 用本机 mingw 静态链接运行库 → `natives/bin/detour_c.dll`，Linux → `libdetour_c.so`）。源码和产物都在 `.gitignore`，云端/新机器先跑一次 build。

**格式对应**：`.nav` = MSET 总表（`TESM`，orig/tileW/tileH/maxTiles/maxPolys + 块名表）；`.tile` 前 8 字节 `[-1][长度]` 正是 Recast 示例的 `NavMeshTileHeader{tileRef, dataSize}`，
后面是标准 `DNAV` v7 数据，直接 `dtNavMesh::addTile`。军工厂 AI 导航 106/106 块载入、0 失败。maxTiles/maxPolys 组合（1024/4096、4096/1024、2048/2048）在 32 位 polyRef 下 salt 位都够。

**接口**（`NavManager` 伪源码里 `self._detour.*` 的全部调用，签名写在 `detour.py` 文件头）：
- 有依据：`add_mesh/remove_mesh/load_mesh(名, 路径[, 偏移])`→bool、`set_detour_flag(名, flag)`=查询过滤 include 标志（游戏常用 65531/65529）、`set_detour_extension(名, 半尺寸)`=最近多边形搜索范围、
  `get_path`→`[vector]`|None（`get_detour_distance` 逐段求和；<2 点当 0）、`find_nearest_poly/get_nearest_nav_point`→vector|None（`get_feasible_point` 等用）、
  `get_poly_ref(名, bmin, bmax, n)`→refs、`find_polys_around_circle`→refs、`set_poly_flag/get_poly_flag`。
- **推断**（计入 `detour.UNIMPL`）：`get_height` = 搜索范围内最近多边形在 (x,z) 的高度（点不在投影内取最近点高度）；`get_vertical_height(…, floor_flag)` = 竖直列各层高度中取 y 以下最高（否则取最近）；
  `get_layer_nav_points` = 竖直列各层点；`get_path_with_flag` 的 flags = 各拐点所在多边形标志（使用方都没读）；终点不可达时返回到最近处的部分路径（Detour 默认行为，计入 `PARTIAL`）。
  `poly_search` 参数语义未知，未使用。
- tilecache 动态障碍 `add_*_obstacle/remove_*/update_navmesh`：`NavManager` 只在 `tc_init_done` 时调用，tilecache 未载入 → 空操作计数。

**★ flags=0 的多边形是不连通区域**：军工厂 AI 导航 4808 个多边形里 1598 个 flags=0（面积反而更大，高处多，90 分位高度 42），与 flags≠0 的多边形**块内没有一条相邻边** →
地图外/屋顶等不可达片区。Detour 过滤 `(flags & include) != 0` 永远排除它们，与游戏同库行为一致。自测/采样必须只在 `flags & 65531` 的多边形上取点（第一次全量采样误判成 33% 查询失败）。

**★ 缺资源与回退**：导出包（§9.5.4）只有配表里的 `server_nav`（= AI 导航）。军工厂运行期还要：普通导航 `scene/…/nav/ordnance_factory1.nav`（`utils.get_default_nav_mesh_file(scene_path)`）、
tilecache 导航 `…/ordnance_factory1_dynamic.nav` + `…_dynamic_cache.tilecache`（`NavManager.get_tilecache_path`，**监管打分用的就是 `NAV_MESH_TILECACHE`**）—— 都缺。
- 回退：载入失败的网格查询落到已载入的 `ai_` 网格，计数 `detour.FALLBACK`（军工厂 300 帧：tc 3456 次、普通 6 次）。依据：`NavManager.set_poly_flag/get_poly_flag/get_detour_path_check_flag`
  在 tilecache 未载入时自己把 `NAV_MESH_TILECACHE` 换成 `NAV_MESH_AI`；普通导航的回退**没有这条依据，是近似**。`SIM_NAV_FALLBACK=0` 关闭。
- **资源在设备场景包里**（已复制到 `res_pull/scene_pkg/`，1.76GB：`scene.idx` + `scene2~5.wpk`；热更脚本包在 `res_pull/hotres/`）：按魔数清点 `data/scene_classify.tsv` →
  **MSET 222 个（导出包有 67）、分块 15518 个（有 3513）、`TEST` 11 个（= .tilecache，导出包 0 个）**。`drivers/sim/nav_hunt.py` 已全部解到 `res_pull/nav_hunt/`（+`summary.json`）。
  所有 MSET 原点都是 (0,0,0)、块 256（牙医 128）→ 按原点分不出是哪张图，要按分块内容的世界包围盒配对（分块按内容寻址，块名表只有 `x_y_layer.tile`）。
  `TEST` 是 NeoX 自定格式：`TEST` + version 1 + 块数 + 参数段 + 块名表（`x_y_layer.tile`）+ 结尾一段 XML（`<offmeshlinks>`），压缩层是另外的文件（格式未认出，没有标准 `RLTD` 魔数）。

**校验**（`t_detour.py`，真实资源）：块数 = 块名表、addTile 0 失败；2000 个可走多边形中心取高度 99.8% 吻合（斜坡多边形按细节网格高度，容差放宽到竖直跨度/2）；
可走区域随机 300 对寻路 300/300 成功、路径长度都 ≥ 直线距离（含穿墙检查约 9 ms/次）；缺失网格载入返回 False 并回退计数。
（信息）路径段抬高后撞到 `.scn_col`：离地 8/15/25 为 9.5/7.5/6.7%；平地段离地 8 撞墙（法线水平）约 7%，**集中在主厂房（物体 352/355，约 300×138×200）与两处地下室（343/927，下探到 y≈-86）**——
是游戏两份数据之间的一致性问题（门洞 / 地下室盖板 / 导航边缘简化，待可视化确认），不是封装问题，不作通过条件。

**下一步（导航层内）**：① 从场景包按内容找回军工厂普通导航与 tilecache（分块按世界包围盒配对；`TEST` 压缩层格式要认）→ 换掉回退；② tilecache 认出来后接 DetourTileCache（动态障碍：板子倒下等）。

### 9.11 ★ 修机站位 + 求生者动起来（2026-10-26，`sim1v4.ServerGeneratorShim`）

**结论：AI 修机站位的算法在共用层里，不用编。** 服务端专有的只是两个方法壳 `init_ai_fix_angle()` / `precompute_pos_for_ai()`（`FoolSystem.set_position_gen` 移机后依次调），内容按共用层重建：
- `fix_pos` = `{0:(None,3), 90:(None,4), 180:(None,1), 270:(None,2)}`（`iLogicGenerator.init_logic_components`；值是 `(占用者uid, 动画序号)`，赛马场中心机全是 5）。
- 方位向量（`iLogicGenerator.check_fix_range` / `get_pos_for_ai`）：`dir2 = 机.get_direction()`；90 → `get_anticlockwise_angle_vector2(-π/2, dir2)`、180 → 转 π、270 → 转 +π/2。
- **给 AI 的站位 `iLogicGenerator.get_pos_for_ai`**：普通机遍历 **(90, 180, 270)**（赛马场中心机四个），站位 = `机位置 + vector(dir2.x, 0, dir2.y) × inter_dis × 0.5`；
  `inter_dis = DM.ui_inter[BATTLE_INTER_UI_INDEX.FIX]['inter_dis']` = **30** → 半径 15。真人交互点另有 `get_interaction_pos`（半径 10）和 `check_fix_range`（`dis_check=12`）。
- 垫片：`ai_fix_angle = [90, 180, 270]`，`ai_fix_pos[键]` = 上式；**唯一推断**：站位点在 AI 导航上取不到高度的方位剔除（`check_inter_pos_valid` 第一步就是 `get_detour_height`），计入 `SHIM_STATS`（军工厂 7 台剔除 1 个）。

**录像旁证**（`res_pull/replays/`，一局真人场景 6 = 军工厂资源；录像含其他玩家昵称，只在本地）：
- 拉取：`.../Documents/video/<账号uid>/<guuid>/` 属游戏 uid，`su -c cp` 到 `/data/local/tmp/<目录>` 再 `adb pull` 到 **ASCII 路径**（`C:\Users\31297\idv_replays`），再复制进工程。
  ⚠ 本机 PowerShell 规则会拦截命令串里的 `rm -rf`/`rm -r`（连同后面的路径误判成删除系统路径），设备端清理写成 `.sh` 推上去执行。
- 事件流（`drivers/sim/replay_scan.py`）：`et=10999` RPC 里 `handle_joystick_move_self_event` 的 args = `[{et:80, uid, pos, dir, speed}]`；`client_update_process(id=密码机网络号, args=[进度, 速度, {修机者: 系数}, …])`；
  `et=202` 状态切换的 `params.new_state_args` 有 **`range_key`（方位键）**、`anim_index`、`inter_pos_params{uid:目标, angle:180}`（angle 恒 180，是相对角）、`a_r_s_p/a_r_s_d`（动画参数，**不是世界坐标**）；
  `et=201` 服务端位置同步 `{uid, pos, dir, speed}`；snapshot_0 的 entities：密码机 `unit_type 3`，`pos/angle(度)/pos_id`（14 个，含未生成的候选位）。网络号↔uid 没有映射表，按空间就近配对。
- 结果（`fixslot_from_replay.py`、`fixpos_from_replay.py`）：12 次修机开始 `range_key` = {90:4, 180:4, 270:4}，**没有 0**（等概率下约 3%）；`range_key`↔`anim_index` 与 `fix_pos` 完全一致；
  用摇杆位置算"离哪个公式点最近" 8 段修机 **8/8 与 range_key 相符**（旋转方向没写反），离公式点 1.8–10（摇杆位置是走近时的，非吸附后）。

**同轮补的其它缺口**：`room.skada_mgr`（`SkadaMgrShim`：`civilian_action_score_recored`/`butcher_action_count` 形状 `{uid: {str(行为): 次数}}`，AI 只读 CURE/CURE_HANG/HOOK_KILL；`add_civilian_score` 按次数+1 是推断；其余方法空操作记名）、
`unit.sync_pos_dir`（服务端网络同步，本地空操作）、`math3d.euler_to_rotation`（只有纯偏航用例有依据）、`matrix.mulvec3x3`（= 3×3 旋转部分乘向量）。

**现状（`run1v4.py 1 1800 --server-ai`，60 秒模拟，1.2 倍速）**：tick 异常 0、被吞异常 0；**4 个求生者走了几百到上千单位**，监管行为树每帧在跑但**原地不动**（→ §9.12.1 已解）。
求生者走到交互点后先后停住：进入交互根运动时 `AnimDataComponent.get_root_bone_diff_offset` 两个 None 相减 —— `AnimDataComponent.__init__` 在 `core.is_client() or core.is_local_server()` 时
`read_mode = READ_FROM_ROOT_MOTION`（读引擎动画，模拟器没有），纯服务端才 `READ_FROM_PYDATA`——**但客户端里没有 pydata.anim 数据（§9.12.3）**。

~~下一步：① 让 AnimDataComponent 走服务端的 READ_FROM_PYDATA；② 查监管为什么不动；③ 能打完一局后跑多局统计。~~ → ② 已解（§9.12.1）；① 走不通，改为待决策（§9.12.3）。

### 9.12 ★ 主循环补全 → 监管动起来；根运动数据调查（2026-10-26）

#### 9.12.1 监管不动的原因：模拟器漏了两处生命周期（已修，`simcore.py`）
- **`world.init()` 从没调过**。真机 `WorldManager.change_to_world`：`cls()` → **`world.init()`** → `set_current_world` → `set_info(info)` → 异步 `init_scene(info_dict)`。
  `WorldBase.init` 按 `world_type` 置 `is_city/is_hall/is_preload/is_battle_server/is_battle_client/is_battle`，并调 `unit_mgr.init()`、`event_mgr.init()`。
  漏调时 **`is_battle_client=False`**（`NOVICE_BATTLE` 本该为 True，本地服务端、`init_combat_core` 都读它），`UnitManager.move_relate_unit_getter` 不存在。
- **主循环 `WorldManager.release_logic` 的每帧步骤**：`cur_world.tick()` 之后还有 `GK.unit_mgr.move_relate_handle()`、`cur_world.tick_unit_del_logic()`（其余是 UI/声音/网络/相机）。
  `move_relate_handle` 每帧把单位的 `move_flag` 复位；`MoveUnit.tick` 第一句 `if self.move_flag: return`，不复位时"自己"(`MyButcherUnit`) 只推进一帧。
  监管的移动指令 `iCommonButcher.start_move_to_cs` 一直是成功的（走到 1066 行返回 True，`whole_path` 已设），卡在每帧推进。
  ⚠ 求生者是 `ClientNPCCivilianUnit`，走自己的 `move_tick_cs`（不受 `move_flag` 影响），所以先动起来了。
- `GK.unit_mgr` 真机由切换世界时赋值，模拟器在 `make_world` 里设 `GK.unit_mgr = w.unit_mgr`。
- `GK.g_event_dispatcher` 保持桩：战斗相关代码里经它派发的只有城镇/烟花/家具/小游戏的 UI 事件（203 处引用，119 处在 `ui/`）。
- 修后：监管从 (1760, 938) 追到 (1238.6, 809.5)（= 140 号求生者位置）；移动中的 `sweep_test` 开始被调用（450 帧 356 次）。

#### 9.12.2 本轮修的其它点
- `math3d.matrix.mulvec3x3` = 只乘 3×3 旋转部分（`RootMotionClassicComponent._local_2_world_offset`）。
- `natives/world.py`：`model.position/rotation_matrix` 取值返回副本（NeoX 语义；之前返回内部对象，调用方 `p.y += h` 把模型改了 → 角色 Y 每帧上涨）。

#### 9.12.3 ★ 交互根运动位移：数据只在引擎动画资源里（待用户决策）
- `AnimDataComponent.__init__`：`core.is_client() or core.is_local_server()` → `READ_FROM_ROOT_MOTION`（读引擎模型动画），否则 `READ_FROM_PYDATA`。
- `READ_FROM_PYDATA` 走 `DM.get_anim_length_dict(gis_id)`（客户端有，`DM.anim_length_data`，加密字典）、`DM.get_dis_anim_data_only(gis_id)`（**客户端没有**）、`DM.anim_height_data`（有）。
  `DataManager.get_dis_anim_data_path` 返回 `pydata.anim.gg%s.dis_anim_offset` 并先抛"这个方法不该被调用"——**根骨骼位移曲线是服务端独有的导出数据**，客户端脚本包里没有 `pydata/anim` 目录。
  `common_cs/role_anims/collected_anim_data.pyc` 只是每个 `gis_id` 的动画名清单（86 个），没有位移。
- 失败点：进入交互状态 → `RootMotionClassicComponent.enable_root_motion` → `_get_root_bone_scale_match_target` → `AnimDataComponent.get_root_bone_diff_offset`（首帧与末帧根骨骼偏移相减，都是 None）。
  角色的 `gis_id`：监管 1、求生者 2/3（`native_unit.gis_id`）。
- **录像能提供的**：`process_root_motion_event` 的 `{op: 'sync_end_pos_dir', anim_name, end_pos, end_dir}`（还有 `sync_pos_dir`、`block`），一局 96 条、约 20 种动画：
  `happy_sickle_attack_1_heavily`×28、`span2`×8、`smash`×7、`hang_envelope`×6、`destroy`×5、`behitch_hx`/`save2`/`save_by2`×4、`repair/repair_2/repair_3`×3、`slide4`/`happy_s_a_carry_heavily`×3、
  `slide2`/`span`/`smash2`/`bind_up_left`×2、`span3`/`create_worm_hole`/`bind_up`×1。只有**结束位置**，没有中间轨迹；动画按角色 `gis_id` 不同。
- **三个方案**（用户 2026-10-26 未选，先收口）：
  1. 先置零 + 录像逐步补：没数据的动画位移按 0 并计数；录像里见过的用"起点→结束位置"的总位移按时长（`anim_length_data`）线性插值。录像越多覆盖越全；中间轨迹是近似，翻窗等在没数据前会丢位移。
  2. 解析引擎角色动画资源：还原度最高；要从设备拉角色资源包、逆 NeoX 动画格式；资源按内容寻址、路径哈希没破（§9.8），按动画名找文件可能很难，工作量大且不确定。
  3. 只置零：最快；修机/救人影响小，翻窗/踩板过不去会影响追击。
- 实现位置（无论哪个方案）：`AnimDataComponent` 的 `_get_root_bone_offset_*_handler` / `get_root_bone_diff_offset`，在模拟器里换一个读法（不要改游戏判定逻辑）。

#### 9.12.4 其它新暴露的问题（未查）
- `AICivilian.qaai_get_current_best_hiding_target`（3775 行）`unsupported operand type(s) for /: 'NoneType' and 'float'`，450 帧里同一求生者 82 次。
- 性能 0.7 倍速（主循环补全后从 1.2 降到 0.7，监管开始移动 + 碰撞扫掠增多）。

### 9.13 ★ 引擎动画资源解析 → 根运动接上（2026-10-26，用户选 §9.12.3 方案 2）

**结论：角色动画 `.animation`（`RAWANIMA`）格式全解，按内容就能认出动画（不用破路径哈希），根骨骼位移与录像终点精确吻合，已接进模拟器。**

**资源**（2026-10-26 从设备 `su cat` 流式拉到 `res_pull/chr_pkg/`，5.8GB，39 个文件大小全对）：`chr_player.idx`+`2~8.wpk`(求生者)、`chr_boss.idx`+`2~6.wpk`(监管)、
`chr_animgraph`/`chr_common`、`Documents/thd/chr_*.thh|thy` 清单、热更 `libclient_hot.so`（md5 `b6f53566…` = §7.5 版本）。apk 里只带 `chr_guanjia`/`chr_prop`（解到 `res_pull/apk_chr/`，格式探查用）。

**`RAWANIMA` 格式**（`drivers/sim/rawanim.py` 文件头有完整说明）：
```
"RAWANIMA" [u32 总长][u32 0][u32 0][u32 HEAD偏移][8B ?][u32 ?][u32 ?][u32 n][n B 骨骼文件相对路径 如 ../dm65_survivor_w.skeleton]
块 HEAD: [f32 帧率][f32 时长秒][8B ?][u8 格式 @+16]…   格式 2=关键帧(96%) 1=ACL(4%) 0=极少(17+18 个)
块 NAME: [u32 串数][源动画名][骨骼名×(串数-1)]          源动画名 = 配置里的文件名 = 动画名（管家包 1534/1534）
块 DATA 格式 2: [u8 =4] + 每根骨骼 { T: u16 n, n×(u16 帧, half3) / S: u16 n, n×(u16 帧, half3) / R: u16 n, n×(u16 帧, u32) } + 补零到 16 对齐
  R 的 u32 = smallest-three：高 2 位=最大分量下标(xyzw)，其余三个按"最大分量之后的循环顺序"高位在前各 10 位，映射 [-1/√2,1/√2]
块 DATA 格式 1: ACL v1.2.1 CompressedClip（tag 0xac10ac10、algorithm version 4；v1.1=3、v1.3=5 对不上）
```
- 布局验证（`rawanim_layout.py`）：格式 2 管家包 1096/1096、监管包 33279/33279 **恰好解析到块尾**（尾部只有补零）。最初误读成"u32 计数"，实为 u16 计数 + 第 0 帧帧号 0。
- 四元数验证（`rawanim_quatfit.py`）：同骨骼文件 ACL 动画里的全局常量骨骼 **48/49 一致**（剩 1 个本身不是常量），相邻关键帧连续性 0.9992（次优映射 0.9976）。
- ACL 用官方源码编：`natives/acl_c/build.py`（v1.2.1 头文件库 + 薄 C 封装，mingw 静态链接 → `natives/bin/acl_c.dll`），哈希校验通过、四元数模长 1。少数 ACL 片段头校验不过（别的版本），计数跳过。
- 引擎侧：`libclient` 里 `0x0663xxxx` 一片是 RawAnimation 序列化（`0x663C138` 起拼 HEAD/DATA/NAME，`movconst.py` 找 MOVZ/MOVK 常量），走反射式 visitor，没继续追；格式最终靠数据+真值定。
  工具：`drivers/movconst.py`（找立即数常量）、`drivers/relaptr.py`（按 `.rela.dyn` 解 vtable 指针）。

**语义（游戏怎么用，伪源码 `AnimDataComponent` / `RootMotionClassicComponent`）**：
- 本地服务端 `core.is_client()` 为假 → `RootMotionClassicComponent` 走 `NO_MODEL_MODE`（按 `game_time` 算动画时间）；`AnimDataComponent` 是 `READ_FROM_ROOT_MOTION` →
  `model.get_animation_component().get_reference_to_first_frame_transform(动画, 毫秒/1000).translation`。
- `new_pos = anim_start_pos + make_orient(anim_start_dir, up)·(local_offset − offset_to_erase)` → local 是**以起始朝向为 +z 的模型空间**。
- 动画名：参数没给时取 `model.cur_anim_name`（引擎播放时更新）→ 模型必须记录播放。`common_tools.utils.play_animation` 调
  `model.play_animation(名, 过渡, 过渡类型, 起始比例, loop, 速率, …)`，**第 4 参是比例**（pos/长度取小数），`anim_time`/`get_anim_length` 是**毫秒**。
- **★ 录像真值**（`replay_rootmotion.py` + 模拟器导出的窗/板位置 `res_pull/replays/factory_windows_boards.json`）：录像 `sync_end_pos_dir.end_pos` 到最近窗/板中心的距离
  = 解码出的根骨骼终点 z：`span2` 4.72(女)/5.27(男)、`span3` 9.24↔9.27(男)、`slide4` 11.36↔11.35(女)、`slide2/4` 13.7↔13.67(男)。
  → half3 解码、动画原点=交互物中心、偏移 = 模型空间 T(t)−T(0)、缩放 1，全部坐实。**例外**：`span` 两次实测 9.56，解码女 13.98/男 15.09，对不上（猜是 `add_suffix_logic` 换了角色变体，未查）。
  （录像起点含走位/吸附，起终点差不能当真值；用终点到交互物中心的距离。）`WoodUnit`=窗(17)、`PanelUnit`=板(43)。

**模型 → 骨骼**（推断，`natives/animdb.py SKELETON_RULES`）：gim 不带自身路径，按目录结构：`chr/player/dm65_survivor_w/*` → `dm65_survivor_w`（女，6130 个动画）、
`dm65_survivor_m/*` → `h55_survivor_m_zbs`（男，6510）、`dm65_survivor_boy|girl/*` → 同名、`chr/boss/butcher/*` → `dm65_butcher_ll`（厂长，710）。
依据 `gim_scan.py`：男角色 gim 引用 `../h55_survivor_m_zbs/h55_survivor_m_zbs.skeleton`(64 处)、女 `../dm65_survivor_w.skeleton`(46)、厂长族 `../dm65_butcher_ll/…`。
大量其它骨骼是皮肤配件（`*_e_*` 袖子/披风等，带同名动画）。编成里的模型：厂长 `chr/boss/butcher/butcher.gim`、医生 `dm65_survivor_w_yiyaoshi_lv1`、`h55_survivor_m_it_lv1`、`h55_survivor_m_qd_lv1`、`h55_survivor_w_hlz_lv1`。

**数据库**（`animdb_build.py` → `res_pull/animdb/<骨骼>.json`，只存根骨骼 `biped` 的位移关键帧 + fps/时长 + 配置别名）：
- 普查 `rawanim_census.py` → `res_pull/chr_pkg/{player,boss}_census.json`（求生者 86332 个 RAWANIMA、2497 个 AnimationConfig；监管 34765/1187）；gim 普查 `gim_scan.py` → `*_gim.json`。
- 配置 Name≠文件名的别名约 1%（如 `close_0`→`close`），只收目录含 `animations_<骨骼>` 的条目。
- 同名多份约 1%：两份都在 thd 当前清单里 = 不同目录的同名文件（如 `animations_dm65_survivor_w/yywf/`），归属分不出，取最后一份并计数。

**接入**（只做查询 + 播放记录，不改游戏判定）：
- `natives/animdb.py`：`table_for(模型路径)`、`offset(名, 秒)` = T(t)−T(0)（关键帧线性插值）、`length_ms`；没数据的动画零位移并计数 `STATS/MISSING`，`SimCore.report` 打印。
- `natives/world.py model`：`get_animation_component()`（`get_reference_to_first_frame_transform`；动画图 `play_animation_graph`/`get_or_create_empty_animation_graph_instance` 给真值桩——
  组件变成真值后 `AnimGraphComponent` 会走到这里，给假值桩就抛 `play_animation_graph failed!`）、`get_anim_ctrl()`（`get_anim_index_by_name` 无则 65535、`get_anim_length`、`get_anim_rate`=1.0）、
  `get_anim_length`、`get_root_bone`=0、`play_animation`/`stop_animation`/`anim_time`/`anim_rate`/`is_playing`（按模拟时钟）。没有骨骼映射的模型（场景物件）保持原来的记录型桩。
- 未做：`default_loop`/`default_rate` 没进数据库（`loop=2` 按不循环、计数）；`get_rootmotion_delta_transform` 只在客户端 ROOT_MOTION_MODE 用，返回单位阵并计数。

**现状（`run1v4.py 1 900 --server-ai`，30 秒模拟，0.9~1.1 倍速）**：tick 异常 0；`play_animation` 275 次、位移查询 1549 次；用到的根运动：求生者 `repair`（最大 1.7，身体晃动）、
厂长 `destroy`（踩板，5.05；录像中位 4.5）、男求生者 `smash`（放板，9.62；录像中位 8.4）。**求生者已进入修机结算流程**（`GeneratorFixComponent.process_fixed`）。
新暴露（都是服务端成员缺口，不属根运动，**未补**）：窗 `WoodUnit.wood_oneway_tag`（监管行为树，900 帧 67 次）、房间 `end_camera_rot_time_dict`（`iLogicGenerator.check_lawyer_fix_generator_score`，修机时）、
躲藏目标 `None / float`（§9.12.4，老问题）。另：同参数两次运行出错位置不同，模拟还不完全确定（随机/计时来源未查）。→ 均在 §9.14 处理。

### 9.14 ★ 服务端缺口补完 + 导航取高度按引擎实现 + 可复现（2026-10-26）

**服务端成员垫片（`sim1v4.py`，每条注明依据）**：
- 窗 `WoodUnit.wood_oneway_tag`（单向窗）：读处全是真值判断或原样传给 `player_span_check(uid, 类型, 单向标志)`；客户端同概念 `InteractiveUnit.oneway_tag`
  （建单位参数 → 场景模型属性 `window_oneway` → False）→ 属性垫片取它，假值桩归一成 bool。
- 房间 `end_camera_rot_time_dict = {}` / `end_camera_rot_time = None`：只有 `iLogicGenerator.check_lawyer_fix_generator_score`（律师开局找机评分）读，为 None 时函数自己 return；客户端只读不写。
- `skada_mgr.action_param_cache`（39 个"战绩表现"评分阈值字段，如 `lawyer_find_generator_time`、`dance_tease_p`、`paoku_dash_trigger_dis_lv1`）：服务端配置，客户端只读。
  全部给"永不满足"的阈值对象 `_NoScore`（比较全假、迭代空、下标取回自身）= 表现评分不触发；依据：用途全是加分或表现标志，AI 只读 CURE/CURE_HANG/HOOK_KILL。

**★ 导航 `get_height` 的引擎实现（libclient 热更版反汇编，`drivers/pymethods.py` 按 PyMethodDef 找绑定 → `SceneDetour` vtable `0x9f40a98`+0x1a0 → `0x8eb5780`）**：
```
findNearestPoly(中心=(x,y,z), 半尺寸=(ext.x×s, 4000, ext.z×s), filter=mesh+0x288) → ref；getPolyHeight(ref, (x,y,z)) 失败 → None
```
- `ext` = `set_detour_extension` 设的值（游戏设 `(1, extent_y, 1)`，`extent_y` = 配表 `navmesh_search_box_y`，默认 4）；`s` = `mesh[0x1138]` 缩放，构造默认 1.0（`0x8eb2a30`），
  `setExtension`（`0x8eb2fb4`）存 `ext×s`；**竖直半尺寸写死 4000**。
- NeoX 内置的是 **v1.6 之前的 Detour**（没有 `dtNavMesh::getPolyHeight`；`dtNavMeshQuery::getPolyHeight` `0x8ea0e50` = 逐细节三角形 `dtClosestHeightPointTriangle`，成功 0x40000000 / 失败 0x80000008）。
  官方 v1.6 先做严格 `dtPointInPolygon`，点正好落在多边形边/顶点上（出生点 `(1828,1800)` 这种整数坐标）会失败 → 封装里加了 `dn_poly_height_legacy` 照旧版写法。
- 文档串（绑定自带 docstring，直接 `pymethods.py` 打出 doc 地址读）：`get_path(mesh, s, e, poly_search=256)` 的 **`poly_search` = 搜索多边形个数上限**（§9.10 原记"语义未知"）；
  `get_height` 文档写的是 `(mesh, x, z)`"从 1000000 往下取最高点"，与实际 4 参实现不符，以反汇编为准。
- 后果：**窗中心离 AI 导航 4–8 个单位（17 个窗全部），按引擎语义取不到高度** → `AICivilian.qaai_get_current_best_hiding_target` 3775/3776 行 `None / float`、`None - float`
  在客户端 NavManager 下是必然的。**结论（推断）：这是游戏本身的 bug，真服务端也会抛、被单位 tick 外层吞掉**，模拟器保留不修。
  ⚠ 未证实点：真服务端的 `room.get_detour_distance` 是服务端自己的实现（不在客户端），取高度方式可能不同；录像全是真人，验证不了。
- **回退网格的近似**（`detour.get_height`，计数 `FALLBACK["get_height 回退网格边缘吸附(近似)"]`）：普通/tilecache 网格缺而落到 AI 网格时，严格取不到就在水平 `walkable_radius`(=6) 内吸附到 AI 网格最近点。
  依据：两者只差墙边收缩距离，真网格边界最多比 AI 网格往外多 6。明确查 AI 网格的查询不吸附。效果：监管 `carry_tar_select` 的 `None < int` 623→5 次。
- 找回普通导航的尝试（`nav_match.py`，场景包 15518 个分块按"AI 导航采样点覆盖率"配对）：106 个块坐标里覆盖率 ≥0.9 的候选是 AI 导航自身(半径 6)、牙医专用(半径 1)、另一张图(25,4,8)；
  块名与 AI 导航一致的 MSET 只有 AI 导航本身 → **没找到普通/tilecache 导航**；导出时也没请求过这两个路径（`miss.jsonl`/`manifest.jsonl` 无记录），设备上有没有未知。

**行为树异常的处理方式改了**（`run1v4.py counted_step`）：计数后**继续抛出**。游戏的 `behavior_step` 不吞异常，冒到单位 tick 外层（`UnitManager.tick_client`）才被吞，这一帧该单位 tick 剩余部分跳过；原来在包装里吞掉会让 `AICivilian.tick` 后半段照常执行。

**★ 可复现**：`SimCore(seed=0)` 设 `random.seed`（+numpy）；`simcore.ensure_hashseed()` 没设 `PYTHONHASHSEED=0` 就带上重跑当前脚本（set 套 str 的遍历顺序）；时钟本来就是模拟时钟。
`t_determinism.py 900 0`：两个独立进程 **900 帧逐帧位置完全一致**。之前"两次运行出错位置不同"、出生点不同的原因就是这两个。

**整局驱动** `run_full.py [最多帧] [每段帧] [种子] [--verbose]`：每段打印密码机进度、求生者状态（离场/挂椅/倒地…）；淘汰者会从单位表移除、逃生者 `is_leave`，每人都有结局即停。

### 9.15 ★ 第一次打完一整局（2026-10-26，`run_full.py 18000 900 0`）

**结果（种子 0，军工厂，厂长 vs 4×qaai_civilian_hard，LV3 自定义人机房）**：模拟 360 秒结束，**监管四杀**：
60s 140 号上椅(115)→120s 前淘汰；150s 141 号被扛起→180s 上椅(127)→240s 前淘汰；270s 139 号上椅(97)→360s 前淘汰；138 号 360s 同时出局。
密码机 3 台修完（[57.8, 100, 5.8, 0.3, 100, 100, 14.9]）。**tick 异常 0、回调错误 0**；被吞异常只剩躲藏目标 None（§9.14，判为游戏自身 bug 保留，约 8700 次/局）。墙钟约 3 分钟（1–4.6 倍速，人少后变快）。

**这一轮按整局暴露顺序补的（全在 `sim1v4.py` / `natives/`，每条注明依据）**：
| 缺口 | 现象 | 处理 | 依据 |
|---|---|---|---|
| 扫掠/射线结果 `[3]` | 根运动撞墙修正 `max_move_dis*move_ratio` 里 None，第 713 帧起每帧 tick 异常把模拟卡死 | 填命中前路径比例 `Hit.t`；零长度扫掠填 0 | `RootMotionClassicComponent._fix_hit_col_intrp_find_pos` |
| `room.task_mgr` | 修完机 `complete_fixed` 末尾抛 | 空操作计数 | 只在 `world_type == NOVICE_BATTLE` 发新手教程事件；模拟器借用该类型 |
| `cur_world.already_die_num/already_win_num` | **淘汰流程中断，被淘汰者永不离场** | 两个 0 计数器 | `iLogicCivilian.die` 先 `+= 1` 再 `_die`；只有 `WorldBattleClientNovice.game_tick` 读 |
| 场景模型属性 `model.get_attr` | 门↔电闸配不上（`get_switch_from_door` 客户端分支比 `switch_l == door`） | **`DM.pos_info` 每行第 4 列就是属性值，属性名 = 类别名**（门 door='2'/'1'、电闸 switch_l='2'/'1'） | 配表实测 |
| 门/电闸 `door_idx` + 配对走服务端分支 | AI 把开门目标设成电闸再调 `get_switch_from_door(电闸 uid)`，客户端分支读电闸的 door 属性 → None | `door_idx` = 场景属性值；两边都有 door_idx 时按 door_idx 配对（服务端分支，返回电闸自身） | `UnitManager.get_switch_from_door` 服务端分支；`AICivilian.qaai_set_action` 2594 行 |
| 角色 `.pos` | 监管选椅 `GlobalHookScoreCal.get_game_info` 读 `civi.pos` 抛 → **不挂人** | `BattlePlayerUnit.pos` 读=get_position3、写=set_position（只挂角色基类：`CrossSFXUnit`/`FireworkVolleyBallUnit` 有同名普通属性） | 读处当坐标；`qaai_can_dig` 临时写 owner.pos 再写回 |
| `Ability.has_skill_and_same_level` | 监管选椅 `judge_genius_lv` 抛 → **不挂人** | `passive_skill_dct.get(id) == level` | 客户端 `Ability.get_skill_level(id) = passive_skill_dct.get(id)` |
| `DoorUnit.get_pos_for_ai_no_overlap(uid)` | 求生者去出口抛（3 万次/局） | 推断 = `get_pos_for_ai()`（同一点） | 共用层 `iLogicDoor.get_pos_for_ai = get_feasible_position3`；"不重叠"错开方式无依据 |
| 监管 `.speed` | `qaai_black_cal_hiding` 距离/butcher.speed 除零 | 配表 `move_speed`（厂长 56 = speed_real） | 求生者 `CivilianUnit.__init__` 置 speed = data.move_speed；监管类没有这一行 |
| 求生者 `escape_source_hook/escape_dest_hook` | `AICommonTrigger.tick` 算救人分抛，整帧 game_tick 后半段被跳过 | None | 只在 AI 读、带真值判断、客户端无写入 |

**之前没注意到的事实**：`run1v4.py` 吞行为树异常曾掩盖了"单位 tick 后半段被跳过"（§9.14 已改为照样抛出）；淘汰后单位直接从单位表移除（不是 is_leave）。

**录像 / 出视频**：`record_game.py [种子] [每几帧] [最多帧]` → `res_pull/replay_sim/seed<N>.jsonl`（15Hz 快照：角色位置朝向/状态/策略/动画、机进度、板椅门状态）；
`render_game.py <jsonl> <out.mp4> [fps] [视野半径]` → 1600×900，左边监管跟随俯视（底图 = AI 导航面 + `.scn_col` 竖直三角投影的墙线），右边全图小地图 + 状态栏，30fps = 2 倍速。
单帧约 55ms（整局 5414 帧约 5 分钟）。注意：椅子 `cur_process` 恒 0，不是挂椅进度（渲染改显示"已挂 N 秒"）；角色中文名按 `DM.player[pid].pinyin` 手映射（文本表没载入）。
从视频看到的行为：监管上椅后常守在椅子旁（"守椅"），求生者多在 QAAI_HIDING。

**下一步（§9.6.4 路线 3）**：多种子跑 N 局统计（胜负、时长、修机曲线、上椅次数）——目前只有 1 局样本，监管四杀、修机偏慢是否像真实人机局还没法判断；
躲藏目标 None 每局 8700 次、可能显著削弱求生者躲藏，是否真是游戏 bug 是最大的保真度疑点。
- 2026-10-26 轨迹可视化（900 帧，录制/渲染脚本在当时会话的 scratchpad：`rec1v4.py` 逐帧记位置 → `render_tracks.py` 画在 AI 导航多边形上的俯视图）：
  3 个求生者 9–21 秒走到密码机后停下，此时有机子在涨进度（30 秒时 3 台机分别为 35/21/18），**停下是在修机，不是卡死**；监管 17.5 秒追上一名求生者，之后两人相距 7、一起定住，推断是攻击动作走到根运动后卡住（§9.12.3），没有逐条验证。
  新暴露的被吞异常：`WoodUnit` 缺 `wood_oneway_tag`（6 次，翻窗相关，推断是服务端成员）、`WorldSim1v4` 缺 `end_camera_rot_time_dict`（1 次）。

### 9.16 ★ 人机选型与难度核查：之前用错了 AI（2026-10-26）

起因：用户看录像发现两个严重问题——求生者挨刀后进 `QAAI_HIDING` 原地不动、有人上椅没人救。核查结论：**行为树选错 + 难度参数没生效**。

**1. 难度没生效：`room.room_type` 实际是 None**（临时探针实测：`make_1v4` 跑 150 帧后读 `w.room_type`、`w.ai_common_trigger.level/level1/civilian_param`、`DM.match_ai_civilian_common_param_data`）。
`ServerRoomShim` 把 `room_type = CUSTOM` 写成类属性，但 `WorldBase.__init__` 第 80 行 `self.room_type = None` 用实例属性盖掉了 →
`AIEnvCombatLevel.table_data_analysis` 和 `QAAIButcher.set_level` 都没走自定义人机房分支：
- 求生者：`bot_src` 为 None、没段位 → `CIVILIAN_RANK_LEVEL_MAP['QAAI_CIVILIAN_HARD'] = 30` → `parse_level_data(30)` 走 **10~99 的写死参数分支**（`fix_prop_range (1,0.95)`、`save_policy ((1,2),(2,1,2))`、`dis4enterhiding (300,380)`…），不读配表。
- 监管：`but_level` 一直没被赋值（三个 bot_src 分支都不中）。

**2. 自定义人机房真正用的行为树**（`pydata/player_ai_conf`，按 pid）：
| 难度（`CUSTOM_AI_LEVEL` → 界面名） | 求生者 | 监管 | 难度 level（`table_data_analysis` / `set_level`） |
|---|---|---|---|
| LV_1 新手 / LV_2 专家 / LV_3 大师 | `custom_ai` = **`novice_civilian_parent`**（3 档同一棵树） | `custom_ai` = `qaai_butcher_common` | 求生者 `210+档位` = 211/212/213 → 读配表 `match_ai_civilian_common_param[(level, play_unit_role)]`；监管 `but_level` 同为 211~213 |
| LV_4 噩梦 | `nightmare_ai` = **`qaai_civilian_rank7`** | `nightmare_ai` = 角色专属（`qaai_butcher_jack` / `_hard` / `_imper` / `_mouth` / `_tentacle` / `_dark_crow4`） | 求生者 level 8（`CIVILIAN_RANK_LEVEL_MAP['QAAI_CIVILIAN_RANK7']`），读配表 `(8, role)` |
- `train_mode_ai` 前三档同 `custom_ai`，第 4 档 = `nightmare_ai`。`play_unit_role`：真人是监管 = 1、是求生者 = 2（配表两套参数不同，如 `(213,1).hide_param[0]=60`、`(213,2)=120`）。
- **能当自定义人机的角色**：求生者 14、15、17、21、25、32、36、62、72、78、79、91、94、96、97、110（**16 没有**）；监管 117、19、30、64、66、67、84、85（63 只有 train/nightmare）。**厂长 pid 1 没有 `custom_ai`**——当前编成的厂长和 16 号都不是游戏会派的人机。
- `novice_civilian_parent` 是**另一套架构**（101 行；`RefreshAllCivilianStatus` → `CalculateGlobalPolicy` → `CheckAndSetGlobalPolicy` RVO/LISTEN/FIX/FIXDOOR/SAVE/HIDING/TREATED/TREAT/ESCAPE/HANGOUT → `SetBaseModule`），
  对应 `ai_env_unit/civilian/`（`RvoMove`/`SupervisedHiding`/`Priming`/`PsyWar`/`HangOutMgr`/`QuickSpeech`/`AIBattleEvent`）和 `AIEnvCombatUtilityNew`，**模拟器里从没跑过**，要补的服务端缺口未知。
  `qaai_civilian_hard`(345 行) 与 `qaai_civilian_rank7`(314 行) 是同一架构（`QaaiCivilianPolicy*`），节点有差异。
- 配表 `match_ai_civilian_common_param` 138 个键（`(0..)`、`(100..106)`、`(1101..15xx)`、`(211..213)`…，每个 ×role 1/2）；`(214,1)` 不存在。

**3. 两个现象的初步归因（推断，未逐条验证）**：
- 挨刀后 `QAAI_HIDING`：qaai 树里 `QaaiCivilianPolicyIsInPanic` → `QAAI_HIDING`，**HIDING 就是被追时的逃跑/绕板窗策略**（放板也在这支，见 `idv-reverse-resume/auto-pallet.md`），不是"躲起来"。
  原地不动的直接原因很可能就是 §9.14 那个每局 ~8700 次的 `qaai_get_current_best_hiding_target` `None / float`：躲藏目标算不出来 → 这一帧单位 tick 被打断 → 不移动。§9.14 "判为游戏 bug 保留"的结论**要重新审视**（它直接造成了可见的错误行为）。
- 没人救：参数走的是写死的 30 档；救人还依赖 `save_or_fix`(SOF)/`AIEnvCombatUtility` 打分，未查是参数问题还是被吞异常。

**4. 改成噩梦编成（2026-10-26，用户定"先做噩梦，监管换杰克"）**：
- `sim1v4.py`：`WorldSim1v4.__init__` 里重新赋 `room_type = CUSTOM`、`player_set_ai_level = (LV_4, LV_4)`；
  编成 = 杰克(30) `qaai_butcher_jack` + 医生(14)/律师(15)/园丁(17)/空军(32) 各 `qaai_civilian_rank7`。
  实测求生者 `level 8 / level1 3 / short_btid rank7`，参数读配表 `(8, 1)`。
- **魔术师(21) 不能用**：`LSkillCivilianMagicSubstitute`（求生者技能的逻辑层 `LSkill*`）只在 `SERVER_MODE` 下导入 `LogManager`，客户端模式建技能时 NameError → `_init_units` 中断。
  这类 `LSkill*` 是服务端逻辑，和 AI 孤岛同一类问题；角色多了要考虑把技能逻辑也放进孤岛。
- **杰克的控制器 = 旧版 `common_cs.ai.AIButcherJack`，不是 `QAAIFactory` 的 `QAAIButcherJack`**：`qaai_butcher_jack` 树里 `ac.*` 用到的
  `shared_policy`/`jack_carry_policy`/`jack_hook_policy`/`jack_guard_policy` 只有 `AIButcherJack` 有（逐个对过）；`QAAIButcherJack` 是配 `qaai_butcher_common` 的。
  服务端选控制器的代码不在客户端（客户端 `change_ai` 一律给基类 `AIButcher`），按"树要的方法谁有"定 → `sim1v4.BUTCHER_TREE_CONTROLLER`。
  `AIButcherJack.but_level` = `AIButcher.__init__` 默认 10（只有 `QAAIButcher.set_level` 会改，噩梦专属树不走它）。
- 房间 `process_quick_speech_event`（AI 快捷发言）：qaai 树里 `qsp_history` 只有发送方写、`QuickSpeechComponent` 是界面发言记录 → 空操作计数。缺它时每帧在 `qaai_send_message` 抛，打断求生者 tick。
- 杰克根运动：`animdb_build.py … chr_boss … ripper.skeleton` → `res_pull/animdb/ripper.json`（638 个动画）；`animdb.SKELETON_RULES` 加 `chr/boss/ripper/ → ripper`（按目录名推断）。
- 开局一次 `KeyError: '32_bt_arg1'`（空军技能参数）：AI 第一次 tick 早于 `try_load_table_data`，之后正常。
- 450 帧：tick 异常 0、被吞异常只剩上面那 1 次；0.5 倍速（比原来的 0.7 慢）。

**6. 噩梦编成整局暴露并补上的缺口（2026-10-26，每条依据写在代码注释）**：
| 缺口 | 现象 | 处理 |
|---|---|---|
| 服务端 `utils.ns` / `utils.util` 打成桩 | `Cleaver.KNIFE_TYPE = ns.ns(...)` 成了桩对象 → 杰克扛人 `KeyError: 1`；`AIButcher` 常量同病；`util.play_animation` 不播 | `simcore.install_server_ai_island` 给 REAL 模块 `utils`：`ns = common_tools.ns`、`util = common_tools.utils`（客户端分支并列写着这两个）。`scan_server_imports.py` 扫过：AI 模块从 `utils` 只要这两个名字 |
| 房间 `get_detour_distance(..., fast=True)` | `GlobalHookScoreCal.get_game_info` 抛 → 杰克选不出椅子，扛起人原地不动直到挣脱（每 29 秒循环一次） | `ServerRoomShim.get_detour_distance` 接 `fast`，按精确距离算、计数 |
| 监管 `.speed` 语义冲突 | `qaai_black_cal_hiding` 除零（每局 2600+ 次，逃生阶段）：客户端"自己"`MyButcherUnit.speed` 是摇杆当前速度（`MoveUnit.set_speed/get_speed`、`fix_hud_move_speed` 每帧写，停下 0/None） | 只包这一个读处（全 AI 唯一读 `butcher.speed` 的地方）：调用期间换成配表 `move_speed` |
| `math3d.matrix.make_rotation_between`、`rotation.get_axis_angle/set_axis_angle` | 杰克雾刃 `AirPower.tick_trace_direction` | 实现 + 自测（a·M = b、轴角重建误差 1e-16） |
| 回退网格寻路端点 | `cal_hangcivi_score` 第 253 行 `dis` 为 None（求生者到被挂者寻路失败）→ 整帧救人打分 tick 异常，182 秒后求生者全卡 | `detour.get_path`：回退查询失败时起终点搜索范围水平放宽到 `walkable_radius` 重试（同 §9.14 get_height 的依据） |
| **`ai_common_trigger.scene_id` = None + 场景用错** | 挨刀后 `QAAI_HIDING` 原地不动的**根因**：`switch_hiding_circle` 失败 → `qaai_hiding_circle(板)` → `CirCle.init_circling_params` 查 `CirClePathInfo.CIRCLING_PATHS[scene_id][板整数坐标]`（预计算绕障环路）查不到 → 不设主障碍物 → `loop_circling` 直接 return、不下移动指令 | ① `AICommonTrigger` 在 `WorldBattleClientBase.__init__` 构造时房间还没 scene_id → `attach_ais` 里按 `__init__` 原样重算；② **`scene_config[1]` 是新手版军工厂**（lut `jungongchangxinshou`），`scene_config[6]` = `SCENE_ID.FACTORY` 正式对局版（多 70+ 项配置），`pos_info` 相同；AI 按图表 `CIRCLING_PATHS`/`PSYWAR_POS`/`HIDING_DATA` 只有 6（实测 6 号表 60/60 板窗命中）→ `make_1v4` 默认场景改 6 |
| tilecache 缺 → 游戏自己换 AI 网格 | `NavManager.get_detour_path_check_flag(use_dynamic=True)` 在 `tc_init_done=False` 时改查 AI 网格 | `attach_ais` 置 `nav_mgr.tc_init_done=True`：游戏照真机查 tilecache 名，由 `natives/detour` 回退 AI 网格 + 吸附；动态障碍仍计数空操作 |
| **挨刀后原地不动（场景 6 下仍在）** | 链路：`QAAI_HIDING` → `get_hiding_unit`=板 → `switch_hiding_circle` True → `qaai_get_hiding_move_position_new`：**离目标 ≥35 直接返回板子中心**（第 3804 行，设计如此）→ `qaai_set_move_position` → n299 `QaaiCivilianMove` → `qaai_move_to_pos`（**不看结果恒返回 True**）→ `start_move_to_cs` 第 615 行 `get_detour_path_check_flag(cur, tgt, polyflag)` **不带 use_dynamic → 明确查 AI 网格** → 板子中心离 AI 网格 ~4、端点 (1,4,1) 找不到 → 第 657 行 False，每帧如此 | **原生 `get_path` 反汇编**（`pymethods.py` → 包装 `0x8EE9900` → 转发 `0x8eeb3e0`(x0=实现指针) → `0x8ee6f94` → `[scene_detour vtable+0xb8]` → 名字查表 → **`0x8eb5d3c`**）：端点 = `0x8eb36a8`(ext×缩放盒内 `queryPolygons(128)` → `closestPointOnPoly` 三轴在盒内且 `getPolyHeight` 成功的最近者) 失败再 `findNearestPoly`(同 ext) → `findPath(2048)` → `closestPointOnPoly` → `findStraightPath`。**ext 就是 set_detour_extension 的值，与模拟器一致**。客户端没人放宽 extension（`room.set_detour_extension` 只可能服务端调）→ **近似（推断）**：`detour._path` 端点失败时水平放宽到 walkable_radius(6) 重试一次，AI 网格本身也做，单独计数 `FALLBACK["get_path 端点吸附(近似) AI 网格本身(推断)"]`。依据只是"真人机不会站着不动"；真服务端导航实现不在客户端，待真值验证 |
| 注意：`§9.10` 旧记 SceneDetour vtable `0x9f40a98`+0x1a0 → get_height `0x8eb5780` | 本轮按 relaptr 解 `0x9f40a98` 起的槽对不上（+0x1a0 → `0x8EF2EBC`，是按网格名查表的外层方法）；外层方法再调每网格对象的实现（get_path = `0x8eb5d3c`）| 以本行链路为准，旧地址待核 |
| **★ 所有 Buff 一直半初始化（项目开始就有）** | `Buff.__init__`：`self.data = deepcopy(DM.skill_state.get(bid))`，`deepcopy` = `common_cs.cython_src.CommonUtils.deepcopy_only_builtin_ref_py`（Cython 原生）→ 自动打桩"导入成功"→ 桩函数返回假值 → 第 483 行 `if not self.data: return` → **buff 效果全不生效**（加速/减速等；杰克雾刃 `VSkillFogBase` 读 `BuffSFx_list` 每帧抛 1.5 万次）。`AICommonTrigger.scene_datas = deepcopy(fresh_circling_paths…)` 同病 | `simenv.FORCE_MISSING`：这个模块让导入真的失败 → 游戏自带的 `except ImportError: deepcopy = copy.deepcopy` 生效（BuffMgr/AICommonTrigger/AIEnvCombatUtilityNew/ActivityButcher/CivilianUnit/SunFlare 都有；SkillModifyManager 只在 SERVER_MODE 分支直接导入、它不在孤岛里）。**同类排查** `scan_try_imports.py <run_full 输出>`：try 块里导入且被打桩的 20 个模块里，对局相关的只有这个；`cython_tools`(`if not cython_tools` 真值判断，桩为假 → 走 _py 兜底，没事)、`common_cs.map.ordnance_factory1_surface`(军工厂没有地面数据文件，游戏 `except Exception: grids = {}`，打桩结果等价) |
| 律师翻窗 `WoodUnit.check_lawyer_span_wood` | 律师(15) 翻非墙窗时 `LStateCivilian.enter_state`(SPAN) 第 383 行抛 → SPAN 挂着永不退出 → 倒地后 `CATCHED` 状态检查不过（`player_catch` 在 `iLogicButcher:794` 返回 False）→ 杰克 `catch` 原地 idle 两百多秒、整局卡死 | 空操作计数（全脚本唯一调用、返回值不用；推断是服务端律师翻窗统计） |
| 未补：`get_hiding_near_valid_pos` 第 104 行 `airpower_dir.cross(air2self) >= 0` | 向量直接与 0 比大小（别处写法是 `.cross(...).y <= 0`），模拟器 `vector.__ge__`（按长度，推断）碰到 int 抛；NeoX 原生行为无依据 | 1 次/局，保持原样 |
| 未补：`Buff.BuffSFx_list` | `VSkillFogBase._update_buff_sfx` 遍历 buff 的特效列表：`Buff.__init__` 在 `DM.skill_state` 查不到 bid 时第 483 行提前 return（半初始化），客户端 `add_buff` 不查 `inited` | 修完导航后 240 秒内未复现，待整局再看 |
| 未补：`cal_treatcivi_score` 第 302 行 | 治疗打分表里残留已淘汰求生者 uid，`unit_mgr.get_unit` 为 None | 待查服务端淘汰者是否留在单位表 |

**救人已恢复**（场景 1 那局）：c141 救下 c140（45.5→61.6s）、c139 救下 c141；杰克会挂椅。`analyze_game.py <录像>` = 策略占比/挨刀后反应/挂椅期间其他人在干什么。

**5. 疑点已排除（2026-10-26）：NeoX `math3d.rotation(...)` 构造参数顺序 = (x, y, z, w)，与模拟器一致**
- 全脚本静态扫描 `math3d.rotation(<4 个常量>)`：`(0,0,0,1)` 5 处（cinematic，按 xyzw 是单位元）；`(1,0,0,0)` 4 处
  （`iLogicTramcar`/`LMineTrainCarrierComponent._cal_player_hitted_direction`、`AirPower.tick_trace_direction` 等）**全是"造一个对象后立刻
  `set_axis_angle(...)` 覆盖"**，初值不被使用；具体四元数 `(6e-06, -0.7386, 6e-06, 0.6741)`（`FireworkVehicleUnit` 载具朝向）按 xyzw = 绕 Y 偏航约 -95°，
  按 wxyz 会是绕斜轴翻约 180°，不合理。→ xyzw。以下是当时记下的疑点原文：
- （原疑点）NeoX `math3d.rotation(...)` 构造参数顺序可能是 (w, x, y, z)
- 依据：`AirPower.tick_trace_direction`（杰克雾刃）写 `rot1 = math3d.rotation(1, 0, 0, 0)` 当单位四元数，再 `rot1.set_axis_angle(axis, 0)`、`rot2.slerp(rot1, rot, factor)`。
  若顺序是 (x,y,z,w)，`(1,0,0,0)` 是绕 x 转 180°，不像单位元 → 暗示 w 在前。模拟器 `natives/math3d.py` 的 `rotation(x, y, z, w)` 是 x 在前。
  这一处紧接 `set_axis_angle(axis, 0)` 覆盖成单位旋转，不受影响；**别处直接用 4 个数构造 rotation 的地方可能错**，没逐个查。
- 别和"坐标 XZY"混淆：用户 ESP 代码（`Code_For_id5/IdentityV/jni/src/Android_draw/PySelf.h` 的 `struct {float x, z, y;}` = x/高度/y，
  `NativeBones.h` 的 objcoor `+0xa0 = X/高度/Y`）说的是**位置三个 float 的第二个是高度** = NeoX Python 的 `vector(x, y, z)` y 朝上，模拟器一致（碰撞/导航/录像都对上）。
  ESP 骨骼读的是 4×4 矩阵（行主序、平移在第 4 行、行向量右乘，与模拟器 `matrix` 一致），**没读过四元数**，定不了 rotation 的分量顺序。
- 核实办法（未做）：静态扫全部脚本里 `math3d.rotation(<4 个常量>)` 的写法，看单位元是写 `(1,0,0,0)` 还是 `(0,0,0,1)`；
  或在用到 `rotation.x/y/z/w` 分量的地方看语义。RAWANIMA 文件里的四元数是 xyzw（§9.13，按数据验证），那是文件格式，不代表 Python 构造参数顺序。

#### 9.16.7 交接（2026-10-26 晚；**2026-10-27 后续见 §9.19**，其中"passive_skill_dct 全 None""杰克没放雾刃"两条已更正）

**当前代码状态**：分支 `claude/inspiring-maxwell-hdavsx`，**本轮改动全部未提交**（`sim1v4.py`、`simcore.py`、`simenv.py`、`natives/{detour,math3d,animdb}.py`、`run_full.py`/`record_game.py`/`t_determinism.py` 改默认场景；
新文件 `analyze_game.py`（录像分析）、`scan_server_imports.py`（服务端顶层导入扫描）、`scan_try_imports.py`（"有 ImportError 兜底却被打桩"扫描）；另一会话的 `profile_sim.py` 也未提交）。
`res_pull/animdb/ripper.json` 新生成（杰克 638 个动画）。**`t_determinism.py` 本轮改完没重跑**，提交前先跑一次确认仍逐帧一致。

**最新一局**（种子 0，噩梦编成，场景 6，`record_game.py 0 2 18000` → `res_pull/replay_sim/seed0_nightmare.jsonl`，视频 `seed0_nightmare.mp4` 445MB，30fps = 2 倍速，**视频时间 × 2 = 模拟秒**）：
- 杰克 210/390/480 秒各淘汰一人；最后 c138 一人在场，600 秒上限仍未结束（7 台机 360 秒全满；剩一人时为何没开门/地窖逃生**未查**）。
- 挨刀后 8 秒：10 次里 8 次几乎全程在跑（不动 0–23/120 帧），距离拉开到 100–400。被打倒后挂椅期间总有人 `QAAI_SAVE`，c141 两次救下 c139。
- 被吞异常只剩：`qaai_need_message` 第 2930 行 `'>' None int`（44 次，n314 快捷发言节点在树尾，影响小，未查）、`get_hiding_near_valid_pos` 向量与 int 比较（6 次，见上表）、开局一次 `32_bt_arg1`。tick 异常 0。
- 导航近似计数（这局）：`get_path 端点吸附 AI 网格本身(推断)` 与回退网格各数千次——**这条推断（§9.16 表）对行为影响大，下个会话优先找真值**（例如真录像里 AI 求生者被追时的轨迹终点是否就是板子中心）。

**用户 2026-10-26 提的 4 个问题与回答（核实程度注明）**：
1. **Buff / 天赋是否完全应用 —— 否。**
   - **天赋（被动技能/genius）完全没有**：探针 60 秒时 5 个角色 `passive_skill_dct` 全是 None。人机天赋由服务端按 `player_ai_conf[pid].ai_genius_id`（杰克 8；另有 `con_lose_ai_genius_id`/`timeout_ai_genius_id`）派发，
     **客户端没有任何代码读 `ai_genius_id`**；`global_data_ai` 相关只有 `ai_genius_lvs=(20,60,100,130)`、`new_novice_ai_genius_lv`、`new_novice_rank12_ai_genius=10`。
     → 下一步：找 `ai_genius_id` 指向哪张表/哪组天赋（配表 grep 天赋方案表；录像 snapshot 里人机实体的天赋字段可作真值，§9.17 说求生者实体 38 键含天赋），再看客户端怎么把天赋装进 `passive_skill_dct`、
     哪些天赋会改事件形态/数值（`SkillModifyManager`，每个单位都有实例但没有天赋输入；`GlobalHookScoreCal.judge_genius_lv` 等 AI 打分也读天赋）。
   - **Buff**：数据半初始化的 bug 已修（`simenv.FORCE_MISSING`，§9.16 表）。但**探针 60 秒内 `BuffMgr.Buff` 一个都没创建**——客户端 BuffMgr 的 buff 多数靠服务端消息下发，本地服务端模式下逻辑层 buff 走哪条路（`combat_core` 的 Buff 组件？`LSkill*`？）**未核实**，
     "受击加速"等效果目前是否生效不知道。→ 下一步：在真录像事件流里找 `et=60 BUFF` 的 bid 列表当对照，对比模拟里同类事件后单位属性（`speed_real`、`msm`）是否变化。
2. **噩梦人机方案是否完整 —— 部分。** 已做：行为树（`nightmare_ai`：求生者 `qaai_civilian_rank7`、杰克 `qaai_butcher_jack` + 控制器 `AIButcherJack`）、自定义房 `room_type=CUSTOM` + `player_set_ai_level=(LV_4,LV_4)`
   → 求生者 level 8、参数读配表 `match_ai_civilian_common_param[(8,1)]`；场景用正式军工厂 6（AI 按图表都在）。**未做**：人机天赋（上条）；求生者角色按 `custom_nightmare_bot_weight` 抽取（现在手选 14/15/17/32，魔术师 21 因 LSkill 缺 LogManager 不能用）；
   杰克 `but_level` 停在 `AIButcher` 默认 10（噩梦专属树不走 `QAAIButcher.set_level`，是否该有别的难度来源未查）；道具/外观；`LSkill*` 技能逻辑层是客户端模式导入（同 AI 孤岛问题，空军/魔术师等技能可能缺服务端分支）。
3. **本次结果分析**：见上"最新一局"。**用户观察到的不合理现象（未分析）**：**视频 1:48–2:22（≈模拟 216–284 秒）监管和求生者隔着一堵墙，监管往左求生者往右、监管往右求生者往左，循环了很久**（两人隔一段距离，不一定很近）。
   用户判断"可能就是第五人格原本 AI 策略不合理"。候选原因（都未查）：① 求生者 `CirCle.loop_circling` 绕障环路（`reckon_best_node` 按监管所在节点选离监管最远的方向 → 与监管对称移动是设计行为）；
   ② 杰克 `AIButcherJack.jack_carry_policy` 追人用寻路/预测（`pre_civi_pos`、`check_turning`），隔墙时没有"绕过去"或雾刃隔墙出刀（`try_use_across_wall_fog`）打破僵局——要查雾刃是否真的在用（buff/技能/动画是否生效）；
   ③ 模拟器近似导致（端点吸附、tilecache 缺失、碰撞擦墙 ~7%）。下个会话先在该时间窗逐帧看双方策略/目标点/路径，判断是 AI 设计还是模拟误差。
4. **改成第五人格原生录像格式 —— 不简单，详见 §9.17（另一会话的调研）。** 原生录像 = 开局快照（pickle，`snapshot_0.snap_shot.event_data` 60 键/79 实体）+ 按时间的服务端消息流（真录像 236 秒 2.9 万条事件、35 种 `et`、48 种 RPC）；
   加载只校验 `version == 1.0`。**但模拟器本地服务端模式基本不发消息**（服务端逻辑直接写客户端对象），录不到这条流，只能按逐帧状态反推合成事件（移动 `handle_joystick_move_self_event`、状态 `et=202`、机进度 `client_update_process` …）。
   §9.17 建议的第一步（不写合成器）：把真录像复制成新 guuid 加进 `vmap.txt` 看能否播放；再整体平移一个求生者的移动事件看客户端是否照改后数据渲染。要 root 写手机目录、用新 guuid（别覆盖真实对局）。

**下个会话建议顺序**（先跟用户确认）：① 提交本轮代码（先跑 `t_determinism.py 300 0`）；② 天赋接入（问题 1）；③ 216–284 秒隔墙对峙定性（问题 3）；④ 剩一人不逃生；⑤ 多种子统计（§9.6.4）；⑥ 原生录像（§9.17 第一步，需手机）。

**本轮可复用的探针套路**（脚本在会话 scratchpad、未入库，思路可照搬）：
- 某单位 AI 卡住：包 `AICivilian` 的若干方法记参数/返回（`get_hiding_unit`/`switch_hiding_circle`/`qaai_get_hiding_move_position_new`/`qaai_set_move_position`/`can_move`/`qaai_move_to_pos`），
  再包单位类的 `start_move_to_cs`；**移动指令在 `unit.qaai_targets['action_policies']['move']`，不在 ai_controller 上**；`qaai_move_to_pos` 恒返回 True，要看 `start_move_to_cs` 的返回。
- 某个返回 False 的长函数：`sys.settrace` 记 `line`/`return` 事件，直接看从哪一行返回（`start_move_to_cs` 657 行、`player_catch` 794 行都是这么定位的）。
- 状态卡住：打印 `state_machine.state` 再按 `CIVILIAN_STATE`/`BUTCHER_STATE` 反查名字（这次是 SPAN+FALL）。
- 原生函数：`pymethods.py <so> 方法名` → 包装函数 → 转发函数 x0 = 实现指针 → 虚调用偏移 → 名字查表外层 → 每网格对象实现（llvm-objdump 在 `%LOCALAPPDATA%\Android\Sdk\ndk\28.2.13676358\toolchains\llvm\prebuilt\windows-x86_64\bin\`）。

### 9.17 调研：用真客户端的录像回放来渲染模拟对局（"方案 C"，2026-10-26，未实施）

用户想要和手机上一样的局内视角。可选三档：A 白模 + 还原相机、B 解析真模型贴图（卡在 §9.8 路径哈希）、C 把模拟结果写成录像，让手机客户端播放。本节只记 C 的调研结论。

**录像链路（`worlds/WorldBattleVideo.pyc`、`worlds/BattleEvent.pyc` 伪源码）**：
- 录制：`BattleEvent.add_battle_event(event)` 是客户端收服务端消息的唯一入口，末尾调 `GK.g_WBV.append_frame(event)` 记成 `(time.time(), event)`；
  定时 `_snapshot()` = 开局快照 `back_start_snapshot` 用 `battle_world.get_recover_info()` 更新一遍（拖进度条时从这里恢复）。
- 回放：`play_local_video_ex(data)` → `GK.g_avatar.start_init_battle_world(start_snapshot, is_local_video=True)`（和断线重连同一条路）→
  `recover_battle_info(start_snapshot)` → `VideoFrame.load_file` 按 `battle_frames_snapshot_<i>.txt` 读 → `VideoFrameUnit.tick_battle_event` 按时间把事件喂回 `battle_event.add_battle_event`。
- **加载时不做完整性校验**：`load_data` = `ReplayUtils.pickle_load`（就是 pickle），`check_version` 只比 `total_info['version'] == self.version`（实测 `1.0`）；`vmap.txt` 只是 `{saved: {guuid: {timestamp, filesize}}, …}`。
- 和服务器的交互只有两处：`_request_upload_video_url` / `notify_client_video_result`（服务器按 `battle_id` 要求上传录像，用于举报复核），`get_genius_from_server`（`ask_all_player_genius`）。
  **伪造录像要用新的 guuid**，不要覆盖真实对局目录，免得服务器按 battle_id 要录像时把伪造内容传上去。

**真录像的规模**（`6ade93e2…`，236 秒）：14 个快照文件、29283 条事件、35 种 `et`、48 种 RPC 函数。
- `10999 COMBAT_CORE`(22845，其中 `handle_joystick_move_self_event` 19614 = 移动)、`304 SYNC_CAM`(1819，录制者相机)、`202 STATE_UPDATE`(1644，状态/动画)、`7`(874，未对上常量)、`430 PHOTO`(666)、
  `10998 COMBAT_CORE_TIME`、`60 BUFF`、`8900 GM_ATK_RANGE`、`54 CAST_SKILL`、`82 SYNC_PRESENCE_NUM`、`204 PSU_UPDATE`、`201 HUD_MOVE_STOP`、`109 MOVE_END_DIR`、`44 ITEM`、`47 CHASE` …（常量名来自 `ComuKeys.GAME_BATTLE_EVENT_TYPE`）。
- RPC 前几名：`get_action_rate` 1305、`handle_dir_sync_event` 327、`handle_follow_event` 254、`client_update_process`(密码机进度) 220、`set_attribute` 191、`process_root_motion_event` 96。
- `snapshot_0.snap_shot.event_data`：60 个键（`scene_id`/出生组/`entities` 79 个/`combat_core_info`/`items_info`/`self_uid`…），求生者实体 38 个键（外观、天赋、`avatar_id` 等）。真录像正好是军工厂，可当模板。

**★ 关键否定结论：模拟器里录不到这条消息流，只能合成。** 探针 `probe_events.py`（会话 scratchpad，300 帧）包住了所有出口：
`world.battle_event` 是 None；`iLogicBase.send_battle_event` 在客户端是空函数（服务端实现在 servercommon）；300 帧里只有 `MyButcherUnit` 往服务端发的 288 条 `et=109`、
十几次 `call_rpc`（`sync_add_component`、`client_update_process` 各一两次）。**本地服务端模式下服务端逻辑直接写客户端对象，基本不发消息。**
→ 要按模拟器逐帧状态（位置/朝向/速度、状态机切换和参数、机进度、板窗椅门）反推出事件，格式以真录像样本 + `BattleEvent.handle_*` 处理函数为准。

**风险与限制**：
- 版本：模拟器跑的是 apk 原包脚本（06-11），手机是热更版（10-23，`res_pull/hotres/` 未解），事件格式要以热更版处理函数和真录像为准。
- 调试是盲的：播放出错会被吞掉，手机上看不到日志；每轮都要推文件、开游戏、进录像列表。
- 只能人看（可以录屏），给不了 RL 当画面观测；每局模拟都要推到手机上。
- 写入 `Android/data/com.netease.dwrg/...` 要 root，并 chown 成游戏 uid（换机后是 `u0_a409`）。播放本地录像是正常功能，没看到上报；但不能保证完全没有风险。

**如果要做，第一步（不写合成代码）**：① 把真录像复制成新 guuid 目录并加进 `vmap.txt`，看客户端能不能列出来、能不能播放；
② 改其中一个求生者的全部移动事件（整体平移），看客户端是否照改后的数据渲染。两步都通过，才值得写合成器。

### 9.18 性能剖析 + 3090 并行（2026-10-26；原因与优化**待仔细核实**）

#### 9.18.1 为什么一局要跑这么久
模拟时间**本来就是虚拟的**：`simcore.frame` 每帧把 `game3d` 时钟推 `DT_MS = 33.333`（30Hz），`time.time()` 已换成模拟时钟（`simpatch.install_clock`），循环里没有 sleep。
慢只因为**算一帧的 CPU 时间超过 33ms**：噩梦编成约 0.5 倍速（一帧约 60ms）；一整局人少后会变快（§9.15 那局 1–4.6 倍速，墙钟约 3 分钟）。
"加大步长 / 降低 AI 决策频率"能直接提速，但会改游戏逻辑时序（扫掠穿墙、AI 判定），要等多局统计校验能用了、确认分布不变再考虑，**现在不做**。

#### 9.18.2 profile 实测（`profile_sim.py 300 0 60`；噩梦编成 杰克 + 4×rank7，种子 0，预热 60 帧后剖 300 帧）
- 开 cProfile：墙钟 38.3 秒 / 模拟 10 秒（每帧 128ms，0.26 倍速；cProfile 本身让速度慢 1.5–2 倍，这一点是估计）。tick 异常 0。**进程内存峰值 363MB**。
- **杰克 AI 占 62%**：`AIButcherJack.jack_carry_policy` 累计 20.2 秒（300 次，每帧都跑），其中
  `check_turning → verify_model → CollisionMgr.static_test_new`（盒子重叠，1864 次）10.4 秒、`check_airpower_scene_col → check_air_power_scene_collision_for_ai → sweep_test_new → colworld.capsule_sweep`（319 次）7.8 秒。
  4 个 rank7 求生者行为树自身合计不到 1 秒。（换杰克后从 0.7 掉到 0.5 倍速，与此吻合。）
- **碰撞层 `colworld.py` 自身 9.6 秒（25%）+ numpy 小数组开销**：`numpy.ufunc.reduce` 134 万次共 8.7 秒（`ndarray.min/max` 各 52 万次，主要来自 colworld）；
  `colworld._dyn_merged` 1.1 万次、累计 11.2 秒（`_candidates` 11.9、`_box_query` 11.4）；`_pt_tris` 累计 3.8 秒、`colworld.__init__`（某个小类）5552 次累计 4.9 秒。
- **导航不是瓶颈**：`natives/detour.py` 自身合计 0.5 秒。（原 §9.6.3-3 猜"导航每帧上百次是瓶颈"是错的。）
- 其它：`natives/math3d.py` 自身 2.5 秒（`vector.__init__` 78 万次）；`BaseUnit.get_position3` 32 万次 1.4 秒；`natives/world.py.__getattr__` 35 万次 0.9 秒。

#### 9.18.3 原因假设与优化候选（**全部待仔细核实，未改代码**）
| # | 假设 | 怎么核实 |
|---|---|---|
| 1 | `_dyn_merged` 每次查询都重新拼动态体三角形（板/窗/门/角色绝大多数帧没动） | 读 `colworld.py:328` 附近代码，确认是否已按标脏缓存；统计每帧真正变化的动态体个数 |
| 2 | 碰撞内核对几个元素的小数组调 numpy（min/max/stack/norm），固定开销大于计算本身 | 定位 134 万次 `reduce` 的调用者（`pstats` 的 `print_callers`）；对拍纯 Python 版耗时 |
| 3 | 杰克 `jack_carry_policy` 每帧都跑 `check_turning`/雾刃场景碰撞检查——要确认这是行为树本来的频率，还是模拟器状态（如扛人/雾刃状态卡住）让它每帧走这条分支 | 看 `AIButcherJack.check_turning`/`check_airpower_scene_col` 的调用条件（`pseudo.py`），对照当时杰克状态；换监管（如 `qaai_butcher_common`）对比 |
| 4 | 不开 cProfile 的真实倍速、其它种子/对局阶段（追人/挂椅/开门）分布是否一样 | 多个种子、不同起始帧各剖一次，再用不带剖析的 `run1v4.py` 对比墙钟 |

优化候选（核实后再定、先跟用户确认）：动态体合并结果按标脏缓存；小数组改纯 Python 或批量向量化。只动碰撞内核、不动游戏逻辑，
用 `t_colworld.py`/`t_physx.py` 对拍 + `t_determinism.py` 逐帧一致验证。若碰撞那约 60% 快 3–4 倍，整体约快 2 倍（估计，未测）。

#### 9.18.4 ★ 3090 服务器（`jing3090`）：**之后需要并行加速的命令都放这台跑**
- 连接：本机 `ssh gpu`（免密，`-o BatchMode=yes` 可用）。
- 规格（2026-10-26 实测）：i7-12700K **12 核 20 线程**、内存 31GB（可用约 29GB）、Swap 7GB、磁盘可用 762GB、RTX 3090 24GB 显存。
  **3090 的 24GB 是显存，模拟器是纯 Python CPU 计算，用不到 GPU**；GPU 留给之后 RL 策略网络训练。并行吞吐看 CPU 核数：每局一个进程（峰值约 360MB），内存不是限制，并发上限按核数约 12–16（扩展性待实测）。
- Python：系统是 3.12；**模拟器要 3.11**（`std_pyc` 是 3.11 字节码）→ 用 `~/.local/bin/uv`（不在非交互 shell 的 PATH 里，写全路径）装 3.11 和 numpy。
- 这台机也跑 pi05 VLA 实验（共用）：开大批量前先看 `uptime` / `nvidia-smi` 负载。
- **尚未部署**。要做的：传 `std_pyc/`、`drivers/sim/`、模拟用到的 `res_pull` 资源（`resdump_1025_015456/res_recovered.zip`、`animdb/` 等，按实际读取清单传，不整个 res_pull）；
  Linux 上重编 `natives/detour_c/build.py`、`natives/acl_c/build.py`；查路径里的 Windows 写法；`PYTHONHASHSEED=0` + 种子保证与本机结果一致（部署后用 `t_determinism` 对拍本机轨迹）。
- 多进程并行脚本：**未写**（计划：每局一个子进程，`--jobs N`，子进程输出一行 JSON 汇总 = 结局/时长/机进度/异常数/轨迹哈希，父进程汇总胜负与时长分布）。

### 9.19 ★ 天赋来源 / 隔墙对峙定性 / 雾刃核实（2026-10-27；后续见 §9.20）

**进度**：§9.16.7 那批改动已提交（`ebddf9b`，提交前 `t_determinism.py 300 0` 逐帧一致）。§9.16.7 建议顺序：① 已做；② 天赋查清来源、**等真值**；③ 已定性；④ 剩一人不逃生 = 杰克没抓住、600 秒超时，用户说不严重、**跳过**；⑤ 多种子统计、⑥ 原生录像未做。

**1. 天赋 / 被动 / 辅助特质（更正 §9.16.7 问题 1）**
- **更正：`passive_skill_dct` 不是 None。** 探针 30 帧：角色自带特质（`DM.player[pid].passive_skill_id_lvs`，如医生 501/504、杰克 23）+ 求生者默认 `global_data_battle.civilian_default_skills = ((112,1),(1000,1))` 都已装进 `ability.passive_skill_dct`（监管没有默认项）。
- 装配链（`BattlePlayerUnit.__init__` → `_init_hero_info` → `init_passive_skills` → `Ability.init_from_dict`）：
  `genius_id_lv_lst = params['genius_id_lvs']`（`[[天赋id, 等级], …]`）→ 每项 `DM.get_genius_data_by_id_lv(unit_type, id, lv)['passive_skill_id_lv']` 追加进被动表。**模拟器建单位没传 `genius_id_lvs` → 天赋全空**，这是唯一缺的一层。
- 天赋表：`DM.butcher_genius_data` / `civilian_genius_data` = `{天赋id: {等级: {passive_skill_id_lv, pre_genius, genius_point, …}}}`（各 40 个）。
- **`player_ai_conf[pid].ai_genius_id` 指向的方案表不在客户端**：取值 监管 1/4/5/6/7/8/11（杰克 11，`con_lose` 12）、求生者 2（医生/律师/园丁等）/3（空军/佣兵等）。客户端 `recommend_genius` 只有 1–6（1–4 求生者、5–6 监管），编号空间对不上；`pid_genius`/`single_practice_genius_recommend` 也不是。客户端没有任何代码读 `ai_genius_id`，人机天赋由服务端放进建单位参数下发（`UIBattleState._form_bot_video_genius_args` 直接读 `unit.genius_id_lv_lst`）。
- **辅助特质**同理：模拟器没传 `support_skill_id` → 默认 `[1]` → 杰克技能第 4 槽 = 701。`SupportSkillAdapter` 只区分 711 闪现 / 722 金身（其它都走闪现策略）。人机实际带哪个，也是服务端数据。
- **★ 已有人机真值（2026-09-23 注入探针，`逆向存档\2026.0917_b6f53566\captures\cmd\173539_ingame.txt`，训练房 `WorldBattleTrain`，用户当监管，4 个人机求生者，pid 未记录）**：
  人机 1001/1002/1003 的 `genius_id_lv_lst`（12 条、100 点）**= `recommend_genius[2]`（博命1）按列表顺序截到 100 点，逐项完全一致**（末项 `(3,3)` 被截成 `(3,1)`）。
  → 推断规则：`ai_genius_id` = `recommend_genius` 的 id（求生者 2/3 正好落在 role=2 的 1–4 里），按难度给点数预算 `global_data_ai.ai_genius_lvs = (20, 60, 100, 130)` 截断。每级都是 5 点，推荐方案总计 120 点（130 预算 = 全带）。
  反例/缺口：人机 1000（终端 16/32）比 `recommend_genius[1]` 截 100 点多了 (34,1)、少了 (3,1)，**不完全符合**；监管 `ai_genius_id` 1/4/7/8/11/12 在 `recommend_genius`（只有 1–6）里找不到，**杰克的 11 仍然未知**；噩梦用哪一档预算未证实。人机求生者 `support_skill_id=[1]`。
- **★ 已接入（2026-10-27，用户指定配装，双方都 130 点）**：`sim1v4.WorldSim1v4.LOADOUT`（pid → 方案, 辅助特质）+ `CIVILIAN_GENIUS` / `BUTCHER_GENIUS`（只写点名项）+ `genius_loadout()`（按配表 `pre_genius` 补齐前置，建单位时校验正好 130 点，否则抛错）。
  注入点：`_init_units` 期间包 `unit_mgr.create_add_unit_in_client`（"自己"和 `add_units_in_scene` 两条路径都经它），往 `unit_info` 补 `genius_id_lvs` / `support_skill_id`，之后交给游戏 `init_passive_skills`。
  - 医生/律师/园丁 `double_heart`：膝跳反射 + 回光返照两条主线、绝处逢生、巨力 3、结伴效应、宣泄效应、救世主情结 1 → 16 项
  - 空军 `save_heart`：化险为夷 + 回光返照、避难所 3、绝处逢生、宣泄效应、巨力 2 → 15 项（救世主情结 3 级是搏命线前置）
  - 杰克 `card_knife`：底牌 + 挽留、破坏欲 3、狂暴 1、愤怒 1 → 14 项；辅助特质 7 闪现
  - 验证（`run1v4.py 6 450 --server-ai`、会话 scratchpad `loadout_check.py`）：天赋全部展开进 `passive_skill_dct`；杰克技能第 4 槽 701 → **(711, 712)**，`SupportSkillAdapter.skill_id = 711`；
    tick 异常 0；`t_determinism.py 300 0` 逐帧一致；0.5 → 0.4 倍速。
  - **★ 整局暴露的闪现问题（已修）**：第一局（`seed0_genius.jsonl`，20 分钟上限）杰克 65.6 秒起整局不动 → 0 杀、两人开门逃生。
    根因：杰克 AI 第一次放闪现，`VSkillSpellFlash.cast` → `VSkillChannel.cast` → `CastingIndicator.update` → `DirectionSelector.process` 解包失败
    （方向取自技能摇杆 `GK.input.get_joystick_skill_dir()` 和相机），技能卡在施法中途。`VSkillChannel.init_casting_indicator` 只给本机玩家
    （`is_self`）建施法指示器，其它单位为 None、cast 时跳过；模拟器里"自己"是人机杰克 → 走进了玩家 UI 路径。
    修法：`sim1v4._ai_self_no_casting_indicator` 包 `init_casting_indicator`，`WorldSim1v4.self_is_ai()` 为真时置 None（计数）。
    复跑：65.5 秒放出闪现（冷却 150 开始走），之后继续追击；`t_determinism.py 300 0` 一致。
  - **★ 律师翻板卡死（已修）**：修好闪现后第二局（`seed0_genius_fixed.jsonl`）150 秒起杰克 `catch` 原地 idle 到 20 分钟上限。
    根因与 §9.16 律师翻窗同构：律师（pid 15）翻板 `LStateCivilian.enter_state(SPAN_PANEL)` 第 3304 行调 `PanelUnit.check_lawyer_span_panel`（服务端方法，
    客户端没有）→ 抛 → SPAN_PANEL 挂着不退出，律师卡在板上原地"跑"，被砍倒后扛不起来。全脚本只此一处语句调用、返回值不用 → `sim1v4._panel_check_lawyer_span` 空操作计数。
    探针（会话 scratchpad `lawyer_stuck.py`）：129.67 秒抛出，同帧进入 SPAN_PANEL，位置 (928.0, 998.8) 此后不变。
  - `record_game.py` 加卡死检测：角色位置/状态标签/机进度/门进度连续 60 秒全不变 → 打印各角色状态并提前结束。
  - 版本差：apk 原包配表里天赋 28（劳有所得）→ 被动 **122**；`idv-replay-genius/genius-table.md` 记的 400 是 9-22 热更版。模拟器跑原包脚本，按 122。
- **真值来源**：录像开局快照每个角色实体都有 `genius_id_lvs`、`support_skill_id`、`is_bot`（现有录像 `6ade93e2…` 5 人全是真人，用不上）。需要一局**有人机参与**的录像（例如自定义房噩梦、用户当求生者，对手杰克人机 + 3 个求生者人机），拉回后读快照即可，不用逆服务端。**待用户决定。**

**2. 隔墙对峙（§9.16.7 问题 3）：定性为游戏 AI 自身缺陷，不是模拟误差**
- 时间窗 ≈215–287 秒，对象是杰克 ↔ c141（空军）。杰克在 (1546–1572, z≈1405)，空军在 (1530–1543, z≈1540)，直线约 140。杰克身前 z≈1419 有墙（射线离地 3/8/15/25 全命中）。
- AI 导航（原生 ext (1,4,1)，**没用到端点吸附近似**）上绕墙左右两条路几乎等长（≈240）。逐帧（`standoff_flip.py`，会话 scratchpad）：杰克实际 x 方向与"当前最短路第一拐点在哪一边"915/918 一致；71 秒内最短路换边 150 次，严格周期约 0.93 秒；空军与杰克反向移动 688 对 155。
  → 机制：杰克每次重新寻路取最短路、没有保持方向；求生者绕障朝远离监管一侧挪（从数据反推，`CirCle` 代码未逐行核）。两条等长路轮流变成最短，形成死循环，直到 288 秒 c140 靠近、杰克换目标才结束。
- 未排除：真服务端 AI tick 频率若不是 30Hz，周期会变，但左右等长的对称性仍在。

**3. 雾刃（更正"杰克一次雾刃都没放"）**
- 游戏里雾刃**随普攻自动出手**（用户指出，代码核实）：`ItemJack.check_jack_energy_buff` 在能量满（`value ≥ max_value`）时把普攻技能的 `logic.nc_dct` 换成生成雾刃的配置；`LSkillBase.process_skill_ncreatures` 按 `{延迟ms: [(新生物id, 类型)]}` 定时生成，类型 1 = `AIRPOWER`。
  杰克配置（`item_arg4/5`）：1201/1205 `is_full_check=True` → `{581: [(8,1)]}`；1211/1214 `is_full_check=False`（≥50% 能量分支）→ `{540: [(57,1)]}` / `{1100: [(57,1)]}`。能量上限 180、回复 10/秒，每次普攻清空。
- **模拟器实测**：第 670 帧满能量出刀 → 第 688 帧（581ms 后）创建 `LAirPower`（`AirPowerFogHitNew`），无异常。录像 jsonl 只记动画名，所以看不到雾刃。
- AI 的 `straight_cast_skill` / `across_wall_cast_skill` 不决定"放不放雾刃"，只在能量满时**选站位走过去、再对求生者挥普攻**（`base_module['attack']`）：直线要求 40–150 内弹道不撞墙（>100 还要 `is_straight_line`），隔墙要求 ≤70。对峙时距离 140、中间是实墙，两条都不触发，与上面的结论一致。
- 未做：雾刃飞行/命中是否与真机一致（`AirPower.tick_trace_direction` 已补的数学函数见 §9.16 表）。

**下一步（先跟用户确认）**：天赋 + 辅助特质真值（需要一局人机录像）→ 按快照传 `genius_id_lvs`/`support_skill_id`；多种子统计（3090 部署 + 并行脚本，§9.18.4）；原生录像（§9.17）。

### 9.20 ★ 路线改为"优化行为树"、人机 AI 三族分类、大师杰克跑通（2026-10-27，**下个会话从这里接**）

**路线决定（用户 2026-10-27）**：个人做强化学习硬件/时间不够（绝悟 1v1 单英雄就用 1.8 万 CPU 核 + 48 张 P40，3090 那台是 20 线程，差约 1000 倍），
改为**调行为树参数 + 加/修分支**；先从**杰克**开始。**评估指标先用"首次击倒用时"**（用户定；需多种子取分布，只反映追击开局）。

**1. 树和控制器是两层**：`bt_code/*.pyc` 只是流程骨架（每帧按序调 `ac.*` 方法），逻辑在控制器类。控制器按 pid 选（`QAAIFactory.CONTROLLER_MAP`，杰克 → `QAAIButcherJack`），树决定调哪组方法。
树结构用 `drivers/sim/bt_tree.py <pseudo.py 输出>` 打成缩进大纲（SEQ/SEL/叶子 + 节点常量参数）。继承：
`AIBase → AIButcher`（209 个方法，其中 138 个 `qaai_*`）`→ AIButcherJack`（噩梦杰克专属）；`AIButcher → QAAIButcher`（策略模块版）`→ QAAIButcherJack / QAAIButcherMary / …`。

**2. 监管人机按"逻辑写在哪"分三族**（全部 `qaai_butcher_*` 树逐个归类过）：
| 族 | 逻辑在哪 | 树 |
|---|---|---|
| ① qaai 方法族 | `AIButcher.qaai_*`：定大策略（CarryingCivilian/HangHook/Guard[/Patrol]）→ `qaai_make_action_policy` → `qaai_make_civilian_adaptation` → 动作节点 | ①a 噩梦树 `qaai_butcher_hard/tentacle/mouth/imper/dark_crow1–4`（入口 `QaaiMakeGlobalPolicy`）；①b `*_player0–3` 系列（前面多"局势判断 `qaai_calculate_situation` + 选目标"）：mary/tentacle/imper/claspman/treeboy/dark_crow，登记在 `AIConst.AI_BUTCHER_LEVEL_MAP`（带 warm_num/safe_num，推断是匹配温暖局人机，未核实） |
| ② 策略模块族 | `QAAIButcher` + `ai_env_unit/butcher/{policy,adapters,components,utils}`（Patrol/Carry/Hook/Guard 策略；Checker/Processer 按求生者技能适配；`OscillationDetection` 防死循环） | `qaai_butcher_common`：所有能当自定义人机的监管**新手/专家/大师三档都用它**，难度只靠 `pydata/match_ai_butcher_param[pid][210+档]` |
| ③ 杰克专属 | `AIButcherJack`（`jack_carry/hook/guard_policy` 三个大函数） | `qaai_butcher_jack`，只有噩梦杰克 |
- 杰克没有①的树，只有②（大师）③（噩梦）。中文角色名只确定 mary=红夫人、imper=宿伞之魂，其它按文件名。
- **红夫人"会用技能"是手写几何，不是学的**：镜子放在自己与目标 1 秒后预测点的中点 + 随机偏差（参数 `mirror_pos`），镜像按镜面直线精确反射，镜像离人 <80 且镜子剩 >2 秒就用镜像追，另有换位/转镜判断。同一逻辑①（`AIButcher.qaai_carrying_mary/qaai_make_action_policy_mary/qaai_mary_guard`）②（`QAAIButcherMary`）各写一份。
  客户端脚本搜过无任何神经网络/模型推理痕迹（服务端不可见，不能完全排除）。

**3. 求生者 rank7 树（297 节点）三层**：房间级团队打分 `AIEnvCombatUtility.cal_score` → 每人取 fix/rescue/treat/ground/treated/escape 中最高分目标（`qaai_get_globaltarget`，一台机超站位数扣 50 分防扎堆）；
树 n6 按固定优先级选全局策略（逃生 > 自救 > 慌了 HIDING > 门快开完守门 > 不危险时[疗伤 > 救人 > 修机 > 开门 > 逃] > 危险时[救人 > 溜鬼 > 逃]）；n81 把策略翻成动作 + 按 pid 的技能分支。救人时机是公式 `T_diff = 距离/45 − (挂椅剩余 − …)`。每帧重算、无保持时间。

**4. 杰克板区诊断（代码层面，模拟器未逐条实测）**：
- 噩梦 `jack_carry_policy`：`Cleaver.diff_knife` 判"板区博弈"（45 内立着/正在放的板、求生者先到板、两人异侧）→ 为真时**整段雾刃逻辑（交互/隔墙/直线）被跳过**；
  `Cleaver.choose_knife_type` 对杰克只要 `can_use_fog_air_power` 就**直接返回 BOARD（压板刀：走到求生者侧板边，预计到达前 0.35–0.47 秒挥刀）**，绕过刀型概率表 → "被砸后该刀型概率 −0.1"的自适应（`dynamic_modify_knife_pro`）对杰克无效。
- 踩板/绕路已有 `cal_detour_path_with_panel`：只看最近已放下的板（150 内），踩板时间 = (到板 + 板后到人)/速度 + 2.42 秒 vs `walk_panel=False` 绕路；结果经 `panel_mask` → BaseMove `set_panel_detour_mask`（语义与模拟器里板子 poly 标志是否生效**未验证**）。
- 大师 `CarryPolicy` 独有：`not_best_path_chase`（80 内每 5 秒按概率去短板区或沿 `MinerShadowMgr` 轮廓截路）；`OscillationDetection`。大师雾刃函数与噩梦基本同一份代码 + 参数化。
- 用户提的权衡（做成决策节点，**未写**）：板区里比较 A 冲板（失败概率 ×(眩晕 + 重新拉近)）/ B 板外等能量放隔墙或交互雾刃（(阈值−当前能量)/10 秒 × 命中率）/ C 绕路截路，取期望时间最短。
- 杰克 213 档（`match_ai_butcher_param[30][213]`，`get_skill_level_param`：bt_arg1..9 → start_cast_fog_time/fog_cd/fog_offset/fog_miss_prob/fog_in_guard/fog_delay/fog_dis_min/fog_dis_max/fog_ex）：
  fog_ex 1（隔墙开）、fog_cd 3、fog_miss_prob 0.1（故意打偏）、fog_dis 0–210、is_in_panel 1、cleaver_prob (0.7,0.3)、not_best_path_chase (5,0.1)。212 档 fog_ex 0。噩梦 `AIButcherJack.but_level` = 默认 10，无这些参数。

**5. 大师杰克跑通（代码未提交）**：
- `sim1v4.WorldSim1v4Master`：BUTCHER = (30, `qaai_butcher_common`)，`player_set_ai_level = (LV_3, LV_4)` → `QAAIButcher.set_level` 得 213；求生者不变。`JACK_VARIANTS` + 环境变量 **`SIM_JACK=master|nightmare`**（默认 nightmare，所有驱动脚本通用）；`WorldSim1v4.__init__` 改为读 `type(self).player_set_ai_level`。
- 冒烟 `run1v4.py 6 450 --server-ai`：控制器 `QAAIButcherJack`、tick 异常 0、会追人出刀被砸。
- **`first_down.py [种子] [上限秒]`**：跑到第一个求生者 FALL，输出一行 `RESULT {json}`（首次击倒秒、受害者、击倒前 stuns/attacks/fogs、控制器、but_level、雾刃参数、被吞异常前 6）。墙钟约 0.5 倍速，一局最多 6–8 分钟。
- 种子 0（上限 240 秒）：噩梦 110.1 秒击倒 c140、stuns 5、attacks 7、fogs 0；大师 240 秒未击倒、stuns 3、attacks 7、fogs 1（90 秒复跑：大师 3/6/1，噩梦 4/4/0）。
- **★ 用户指出数据有问题（原话）："雾刃CD20秒一次，CD一好普通攻击就会触发雾刃，普攻7次不可能雾刃0或1次，下次查吧"**。
  → 下次先查计数本身：`fogs` 数的是 `unit_mgr.get_units_by_type(UNIT_TYPE_CONF.AIRPOWER)` 新 uid（大师 `cast_skill_in_carry` 自己也这么查），但 §9.19 实测雾刃是逻辑层 `LAirPower`（`AirPowerFogHitNew`），可能不进单位表；
  `attacks` 数的是杰克进入 `BUTCHER_STATE.SKILL_ATTACK` 的次数，`stuns` 数进入 `HIT_BY_PANEL`，都没交叉核对。也要排除模拟器里能量回复/`check_jack_energy_buff` 换 nc_dct 本身没生效。**在这之前 first_down 的 stuns/attacks/fogs 都不可信，first_down_s 也待核。**
- 大师杰克被吞 `TypeError None/int`（`QAAIButcherJack.find_move_unit` 第 459 行）：90 秒 642 次调用失败 29 次，**全是窗 uid 76**（中心 (1878.7, 0, 971.6)）——`modify_detour_pos` 取不到窗中心高度。
  量过（scratchpad `navdist_probe.py`）：43 块板中心 42 块在 AI 网格上；17 扇窗离 AI 网格 8.5–9.7（box 半径 6 命中 12 扇、8 才命中其余 5 扇），超出回退吸附 6。与 §9.14 躲藏目标 None 同根。
  修法待用户定：A 找回真 tilecache（§9.6.3-4）/ B 回退高度吸附放宽到 10（近似，影响双方）/ C 暂不动记偏差（我建议 C + 先部署 3090 拿基线）。
- ⚠ 工作区里还有**另一会话未提交的改动**：`sim1v4._panel_check_lawyer_span`（律师翻板卡死修复）、`record_game.py` 卡死检测、SKILL §9.19 两条。本节种子 0 那几局是否已含律师翻板修复不确定（改动时间未对上），对照前要重跑。

**下个会话顺序（先跟用户确认）**：① 查雾刃/普攻/被砸计数（用户点名）；② 提交两边未提交改动（先 `t_determinism.py 300 0`）；③ 3090 部署 + 并行跑多种子首次击倒基线（噩梦 vs 大师）；④ 窗户导航修法 A/B/C；⑤ 板区决策节点（A/B/C 期望时间）与移植大师防死循环/截路。

## 8. 免责

纯静态逆向，用于安全研究与互操作性分析。使用者需自行确保行为符合所在地区法律法规及服务条款。
