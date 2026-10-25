---
name: touch-inject-arbitration
description: 做任何「自动触摸注入」功能(自动砸板/自动飞轮/自动校准/连招/自动道具)前必读——触摸注入的仲裁(controller_gate + finger-outside-gate + 单一 owner + 队列 + 设备代际)是什么、不做会怎样(抢手指/卡键/误触/封号)、以及商业外挂 007(第五人格 ESP)这套怎么处理的。含 007 自动砸板/飞轮的完整静态逆向(做到哪、MBA 挡在哪)+ 逐轴对照当前 IdentityV 实现(决策逻辑/触摸设备/内核)。给 Touch::InjectTap 升级用的通用底座,跟具体游戏偏移无关。与 idv-reverse-resume(auto-pallet.md/ruochen-teardown.md 四点六)、007 SKILL(C:\Users\31297\Desktop\逆向\007\SKILL.md §4/§5/§12)配套。
metadata:
  type: reference
---

# 触摸注入仲裁 —— controller_gate + finger-outside-gate(逆向 007 + 对照自研)

> 来源:商业外挂 `007-free.sh`(网易《第五人格》ESP,aarch64 ELF,详见 [[007-skill]] = `C:\Users\31297\Desktop\逆向\007\SKILL.md`)静态逆向 + 对照当前 IdentityV 自研实现([[idv-reverse-resume]] 的 `auto-pallet.md` / `ruochen-teardown.md` 四点六)。
> 2026-10-15 建。**这是做自动功能的通用底座,不含游戏偏移,换游戏照用。**

## 零、一句话 + 何时读

任何「读到游戏状态 → 模拟点击」的自动功能,真手指和注入手指在内核眼里是**同一套 pointer**,会抢。**仲裁 = 决定"现在能不能注入、由谁注入、注入会不会和真手指/其它自动逻辑打架"**。不做轻则卡操作/误触,重则给反作弊送上"人类做不出的输入"直接起封号信号。**加任何 auto-* 功能前读本篇。**

---

## 一、★ 仲裁是什么(机制)

Android 多点触摸:每根手指是一个 **pointer**,带 `pointer id / slot`;一次手势 = `DOWN→MOVE…→UP`,全程 pointer id 不变;游戏把虚拟控件(轮盘/技能键/校准键)绑到"第一个在该区域按下的 pointer"并跟到它抬起。注入点击 = 往同一条输入流插一个合成 pointer。打架就在这。

仲裁四件套(007 的键名直接印证):

| 机制 | 007 键名 | 作用 |
|---|---|---|
| **准入闸门** | `automation.controller_gate=` | 总闸:每次注入前判定"现在能不能动",不通过就拒绝并给**原因**(见 §2) |
| **单一占用权** | `touch.owner=` / `touch.owner_conflicts=` | 同一时刻触摸通道只有一个逻辑 owner;拿不到就拒绝、计 `owner_conflicts++`,不硬插 |
| **手指闸门** | `finger-outside-gate` | 具体条件:真手指相对目标区的位置关系满足才放行(polarity 见 §2 注) |
| **设备代际** | `touch.device_epoch=` + `touch.stale_commands=` | 记录输入设备/触摸状态的"代";前后台切换、Surface 重建、重连会换代,带旧代的命令判 stale 丢弃 |
| **串行队列** | `touch.{requests→queued→injected_downs/ups}`,`dropped_commands`/`worker_dropped_publications` | 所有注入进一个队列、一个 worker 顺序执行;两条自动逻辑(飞轮+校准)不会同时灌,挤掉计 dropped |

一句话:**controller_gate 管"能不能动"、finger-outside-gate 管"这个点能不能碰"、owner 管"谁能动"、epoch 管"命令还新不新鲜"、队列管"别并发"。**

---

## 二、★ controller_gate 的完整拒绝原因枚举(从二进制抠出,硬证据)

`automation.tap_rejected` 会带下列**五个原因之一**(007 反汇编 `0xc3a860~0xc3acec` 是这组原因串的选择器,可读非混淆):

| 原因串 | rodata 地址 | 含义 |
|---|---|---|
| `execution-budget` | `0x3d5e3`(`execution-budget.automation.tap_rejected=`) | **速率/时间预算超限**。决策段 `0xc3a934` 比较 `0x5F5E100 = 1e8 ns = 100ms` 窗口、`0xc3a964` 用 `×0xF4240(1e6)` 做 ms→ns → 两次注入之间有纳秒级最小间隔预算 |
| `cooldown-not-ready` | `0x3a8bb` | 该动作自身冷却没到 |
| `higher-priority-action` | `0x3c14f` | 有更高优先级的自动动作正占用(如校准抢在飞轮前) |
| `threat-type-disabled` | `0x42a11` | 该功能/威胁类型被关(对应服务端 `read_channel_mask` / `degrade-feature` 门控,见 [[007-skill]] §6) |
| `finger-outside-gate` | `0x38bef` | 真手指相对 gate 区的位置条件不满足 |

> ⚠ **`finger-outside-gate` 的 polarity 静态没 100% 钉死**:名字直读是"手指在 gate 外"。两种可能读法——(A) 注入只在真手指**离开目标键区**时放行(避免抢键),finger-outside 是"安全窗口"的名字;(B) 某些自动(如乐师校准)**要求手指在某激活区内**,finger-outside = 不在区内被拒。精确谓词在 MBA 决策码里(见 §4),**留给动态 hook 确认**。无论哪种,§5 的工程改法都成立。

---

## 三、★ 007 自动砸板 / 自动飞轮 —— 完整逆向(做到哪 + 哪被 MBA 挡住)

### 3.0 先纠正:007 里「砸板」和「飞轮」是同一个功能
中文串 `飞轮`/`按下飞轮`/`盖板`/`破裂木板`/`板区` 指同一套翻窗-砸板机制。`settings.*` 全量里自动开关只有 `enable_auto_flywheel`(砸板)、`auto_calibration`、`auto_calibration_musician` 三个;**没有独立 `auto_skill` 开关**——`auto_skill.*` 是底层**注入引擎**,飞轮/校准都往它提交点击命令。

### 3.1 flywheel 状态模型(✅ 从诊断码 `0x1951c40+` 抠出,结构体 `base+0x51a8`)
诊断序列化器逐字段读,得到板子冷却结构布局:

| 偏移 | 类型 | 字段 | 诊断键 |
|---|---|---|---|
| `+0x00` | u16 | **candidates** 候选板数 | `cooldown.flywheel.candidates=`(str `0x40186`) |
| `+0x02` | u16 | **known** 已知板数 | `cooldown.flywheel.known=`(str `0x3ed07`) |
| `+0x04` | u8 | **failure_stage** 失败阶段 | `cooldown.flywheel.failure_stage=`(str `0x3d924`) |
| `+0x05` | u8 | **status** 状态 | `cooldown.flywheel.status=`(str `0x3e2d9`) |

另有 `.has_flywheel=`/`.flywheel_ready=`/`.flywheel_remaining=`/`.flywheel_status=`/`flywheel-missing`(运行时板子对象侧字段)。
→ **007 的"读板子"字段面**。但注意:**具体偏移链不在二进制里**(服务端下发的 offset-VM 程序,见 [[007-skill]] §3)——这几个是诊断结构,不是游戏对象偏移。

### 3.2 决策逻辑 = MBA 混淆(✅ 本轮补验,§12 结论延伸到此路径)
砸板"何时按、按哪块、finger-outside 谓词"落在 `0xc3a9c4` 一带,典型 MBA:
```
eon w12, w13, w11 ; and w13, w11, w13 ; add w11, w11, w12 ; sub w11, w11, w13
= w11 + (w13 ⊕ ¬w11) − (w11 ∧ w13)    // 把简单值用布尔+算术混起来,专拖死 Hex-Rays
```
+ 每变量 spill 到 `[x29,#-0x100]` 怪偏移 + csel 链 + 不透明谓词。**静态不可完整还原,与 [[007-skill]] §12 一致。** 要拿决策算法走动态(§6)。

### 3.3 触摸注入机制 = 自家 wuwa 内核驱动合成(无 /dev/input)
- 全二进制**无 `/dev/input`、`uinput`、`MotionEvent`、`sendevent` 串**(只有 `/dev/null|random|urandom`)。
- → 触摸**经它自己的 wuwa 内核模块合成**(节点 `/proc/inte_ko`,ioctl magic `'E'`=0x45,见 [[007-skill]] §4)。读内存的 24B 通道是 `_IOR`(`0x80184540|idx`);触摸注入需要一个 **`_IOW` 命令(本轮未定位,留动态)**。
- 性质上 = **内核合成触摸**,类似若辰的 TwT/天堂路线,**不是** `/dev/input` 空闲 slot。

---

## 四、★ 逐轴对照:007 vs 当前 IdentityV 自研

| 轴 | 007(商业) | 你当前([[idv-reverse-resume]]) | 差异/启示 |
|---|---|---|---|
| **砸板决策** | MBA 混淆,服务端下发偏移;带 candidates/known/failure_stage/status 状态机 | 若辰 10.1.74 那套已落地(`AutoPallet.h`):板状态 `[[obj+0x750]+0x30]==16`、OBB 判定、监管最近板、冷却 800ms | 逻辑你已有且**可读可改**,007 的抠不出来。你不缺砸板算法 |
| **板子可用性** | `flywheel_ready/remaining` + `failure_stage` 每阶段诊断 | 猜 `state==16`(立着)/ 或走 Python `units_by_type` 木板键 | **可抄:`failure_stage` 式每阶段失败诊断**,热更失效一眼定位 |
| **触摸设备** | **自家 wuwa 内核驱动合成触摸**(无 /dev/input) | `Touch::InjectTap` 走 **`/dev/input` MT type-B 空闲 slot**(= 若辰 RT 模式);你的 `kerneldriver-qxqd.hpp` 只 `socket+ioctl 601~608` **读内存、无触摸命令** | 架构差异:007 单驱动(读+点),你分离(qxqd 读 / dev/input 点)。若以后上内核触摸(TwT/天堂),延迟更低 |
| **内核** | 单一 .ko,自己 insmod,读内存+(推测)触摸同一驱动 | 内存读走 qxqd;触摸不碰内核(走 /dev/input) | 你当前更"轻";007 的驱动功能更合一但也更重/更容易被查 |
| **仲裁(本篇核心)** | controller_gate 五原因 + owner + epoch + 队列 + finger-gate(§1/§2) | 若辰那套门控:同块板点过不再点(直到连续 150ms 无候选)、两次≥800ms、触摸点须在屏内、**QTE 校准进行中不点**、点后记板 | **你有"冷却+互斥"但没有 owner/epoch/队列/finger-gate 的完整体系**。加更多 auto-* 时按 §5 补 |
| **注入共存** | 内核合成,真手指天然共存 | MT-B 空闲 slot 共存(不 EVIOCGRAB、不克隆 uinput);`no_free_slot` 就不抢 | 两边都做到了"不抢真手指",路径不同 |

---

## 五、★ 不处理仲裁的后果 + 给 Touch::InjectTap 的改法

### 后果(从轻到重)
1. **抢手指/卡操作**:假 pointer 和玩家轮盘/技能手指撞 → 角色走着突然停、轮盘回中、你自己的点击被吞(= `owner_conflicts`)。
2. **卡键/幽灵手指**:注入 DOWN 没干净配对 UP(换代、id 错位)→ 游戏以为有手指一直按着,技能连放/移动卡死,要真点一下才解锁(= `stale_commands`)。
3. **误触空放**:命令 stale,点下时状态已变 → 砸板砸空、技能空放、校准点歪,白交冷却(= `failed_injections`/`unavailable_attempts`)。
4. **ANR/输入异常/闪退**:喂进物理不可能的多点序列(id 重叠、UP 先于 DOWN、同坐标两 DOWN)→ InputDispatcher 卡死甚至崩。
5. **★ 封号信号飙升**:无仲裁注入会产生**人类做不出的输入**(另一指还在屏上时凭空多一触点、零位移完美定时点击与真实输入重叠、id 分配不符人类手势)。反作弊正抓"不可能并发触摸/非数字化仪来源输入"。finger-outside-gate 让注入只落在人手空隙里 → 检测面骤减。**仲裁不只为不卡,更为不被抓。**
6. **自家功能互撞**:无单 owner+队列,飞轮和校准同时注入 → 两段手势 DOWN/UP 交错成乱码。

### 给 `Touch::InjectTap` 的四点改法(都不涉 007 混淆逻辑,通用工程)
1. **读真手指**:注入前知道当前有哪些真实 pointer 及坐标(/dev/input 本就在读真设备事件;内核触摸模式下由驱动提供)。目标键区有真手指就**不注入**(= finger-gate)。
2. **单一 owner + 队列**:所有自动点击走一个 worker 串行,一个逻辑 owner,拿不到就排队/丢弃,别并发硬插。你现有"800ms 间隔 + 同块板不重点"是雏形,升级成通用 owner/队列。
3. **DOWN/UP 严格配对 + 换代清理**:每个注入手势自洽;前后台切换/重连(epoch 变)时清掉半截手势。
4. **epoch 打标丢 stale**:给命令打设备代,过期即丢。
5. (已有,保留)**QTE 校准进行中不点** → 正是 007 `higher-priority-action` 的思路:做成优先级表,高优先级动作抢占低优先级。

---

## 六、复现命令 + 锚点 + 下一步

### 复现(本机,2026-10-15 实测可跑)
```bash
f="/c/Users/31297/Desktop/逆向/007/007-free.sh"
OD="/e/android-ndk-r27d-windows/android-ndk-r27d/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-objdump.exe"
# 注意:mingw 自带 objdump(binutils 2.30)不支持 arm64(报 architecture UNKNOWN),必须用 NDK 的 llvm-objdump
"$OD" -d --start-address=0xc3a860 --stop-address=0xc3acec "$f"   # gate 原因选择器(可读) + 决策(MBA)
"$OD" -d --start-address=0x1951c40 --stop-address=0x1951d00 "$f" # flywheel 诊断序列化器(可读)
# 字符串偏移==vaddr(rodata off==addr):dd if="$f" bs=1 skip=$((16#3d5e3)) count=48 | tr -c '[:print:]' '.'
```
IDA 库已存 `C:\ida007\s007.elf.i64`(31079 函数,秒开);字符串→代码 xref 在 `C:\ida007\out_xref.json`。

### 锚点(code vaddr)
- gate 原因选择器:`0xc3a860~0xc3acec`(可读);**MBA 决策核** `0xc3a9c4` 一带;`finger-outside-gate` 引用 `0xc3abd8`
- 执行预算时间math:`0xc3a934`(1e8 ns=100ms)、`0xc3a964`(×1e6 ms→ns)
- flywheel 诊断序列化:`0x1951c40+`(结构 `base+0x51a8`:candidates u16@0 / known u16@2 / failure_stage u8@4 / status u8@5)
- touch 计数 dump:`0xc3cc7c~0xc3cdcc`;controller_gate/touch.owner dump:`0xc85184`/`0xc853f4`/`0xc854d0`
- 原因串 rodata:`execution-budget`=`0x3d5e3`、`cooldown-not-ready`=`0x3a8bb`、`higher-priority-action`=`0x3c14f`、`threat-type-disabled`=`0x42a11`、`finger-outside-gate`=`0x38bef`

### 下一步(动态,接 [[007-skill]] §10/§12.4)
1. **frida hook `auto_skill` 的注入命令发射点**:入参=它决定的点击坐标/slot,出参=结果码 → 拿到决策输出,绕过 MBA。
2. **hook controller_gate 返回点**:观察每次 tap 被判哪个原因、finger-outside-gate 的真实谓词(钉死 §2 的 polarity)。
3. **定位触摸注入的 `_IOW` ioctl 命令号**:hook wuwa 驱动 ioctl,看 touch 用的 magic 'E' 命令 + 结构。
4. 处理反调试/反篡改(TracerPid + 执行器自校验,见 [[007-skill]] §9)后再 hook。
