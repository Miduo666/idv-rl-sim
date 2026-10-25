# 原生骨骼读取 —— 抄若辰的偏移链进我们的驱动/裸读路线（进行中）

> 2026-09-25。目标：让**局内生产读取路线（C++ 驱动 / 跨进程裸读，非注入）**能读到骨骼世界坐标，画骨架。
> **注入只当探针**（探针协议见文末），生产代码零注入。

## ★★ 2026-10-17 复盘：若辰链没复现成，用 007 注入真值夹出分叉（下次从这节接）

**本轮结论（用户给的两个硬约束）**：① 若辰原生链**概念可信**（若辰自己跑通，我们没复现成）；
② **007 注入读骨骼绝对可信（用户亲手复现过）** —— `anim_data_component.get_bone_position(name)`。
所以失败一定在**我们的移植**，不在概念。把两份摆一起夹出分叉：

### 交叉（两份读的是同一份数据）
`get_bone_position(name)` = 引擎做 `(POSE 调色板里该骨骼的模型空间变换) × (模型→世界矩阵)`，
**正是若辰链的最终那步**（POSE 矩阵第 4 行 × `X26+0x1C0` 世界矩阵）。
→ **007 的 `get_bone_position(name)` 输出 = 若辰链最终输出的精确真值，同一个数两条路算。校准就拿它当标尺。**

### 分叉 ①（最可疑：入口名字写错，可能就是我们失败的根因）
本文件上面 line 9 当初活体测的是 **`_anim_data_component`（带下划线）→ None**，据此断定"Python 读不到骨骼"，
才被逼去走 `model+0x20 → [M+0x818]` 那条难链 —— **而我们正是卡在这条链没复现成。**
但 007 载荷（`1_patched.so` 作者载荷 @0x1B33C，line 811-818）用的是 **`anim_data_component`（无下划线）→ 活的**，有 `get_bone_position`，兜底 `model.get_bone_pos(name)`。
→ **存在一个活的 Python `anim_data_component` 对象，内部必持有通往 ANIM/POSE 的原生指针。**
内核不能调方法，但**能像 `PySelf` 裸读 `position` 那样裸读这个对象的原生指针**，直达 POSE —— 绕开失败的 `M+0x818` 入口。
**下次先试这个入口。**

> **★ 2026-10-18 静态坐实分叉①(脚本解包档案,零设备)**：在 `逆向\第五人格_脚本解包_反作弊\all_pyc\` 里 grep：
> `ClientUnits/BaseUnit.pyc`、`PlayerUnit.pyc`、`BattlePlayerUnit.pyc` **同时含 `anim_data_component`(无下划线) 和 `_anim_data_component`(有下划线)**两个名字
> —— 典型的 property + backing 字段模式。**我们当初活体测的 `_anim_data_component`→None 是 backing 字段;007 用的 `anim_data_component`(无下划线)是 property、才是活的。**
> 组件类 = `common_cs/combat_core/components/unit/AnimDataComponent.pyc`(含 `get_bone_position`/`get_bone_pos`/`get_bone_count`，以及 `_anim_index_by_name` 名字→下标表，对应若辰名字逻辑)。
> `get_bone_position` 具体读哪个原生字段**没能静态拿到**:本机无 pyc 反编译器(3.11 pyc,3.13 的 `dis` opcode 不兼容;`marshal.loads` 跨版本直接崩 exit 116;不装 pycdc)。
> 但这步本就该走若辰的原生偏移链(下面已解),不依赖它。**净收获:下次活体探针读 `unit.anim_data_component`(不是下划线那个),确认非 None 后裸读其原生指针。**

### 分叉 ②（对答案用错标尺，会误判成"链错了"）
line 152 记：`get_bone_matrix(0)`=世界、`get_bone_matrix(17=head)`=父相对 —— 引擎访问器是**混合表示**。
但若辰裸读的 POSE 调色板是**模型空间**（所以才统一 ×一个世界矩阵）。
→ **裸读 POSE 数组别拿 `get_bone_matrix(i)` 比（表示不同，必对不上）。正确标尺是 `get_bone_position(name)` 最终世界坐标。**

### 分叉 ③（版本相关常量没落地）
- 名字池全局偏移 `0xAAF0828` 是若辰那版 so 的，我们版 libclient 要重找（或只用每项自带池指针，名字只在首次建"名字→下标"时用）。
- `swap_yz` 按单位拿 `unit.position` 现场校准。
两者错 → "坐标飘"而非"读不到"，拿现象可区分。

### 待办（下次冷启动按这个顺序，探针已就绪）
> 注入探针现成可用：**2026-10-17 已重构 007 = 新代码 + 纯注入 + probe2 命令通道**（见 `injection.md §五`）。
> 合并载荷 `IdentityV\injection-research\payload_probe2_beautify.py`。命令通道 `idv_cmd.py`（今天验证过能用）。

1. **取真值**（007 注入探针，训练局站定）：每个单位 dump
   `get_bone_count()`、每根 `get_bone_position(name)`（世界真值）、`unit.position`，
   外加 **`id(anim_data_component)` 和 `id(model)` 两个原生指针**（PC 侧按 id+偏移裸读用）。
2. **裸读对齐**：devread/驱动从 **`anim_data_component` 原生指针**往下钻找 POSE 数组（**不是** `model+0x818`），
   算世界坐标，逐根对第 1 步的 `get_bone_position` 真值。对上→入口①假设成立；对不上→拿真值逐跳 dump 判是入口还是矩阵数学。
3. **落地**：C++ 骨骼读取模块（类比 `PySelf`，新入口 anim_data_component），接现成投影 + `connections[][2]`（旧 `DrawOverlay`，备份
   `逆向存档\_backup\007_before_refactor_20261017_0015\jni\src\Android_draw\SoHookIntegration.cpp:1413` 起 16 条边）+ 一个「骨骼」开关。
   TARGET_BONES 17 根（spine/head/neck、l/r clavicle/upperarm/forearm/hand、l/r thigh/calf/foot）。

---

## ★★ 2026-10-18 局内活体 probe2 结果（分叉①坐实 + 驱动路线定性，下次从这接）

注入态 probe2，训练局站定。工具 `逆向存档\_scripts\cmd_bones.py`(真值 dump) + `cmd_bones2.py`(组件映射)。
⚠ 当前机 UID = `u0_a409`，`send_cmd.ps1` 里写死的 `u0_a310` 是旧机、会 chown 错 → 手动 chown u0_a409 推。

**① 分叉①彻底坐实**：
- `unit.anim_data_component`(无下划线) = **AnimDataComponent 活的**；`unit._anim_data_component`(有下划线) = **None**。
- 且 `anim_data_component` **不在 `unit.__dict__` 里(是 @property)**，`_anim_data_component` 在 dict 里但值 None。
  → 我们当年读 `_anim_data_component` 得 None、据此断"Python 读不到骨骼"，是读错了名字。
- 跨单位一致：监管 MyButcherUnit 76 根、求生者 CivilianUnit 69 根，全部 `anim_data_component` 活、`_anim_data_component` None。

**② 真值标尺拿到（注入直接出世界坐标）**：`anim_data_component.get_bone_position(name)` 对 76 根**全部返回真实世界坐标**
（biped head/pelvis/l·r hand/foot…，围绕 `unit.position=(208.86,0.33,398.77)` 聚集，脚 y≈2、头 y≈18）。
骨骼数/名字走 `model.get_bone_count()`(=76) + `model.get_bone_name(i)`；`adc.get_bone_count()`=None(组件不暴露,数在 model)。
`model.get_bone_matrix(i)` 这次取不到平移(返回 None/索引不出)，不影响——`get_bone_position(name)` 已是世界真值。
名字表(监管 butcher.gim，76 根)：`biped / biped pelvis / biped spine / biped spine1/2 / biped neck / biped head /
biped l·r {thigh,calf,foot,toe0,clavicle,upperarm,forearm,hand,finger0/1/2…}` + 一堆 `biped_boneNN / boneNNN`(饰品/武器挂点)。

**③ 组件内部没有通往 POSE 的 Python 指针（驱动路线的硬结论）**：`cmd_bones2.py` dump 了 AnimDataComponent 全部属性——
坐标来自 `_get_bone_position_proxy` 等**原生代理方法**(调 native_unit/core→原生)，**没有任何 Python 可见的 pose/skeleton/anim 原生指针字段**。
组件挂在 CombatCore 组件系统：`.entity/.owner=ButcherUnit`、`.core=CombatCore`、`.native_unit=MyButcherUnit`、`.instance_type=37`。
→ **驱动(裸读,不能调方法)即便顺着 `combat_unit.components` 找到这个组件,也拿不到骨骼**。驱动要骨骼仍**只能走若辰原生链**(下面那节，从 `model` 原生对象 `[M+0x818]`→POSE)。
注入态拿到的原生指针：`id(anim_data_component)=0xB400007CF9ECC380`、`id(model)=0xB400007B590FD8C0`、`adc.native_unit id=0xB400007CF9EAD660`。

**④ 下一步取决于一个产品决定(等用户定)**：
- **注入路线**：直接 `anim_data_component.get_bone_position(name)` —— 刚实测 76 根全出、按名字几乎不失效、零偏移。但生产要接受注入风险(ptrace+.so，撞 native 环境检测；见脚本解包档案 SKILL §0)。
- **驱动路线(零注入)**：若辰原生链(下面)，仍需活体校准 `M=[model+0x20]? → [M+0x818]` 等——而**校准需要裸读内存，注入 probe2 无 ctypes 读不了裸地址、/proc 又被反作弊禁**，所以**只能在 C++ 叠加层里用驱动 ioctl 自己读+自检**(算出的骨骼应紧贴 `PySelf` 已有的 `unit.position`，头比脚高 ~18)，不需要再开 probe。

## ★★★ 2026-10-18 落地：驱动路线骨骼**跑通了**(用户选的零注入路线)

用户选驱动路线。实现 **`IdentityV\jni\src\Android_draw\NativeBones.h`**(抄若辰类型1链，驱动 `getPtr64`/`vm_readv` 读) + draw_Gui「显示骨骼」开关 + 16 条连线投影。
产物 `ayikexro.sh`(md5 `716e39fd…`，已推 `/data/`)；首版 `wtobjefx.sh`。**上机骨架正常绘制 → 若辰链在我们驱动上成立。**

- **M = `unit.model+0x20`**(= `PySelf` 本体集合 `copy_bodies()` 拿到的场景对象)，`[M+0x818]`=ANIM 直接走通，**类型1**(没用到类型0兜底)。
- **名字**用每项自带池指针(`{u32 id, pool_ptr}`，`[[pool+(id>>14)*8]+(id&0x3FFF)*8]+0x10`)，**绕开了版本相关全局 `0xAAF0828`**——成功,名字全解出(biped head/neck/spine/l·r …)。
- **世界坐标** = 姿态第4行 × `[M+0x28]+0x1C0` 世界矩阵；`swap_yz` 拿自身 `objcoor+0xa0` 自动校准一次(`NativeBones::g_swap_yz`，日志 `[骨骼]根骨世界…objcoor…swap=`)。
- 骨骼数:监管 76 / 求生者 69。TARGET 17 根 + 16 边同若辰 `DrawOverlay`。
- **用户反馈迭代**：
  - `ayikexro.sh`：① 自身不画(self 仍读一次做 swap 校准,= 若辰 `ignoreSelfBones`)；② 头部加实心圆。
  - **`hvkdlfis.sh`(md5 `5ed85ab7…`，已推 `/data/`，当前版)**：③ **监管红骨 / 求生者绿骨**(监管本体 = `PySelf::hunter_body`)；④ **离自己 <1m 不画**(同其它逻辑,`self_obj!=0` 时按单位 objcoor 三维距离)；⑤ **头圆沿 脊椎→颈 身体朝向往上顶、脖子接圆底**(引擎颈→头段仅 ~0.8 太短、圆压颈上不好看;头边 slot0 从通用连线里剔除、单独画)；⑥ **名字去掉 `Name.h` 存的外层 `[]`**(绘制处剥括号,不动表——表里 `[信徒]` 等被 strcmp 依赖)；⑦ 去掉骨骼调试日志(已验证成功)。
  - 头是**标准读取**(真实 `biped head` 世界坐标),上顶只是显示侧偏移。`show_draw_Bones` 用户已默认开。
- **启动由用户自己跑**(我 adb 启动被拒，见记忆 [[idv-user-runs-probes]])。诊断在菜单「显示骨骼」下方那行 `NativeBones::log_text()` + 日志关键字 `[骨骼]`。
- **剩余可选**：多单位远距的 pose 冷页读失败(内存压力)未特殊处理；类型0兜底没写(没触发到)；骨架颜色/可见性(被墙挡变红)未做——若辰用 `is_visible_in_this_frame` 只判视锥(见 ruochen 四点七)，真遮挡要几何射线，暂不做。

## 为什么走这条路（先读，避免重蹈覆辙）

- **骨骼在 Python 层读不到**：`unit.model` 是原生 `world.model`，`model.__dict__` **空**（`keys=[]`），骨骼全在原生 C++ 里。
  `unit._anim_data_component`/`_anim_graph_component`/`animator`/`animation_controller` 活体实测**全是 None**。
- **`model.get_bone_matrix()`/`get_bone_prs()` 是方法调用，只有注入能调**，不能进裸读路线（裸读只能读存储字段，不能调函数）。
  （注入下它们能用：`get_bone_count()=53`，标准 biped 骨骼名 `biped head`/`biped spine`/`biped l hand`…，`get_bone_matrix(0)`=世界矩阵、子骨骼=父相对；仅供**探针取真值**。）
- **正解 = 抄若辰**：若辰本身就是外部读取型（ptrace + /proc/pid/mem，和我们驱动同路），它读骨骼靠 `sub_39F0CC`(reader-bone-pose)
  纯原生偏移（进程外没 Python，根本调不了 get_bone_matrix）。**它的代码里就写死了 model→骨骼数组 的偏移链**——直接反汇编抄，
  比在活体内存 BFS 盲搜靠谱得多。**（教训：有现成外部读取型外挂时，先反汇编它抄偏移，别盲搜内存。）**

## 若辰的读内存原语（= 我们驱动里 read 的等价物）

- **`sub_3706B4(ctx, target_addr, out_buf, size)` → bool**：`target_addr &= 0x00FFFFFFFFFFFFFF`（剥高字节 tag），
  在 ctx 的区间表（`[ctx+0x38]`=begin/`[ctx+0x40]`=end，元素步长 0x10，有序，二分查找）里校验地址落在已知区间，再读 size 字节。
- **`sub_37086C(ctx, ?, out)` → bool**：读 8 字节（调 sub_3706B4 size=8），结果再 `& 0x00FFFFFFFFFFFFFF` 剥指针 tag。= **read_ptr**。

## ★ 2026-09-26 静态解完的完整链（`sub_3A6074` 解析器 + `sub_3A40F0` 缓存 + `sub_39F0CC` 消费，逐条汇编）

> **下面这节取代后面 2026-09-25 那版**（那版把 `+0x2B8 → +0x1E8` 写成一条链是错的，`+0x1E8` 属于 `+0x818` 那条；
> "`+0x140`=矩阵/`+0x1C0`=可见"也只对类型 0 成立）。工具：NDK `llvm-objdump` + scratchpad 里自写的 ADRP/ADD 交叉引用
> (`rc_xref.py` / `rc_strs.py`，会清；按本节偏移重建即可)。`M` = 若辰 `subject+0x48` 的原生模型指针。

**若辰先试类型 1，失败才走类型 0**（`sub_3A6074`）。所有 `[..]` = 读 8 字节指针并 `& 0x00FFFFFFFFFFFFFF`。

```
===== 类型 1（主路径）=====
ANIM  = [M + 0x818]                    非 0
        [ANIM + 0x1D8] 必须非 0          (只做校验)
P2    = [ANIM + 0x1E8]
SKEL  = [P2 + 0x30]                    骨架对象
X26   = [M + 0x28]                     ← 猜测 M = 场景对象(model+0x20)，那 X26 就是 objcoor，待活体核对
世界矩阵 = 读 64 字节 @ X26 + 0x1C0      4x4 float，行主序、平移在第 4 行；sub_3A63D8 校验 16 个有限 + 缩放 0.001~1e7
读完再读一次 [M + 0x28]，要求 == X26    (防竞态)

骨骼名/数量：
  NAMES = [SKEL + 0x80] .. [SKEL + 0x88)    16 字节一项，(end-begin) 必须是 16 的倍数且 ≤ 0x2000
  骨骼数 = (end - begin) / 16               1..512（实测模型 53）
  名字项 {u32 id @+0, 池指针 @+8}：
    名字 = C 字符串 @ ( [ [池 + (id>>14)*8] + (id & 0x3FFF)*8 ] + 0x10 )   ≤128 字节
    池读不到时退回 全局池 = 若辰参数1 + 0xAAF0828（参数1 应为 libclient 基址；**这个偏移是若辰那版 so 的，我们的版本要重找**）
  若辰按名字(biped spine 等，表在 0x4D7008)找出最多 17 个关注骨骼的下标，存进缓存描述符 +0x50..+0x90

骨骼姿态（每帧）：
  POSE  = [ANIM + 0x248]
  flag  = u8 [POSE + 0x24]
  ARRAY = [POSE + 0x10 + ((flag & 2) ? 8 : 0)]     双缓冲
  读 (最大关注下标+1) * 64 字节 @ ARRAY           每根骨骼 = 4x4 float 矩阵（64 字节）
  再读一次 u8 [POSE + 0x24]，要求 bit1 没变        (防竞态；变了就整帧重读)
  骨骼 i 的 v = 第 i 个矩阵的第 4 行 (x, y, z, w)   要求 |w| ≥ 0.001 且有限
  世界坐标 = v × 世界矩阵（行向量右乘，x = v·列0 …）
  若 swap_yz：交换结果的 y/z。swap_yz 是若辰按单位自己校准的标志(某结构 +0x18 字节)，不是游戏字段 —— 活体拿 unit.position 对照即可定
  每个分量有限且 ≤ 1e7 才收

===== 类型 0（兜底）=====
B     = [M + 0x2B8]                    骨骼数 = u32 [B + 8]，1..512
PTRS  = [B + 0x10]                     8 字节指针数组，每根骨骼一个对象 p
X26   = [M + 0x80]
可见   = u8 [X26 + 0x1C0] 必须非 0
世界矩阵 = 64 字节 @ X26 + 0x140
SKEL  = [ [ [M+0x818] + 0x1E8 ] + 8 ] + 0x30 ，名字表同上
骨骼 i：p = PTRS[i]，读 24 字节 @ p+0x64，v = ( f@p+0x6C , f@p+0x78 , 0 , 1 )   ← 第三分量写死 0，看着怪，**没验**
        世界坐标 = v × 世界矩阵，同上
```

**若辰的缓存描述符**（`sub_3A40F0` 返回，`sub_39F0CC` 里的 `x28`）= 解析器结果往后挪 8：
`+0` 类型、`+0x08` M、`+0x10` ANIM(类型1)/B(类型0)、`+0x18` 类型0 的 PTRS、`+0x20` 期望 X26、`+0x30` SKEL、
`+0x38/+0x40` 名字数组起止、`+0x48` 骨骼数、`+0x50..+0x90` 关注骨骼下标。缓存有效性：`[M+0x818 或 0x2B8]` 与 `+0x10` 相同、
`[[..]+0x1E8]+0x30` 与 `+0x30` 相同。

**静态能解的已经全解了，剩下只能活体定**（见下面待办，已按本节改写）。

---

## （旧）2026-09-25 首版偏移链 —— 已被上一节取代，留档

```
MODEL_NATIVE = [subject+0x48]
   // 若辰 subject 里 +0x48 = 模型原生指针。对应我们：unit.model 的 native 对象。
   // 活体：PyObject(model)+0x20/+0x28/+0x30 都指向同一个原生 SCENE 对象；待核对 MODEL_NATIVE 是否 = 这个 SCENE。

--- 世界矩阵 + 可见标志（每 subject，sub_39F0CC 主体）---
type    = 字节 descriptor[0]                       // 1 或其它，选偏移
X26     = read_ptr( MODEL_NATIVE + (type==1 ? 0x28 : 0x80) )
[X26+0x140] → 4x4 世界矩阵(64 字节)   // 读 0x40 字节，sub_3A63D8 做有限性(NaN/inf)校验
[X26+0x1C0] → 可见标志字节
// 读完对 MODEL_NATIVE+{0x28|0x80} 再读一次做防竞态校验（要求两次一致）

--- 骨骼姿态数组（sub_39F0CC，ANIM = descriptor[0x10]）---
POSE   = read_ptr( ANIM + 0x248 )
flag   = read_byte( POSE + 0x24 )
ARRAY  = read_ptr( POSE + ((flag & 2) ? 8 : 0) + 0x10 )   // 双缓冲：按 flag 选 +0x10 或 +0x18
block  = read( ARRAY, count*stride )                       // 一次性读全部骨骼矩阵到本地缓冲

--- 骨架解析 sub_3A40F0（把 MODEL_NATIVE 解析成 ANIM，混了若辰自己的缓存层）---
P1 = read_ptr( MODEL_NATIVE + 0x2B8 )
P2 = read_ptr( P1 + 0x1E8 )
     read_ptr( P2 + 0x30 )            // 校验值
... → ANIM（最终存进 descriptor[0x10]，见待办①）
// 骨骼按【名字】定位（函数里引用 "biped spine" 等），抗热更、抗关节重排

--- 若辰的骨架描述符（它本地构建的结构，不是目标内存）---
descriptor[0x00] = type 字节
descriptor[0x10] = ANIM 指针（目标进程）
descriptor[0x20] = 期望的 X26（校验用）
descriptor[0x48] = 骨骼数量（bounds < 0x201）
descriptor[0x50/0x70/0x90] = 关注的骨骼索引列表（SMAX 取最大索引）
```

## 待办（2026-09-26 更新：①②③ 静态已解，见最上面那节；剩下的只能活体核对）

> ~~① `P2 → ANIM` 最后 1~2 跳~~ —— **已解**：ANIM 就是 `[M+0x818]` 本身，`+0x1E8→+0x30` 是骨架/名字那条支线。
> ~~② `ARRAY` 步长/格式~~ —— **已解**：64 字节 4x4，行主序。
> ~~③ 位置提取~~ —— **已解**：第 4 行 × 世界矩阵（`X26+0x1C0`）。
>
> **活体还要核对的（一局训练局站定即可）**：
> - **a. `M` 是不是场景对象**（`PyObject(model)+0x20`）。若是，`[M+0x28]` = objcoor，已知 objcoor+0xa0 是脚底坐标，可交叉验证世界矩阵平移。
> - **b. 这一版走哪种类型**：`[M+0x818]` 非 0 且 `[[M+0x818]+0x1D8]` 非 0 → 类型 1。
> - **c. 下标对应**：名字表第 i 项 ↔ ARRAY 第 i 个矩阵，与 `get_bone_name(i)` / `get_bone_matrix(i)` 真值比对（尤其第 4 行是模型空间还是父相对）。
> - **d. swap_yz**：算出的世界坐标与 `unit.position` 比，看要不要交换 y/z。
> - **e. 名字池**：先试每项自带的池指针；全局池偏移 `0xAAF0828` 是若辰那版 so 的，要在我们这版上重找（或者干脆不用：名字只在第一次建"名字→下标"时用）。
> - 类型 0 的 `(f@+0x6C, f@+0x78, 0, 1)` 只在这一版走类型 0 时才需要验。
>
> 以下是 2026-09-25 首版写的补全方法，思路仍适用：
>
> **补全方法（活体实跳，不用再撕汇编）**：
> 1. 注入探针取真值：`id(u.model)` + `u.model.get_bone_matrix(0/17)` + `u.world_position`（囚徒站定时）。
> 2. devread 从 MODEL_NATIVE 按 `+0x2B8 → +0x1E8 → …` 实跳，每跳 dump，找到那个 `+0x248 → POSE → +0x10 → ARRAY` 的结构（POSE 特征：+0x248 指来、+0x24 有 flag 字节）。
> 3. 到 ARRAY 后按不同步长(48/64)切分，和 get_bone_matrix 真值逐根比对 → 定步长、格式、位置字段。
> 4. 反推 MODEL_NATIVE：先确认 = `unit.model` 的哪个 native（活体 PyObject(model)+0x20=SCENE，试 `[SCENE+0x2B8]` 能否走通 +0x1E8→+0x30）。
> 5. 全部落地成 C++ 常量偏移（零注入），按名字取骨骼（`get_bone_name` 的 53 个名字表做索引映射）。

## 探针工具链（复用，别重新摸索）

- **注入命令通道（probe2，仅探针）**：写 Python 到 `/sdcard/Android/data/com.netease.dwrg/files/idv_cmd.py`
  （`chown u0_a310:ext_data_rw`、`chmod 660`），探针每 2 秒 exec、删除、结果写 `idv_cmd_out.txt`。
  命令里现成：`GK`/`mgr`/`me`/`units_of(t)`/`idict()`/`attr_names()`/`cname()`/`S(lambda:...)`/`P(...)`/`R(v,n)`/`json`/`time`。
  推送三连见 `injection.md`（先 push 到 /sdcard 再 su cp+chown，rm 单独一条）。
- **devread（PC 侧裸读，和驱动同路）**：`C:\Users\31297\Desktop\逆向\_通用工具\procmem\devread.py`，`Mem(pid)`→`.q/.d/.f`，
  **tag 掩码 `0x00FFFFFFFFFFFFFF`**，**游戏必须前台**（`oom_score_adj=0`），换出页会跳过（见 android-re-toolkit 第五节）。
- 本轮临时脚本在 scratchpad（会清）：`bexplore*.py`(devread)、`gt.py`/`vis*.py`/`bnat1.py`/`bstore.py`/`mid.py`(探针)；
  若辰汇编 `a_3A40F0.txt`/`b_39F0CC.txt` 等；关键结论都在本文件，不依赖那些临时文件。

## 活体已确认的旁证（2026-09-25，pid 25114 时）

- `id(u.model)` 例：`0xb400007c8a8001b0`；`PyObject(model)`：+0x08=ob_type，+0x18=libclient .text 指针(原生方法)，
  **+0x20/+0x28/+0x30 = 同一原生 SCENE 对象**；`SCENE+0x28`=objcoor（世界矩阵在 objcoor+0x60：平移=脚底世界坐标），`SCENE+0x30`=回指 PyObject。
- `model.get_bone_count()=53`；`get_bone_matrix(0)` 平移=世界坐标、`get_bone_matrix(17=head)` 平移=父相对（局部）。
- 遮挡：`is_visible_in_this_frame()` = 只判视锥，不判墙挡（见 `ruochen-teardown.md` 四点七的对照实验）。
