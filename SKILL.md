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
   碰撞层已完成、AI 孤岛机制已完成，剩密码机修机站位（服务端算法缺）和导航层两处缺口 → **从 §9.6 接着做**。

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
- 动画根运动**不需要**注入：服务端模式 `AnimDataComponent.READ_FROM_PYDATA`，数据在 `pydata.anim.gg*`（脚本包里）。

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
- 配表里**没有任何地方引用 `qaai_*`**：服务端给人机分配 AI 的配置不在客户端，编成自己定（默认厂长 `qaai_butcher_common` + 4×`qaai_civilian_hard`）。
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

### 9.6 现状与下一步（2026-10-25 收口，下个对话从这里接）

#### 9.6.0 一句话现状
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

#### 9.6.3 缺口清单（按阻塞程度）
1. **`GeneratorUnit.ai_fix_angle` / `ai_fix_pos`**（硬阻塞：`AICommonTrigger._init_gen_fixdir` 每帧抛 → `game_tick` 中断）。已知：
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
python run1v4.py 1 300 [--server-ai]     # 1v4 对局；末尾打印碰撞查询/命中/未登记形状/调用样本
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

---

## 8. 免责

纯静态逆向，用于安全研究与互操作性分析。使用者需自行确保行为符合所在地区法律法规及服务条款。
