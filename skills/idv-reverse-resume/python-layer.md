# Python 层：玩法状态在哪、怎么读（2026-09-21 建立）

游戏的**玩法状态全部在内嵌 CPython 的堆上**，不在场景对象里。密码机破译进度、大门开门进度、
椅子状态、本机玩家身份，都得走这一层。这份文件是这一层的完整参考。

SKILL.md 里只留了操作要点，遇到"进度读不出/配不上/热更后失效"翻这里。

---

## 一、为什么必须走 Python 层（这是个花了一整轮才确认的负面结论）

数组里那 290 个对象是**渲染节点**，类名是 `.gim` 模型路径，身上**不带任何玩法状态**。

实测过程（别再重做一遍）：

- 拿 7 台密码机做四档差分（0%×3 / 25% / 80% / 100%×2），要求"同档内取值一致 + 档间严格单调"
- 扫了 f32 / f64 / u32 / u16 / u8 五种宽度
- 范围：对象本体 0x400 字节，以及沿对象内指针下钻**两层**（20 个一级节点组、405 个二级节点组）
- **结果：0 命中**

顺带也否掉了"破译完成标志位"：本体里没有任何字段满足"两台 100% 同值、其余全是另一个值"。

决定性证据：`fix_process`、`hack_process`、`get_generator_units` 这几个名字在 175MB 的
`libclient.so` 里**一个都搜不到**。说明它们不是 C++ 注册给 Python 的属性（那样会有静态
`PyGetSetDef`/`PyMethodDef` 字符串），而是游戏 Python 脚本里定义的纯 Python 属性。

**推论：任何"玩法语义"的东西，先假设它在 Python 层，别再去场景对象里扫。**

---

## 二、完整链路（端到端验证过，跨对局重验通过）

```
libbase + 0xA7029E8              -> sys.modules              (dict, ma_used≈4000)
  按名字找 "game_kernel"          -> module                   (本局 sys.modules entry#328)
    module + 0x10                -> md_dict                  (125 个属性，进程内稳定)
      按名字找 "unit_mgr"         -> UnitManager 实例          (entry#31，每局重新分配)
        实例 - 0x18              -> managed dict
          按名字找 "units_by_type"-> dict(int -> list)         (entry#8)
            键 int 3             -> list                      (3 = 密码机的 unit_type)
              list+0x10 = 元素数   list+0x18 = 元素数组
                每个 GeneratorUnit 实例 - 0x18 -> dict (323 条)
                  entry#242 "fix_process"  -> 0~100 的进度
                  entry#69  "model"        -> +0x20 = 场景对象指针
                  entry#59  "position"     -> +0x10/+0x14/+0x18 = X/高度/Y
                  entry#14  "uid"          -> 本局唯一 id（密码机是连号 1000007~1000013）
                  entry#62  "unit_mgr"     -> 回指 UnitManager
```

**静态根是怎么来的**：CPython 把主解释器内嵌在 `.so` 的静态数据里，所以
`interp->imports.modules` 本身就落在固定模块偏移上。相邻的几个字段可以互相印证：

```
libbase + 0xA7029E8  -> dict ma_used=4001  键: builtins, _frozen_importlib, _imp, ...  ← sys.modules
libbase + 0xA7029F8  -> dict ma_used=96    键: __name__ ... addaudithook               ← sys 模块字典
libbase + 0xA702A00  -> dict ma_used=151   键: __name__ ... __build_class__            ← builtins
libbase + 0xA702A08  -> module 对象
```

**想做成自愈**（强烈建议，热更后 `0xA7029E8` 大概率会动）：在 `.so` 的 rw 段 / bss 里扫
指向 dict 的指针，取那个"前几个键依次是 `builtins`、`_frozen_importlib`、`_imp`"的。
这个特征几乎不可能变，比写死偏移抗热更得多。`_scripts\py_staticscan.py` 就是干这个的。

---

## 三、类型对象与 CPython 3.11 布局速查

**解释器是 CPython 3.11**（不是 2.7，旧记录里关于注入的假设要按这个重新对）。判据：

- dict 用 `PyDictUnicodeEntry{key, value}` **16 字节、不存 hash**（3.11 引入）
- `PyLong` 仍是 **ob_size 语义**（int 0 → ob_size=0；int 100 → ob_size=1, digit=100）。
  3.12 会是 `lv_tag`（int 0 标签是 1、int 100 是 8），实测不是。
- managed-dict 实例的 dict 指针在**对象前 0x18**

| 类型对象 | 模块相对偏移 |
|---|---|
| `PyType_Type` | `+0xA034F80` |
| `str` | `+0xA038140` |
| `PyDict_Type` | `+0xA023BF0` |
| `PyLong_Type` | **`+0xA026498`** |
| `PyFloat_Type` | `+0xA0336F0` |
| 小整数缓存基址(-5) | `+0xA6F42E0`，步长 32，index = 值+5 |

> `PyLong_Type` 我一开始算成了 `0xA626498`（多写了 0x600000），导致所有 int 值被判成
> "类型不对"。`0x7A9A626498 - 0x7A90600000 = 0xA026498`，算的时候仔细点。

结构偏移：

```
dict:      +0x10 ma_used   +0x20 ma_keys   +0x28 ma_values(非0=split table，值不在entries里)
keys:      +0x08 log2size  +0x09 log2_index_bytes  +0x0A kind  +0x18 nentries
           entries 起始 = keys + 32 + (1 << log2_index_bytes)
           entry 步长 = 16 (kind!=0, 全unicode键 {key,value}) / 24 (kind==0, {hash,key,value})
str:       +0x10 长度  +0x18 hash  +0x20 state(interned的紧凑ASCII是0xE5)  +0x30 数据
float:     +0x10 double
long:      +0x10 ob_size  +0x18 第一个 digit
list:      +0x10 ob_size  +0x18 ob_item
module:    +0x10 md_dict
实例:      -0x18 = managed dict 指针
```

**所有堆指针高位带 `0xB4` 标记**，比较和解引用前必须 `& 0x00FFFFFFFFFFFFFF`。
这是 **Android 的堆指针标记（TBI，固定 tag 0xB4）**，不是 NeoX 自己的方案 —— 旧记录写错了。
所以它对**所有 malloc 指针**都成立，不止引擎对象。

---

## 四、三个必须守住的坑

### 1. entries 起始必须**逐实例**算

`entries = keys + 32 + (1 << log2_index_bytes)`，而 `log2_index_bytes` 取决于那个 dict 自己的大小。
**同一个类的不同实例，dict 形状可以不一样。** 把一台机器上算出的偏移套到另一台上，
会读到完全无关的属性 —— 我在大门上就是这么读出 `10737.42`、`1789918793` 这种垃圾的。

### 2. 值的类型在 int 和 float 之间来回变

`fix_process` 为 0 和 100 时通常是**缓存的小整数对象**（指针恒等于 `libbase+0xA6F42E0+(值+5)*32`），
中间值是 float。而且同一台机器在不同对局里可能一个是 int 0、一个是 float 0.0。

**两种都要认**；"认不出"必须当成读取失败，**绝不能当成 0**。

### 3. 读取竞态：属性每帧重新赋值，旧 float 进 freelist 被复用

这是最隐蔽的一条。实测大门的 `hack_process` **每次读之间指针都变**（10/10），
而密码机空闲时指针纹丝不动。属性每被赋值一次就换一个新的 `PyFloatObject`，
旧的进 freelist 立刻被别人复用 —— 复用后 `ob_type` 仍然是 `PyFloat_Type`，
所以光看类型分辨不出来。

**正确的读法**：

```
读指针 vp -> 读对象(32字节) -> **再读一次指针确认还是 vp**
  且 refcount > 0
  且 ob_type ∈ {PyFloat_Type, PyLong_Type}
  且 数值落在 0~100
任何一条不过就重试；重试几次还不行，这一帧判为"读取失败"而不是"进度 0"
```

内核驱动读一次是微秒级，正常一次就过。**PC 侧用 adb 读（一次往返 0.3 秒 ≈ 18 帧）
则几乎必然读到垃圾** —— 所以 PC 脚本读"活跃变化的属性"时数据不可信，
只有空闲属性（指针稳定）才读得准。诊断时先跑一个空闲对照组区分是偏移错还是竞态。

---

## 五、unit_type 总表（`units_by_type` 的键）

一局军工厂实测：

| 键 | 类 | 本局数量 | 关键属性 |
|---|---|---|---|
| 1 | `ButcherUnit` | 1 | 监管者 |
| 2 | `CivilianUnit` | 4 | 求生者 |
| **3** | **`GeneratorUnit`** | **7** | **`fix_process`**, `fix_speed`, `fix_freeze_process`, `fixed_success`, `be_fixed_flag`, `fix_mates` |
| 4 | `HookUnit` | 15 | `state`（狂欢之椅） |
| 5 | `BoxUnit` | 4 | `state` |
| **6** | 大门（类名那页换出了没读到） | 2 | **`hack_process`**, `hack_speed`, `can_open`, `has_open`, `is_opening` |
| 7 | `WoodUnit` | 11 | 木板 |
| 10 | `CaveUnit` | 1 | 地窖 |
| 12 | `SwitchUnit` | 2 | 电闸 |
| 19 | `PosterUnit` | 1 | |
| 214 | `SoftWallUnit` | 64 | |
| 252 | `MailDogUnit` | 1 | |

**这张表是权威的本局真实数量**，比场景侧 `+0x240`/`+0x1a0` 那套启发式判据可靠。
椅子真实 15 个、箱子 4 个、木板 11 个、地窖 1 个、大门 2 个 —— SKILL.md 里那几条
"多画"的待办可以直接用这个解决。

### 2026-09-22 注入实测（另一张图，全部键的类名都读出来了）

跨进程读经常读不出类名（那一页换出去了）；**注入之后是进程内 `type(u).__name__`，一个不缺**：

| 键 | 类 | 本局数量 | 说明 |
|---|---|---|---|
| 1 | **`MyButcherUnit`** | 1 | ← **本机操控时是这个类，不是 `ButcherUnit`** |
| 2 | `CivilianUnit` | 4 | |
| 3 | `GeneratorUnit` | 7 | 密码机 |
| 4 | `HookUnit` | 15 | 椅子 |
| 5 | `BoxUnit` | 8 | 箱子（上表是 4，随地图变）|
| 6 | **`DoorUnit`** | 2 | ← 上表"类名没读到"的就是它 |
| 7 | `WoodUnit` | 11 | 木板 |
| 8 | **`PanelUnit`** | 32 | 新 |
| 9 | **`CupboardUnit`** | 17 | 柜子，新 |
| 10 | `CaveUnit` | 1 | 地窖 |
| 11 | **`CrowUnit`** | 21 | 乌鸦，新 |
| 12 | `SwitchUnit` | 2 | 电闸 |
| 214 | `SoftWallUnit` | 64 | |
| 260 | **`ElectricBoxUnit`** | 9 | 电箱，新 |
| 401 | **`ImperUmbrellaUnit`** | 1 | 无常的伞（只有该监管在场时出现）|
| 1911 | `CommonSceneUnit` | 1 | |

⚠️ **键随对局/角色变**（`401` 只在无常局出现，`19`/`252` 这局没有）。
**别把键表写死当白名单**，每局重新枚举。

**2026-09-22 梦之女巫局又刷出这些**（同一天不同局，数量也会变，如 `HookUnit` 15→16）：

| 键 | 类 | 数量 | 说明 |
|---|---|---|---|
| 30 | `MagicFieldOutlineUnit` | 1 | |
| **236** | **`MyYidhraPuppetUnit`** | 5 | **梦之信徒**（梦之女巫的可操控从属）|
| 10070 | `WormholeUnit` | 12 | |
| 10071 | `WormholePreviewUnit` | 1 | |
| 10072 | `WormholeBallUnit` | 1 | |

**2026-09-22 晚又见到的**：

| 键 | 类 | 说明 |
|---|---|---|
| 1 | `MyButcherPatrolPuppetUnit` | **巡视者，混在监管列表里**。挑"真监管"要按类名(tp_name)跳过含 `Puppet` 的 |
| 2 | `SlideManCloneUnit` | **幻灯师分身，混在求生者列表里**（继承 `CivilianUnit`，`unit_type=2`）。区分字段见 SKILL.md「角色本体」|
| **17** | `CloneUnit` | **魔术师分身**，独立键，`is_clone=True`、`unit_type=17`，数量会持续涨（12→19/10 秒）|
| 222 | `BirdUnit` | |
| 大厅/准备 | `53 BookshelfUnit` / `59 ChairUnit` / `74 BottleUnit` / `100 MyCityUnit` / `1009 Halloween2022Unit` | 没有 1/2，见 SKILL.md「准备阶段」|

**可操控的从属单位会混进列表**：机械玩偶 `MyCivilianPuppetUnit`、幻灯师分身 `SlideManCloneUnit`
混在 `[2]`（求生者）里，巡视者混在 `[1]` 里，梦之信徒在独立键 `[236]`、魔术师分身在 `[17]`。
数"本局真实求生者数量"或挑"真监管"时要注意。

**每个玩家单位上类型为 `world.model` 的属性**（注入实测）：`model`（本体）、`another_model`（另一形态，
所有玩家类都有，多数为 None）、`_fragrance_image`（每个求生者一份同名隐藏副本）、`balloon_model`、
`umbrella_model`（无常）；幻灯师分身另有 `clone_dissolve_model` / `slide_man_shell_model`。
`world.model` 在 Python 侧有 `.visible` / `.filename`，**`+0x20` 是场景对象指针**（进程内没有 `ctypes`，
要从 PC 侧读 `id(obj)+0x20`）。
自身/操控识别见 `SKILL.md` 的「自身（本地玩家）识别」一节。

⚠️ **别从"这局没有某个键"推出"这类东西不在 `units_by_type` 里"。**
我犯过这个错：看到这局没有道具相关的键，就写成"道具只挂在单位身上"——
**是错的**。道具**既可以被携带、也可以掉在地上**，掉地上时很可能自成一个 unit。
那局只是恰好没有掉落的道具而已。**要验证就盯着键表随时间变化**（掉一个道具看看多出什么键），
不要拿单帧快照下结论。

（`_iter_unit_hold_items(unit)` 只是作者脚本读**携带中**道具的那条路径，不是全部。）

---

## 六、跨对局验证过的 entry 序号

| 位置 | 名字 | 序号 |
|---|---|---|
| sys.modules | `game_kernel` | 328 |
| game_kernel md_dict | `unit_mgr` | 31 |
| game_kernel md_dict | `g_unit` | 27（值是本机的**主角色**，**不跟随**操控切换；当前操控角色要读 `g_cam_ctrl.unit`，见 SKILL.md「自身识别」） |
| UnitManager dict | `units_by_type` | 8 |
| GeneratorUnit dict (323条) | `uid` / `position` / `unit_mgr` / `model` / `fix_process` | 14 / 59 / 62 / 69 / 242 |
| 大门 dict (238条) | `uid` / `position` / `hack_process` | 7 / 52 / 220 |

**换了一局重验，全部命中**（所有堆地址都变了，序号没变）。

但序号依赖类属性的插入顺序，热更改一行代码就可能整体位移，所以**代码里一律按名字查找**，
查到后缓存序号，下次先试缓存并用名字校验，对不上自动回退全扫。
这样热更后不会给出错误结果，最多慢一次。

---

## 七、配对：用 `model` 指针身份，不要用坐标

把 Python 侧的 `GeneratorUnit` 配到场景侧的 `obj`：

```
GeneratorUnit.model (entry#69) -> +0x20 = 场景对象指针（就是数组里那个 obj）
```

`+0x20` / `+0x28` / `+0x30` 三处都指向同一个场景对象，任取其一。

**坐标配对不可靠**：实测一局 7 台里有 **4 台的 `position` 读不出来**
（`uid 1000006/1000009/1000011/1000012`），这几台靠坐标永远配不上 ——
表现就是"明明破译完了叠加层还画着机器"。`visual_position` / `logic_position` 也是 0，救不了。

`model` 指针实测 7 台里 6 台立刻命中，命中的场景对象 `+0x240` 全是 2，和场景侧判据完全一致；
剩下 1 台是 `model` 短暂为空的瞬态。**坐标只作为 model 为空时的兜底。**

顺带：同一批场景对象的地址是按 `0x9B0` 连号排列的（`0x7AC75A62E0`、`...6C90`、`...7640` …），
认地址的时候能用上。

---

## 八、其它已确认的玩法语义

- **五台破译完之后，剩下的机器 `fix_process` 会被强制置 100**（实测 7 台全是 100.0）。
  所以"已破译数"在终局阶段会是 7 而不是 5，做逻辑时注意。
- **大门 `hack_process` 每帧都在被重新赋值**，即使没人开门。读它必须按第四节的防竞态法。
- `fixed_success` / `be_fixed_flag` 是 True/False 单例（两个地址相差 0x20）。
  `fixed_success` 的语义不是"破译完成"——一台 81.69% 的机器它也是 True，
  推测是"上一次校准成功"。别拿它当完成标志。

---

## 九、工具链（都在 `逆向存档\_scripts\`）

| 脚本 | 用途 |
|---|---|
| `pyw.py` | **公共库**：CPython 活体行走，批量预取 + 容忍换出页的 dict/str 读取 |
| `py_chain.py` | **主力**。从静态根走到某类单位的某个属性。`--type 6 --attr hack_process`、`--attrs` 列全部属性名、`--grep` 看一组属性、`--scan` 强制全扫 |
| `py_attrdbg.py` | 权威诊断：每轮按名字全扫取值 + 打印 dict 头（看 `ma_values` 是否 split table）+ 防竞态校验读 |
| `py_watch.py` | 对同一批槽位连续采样，分辨"真实变化"和"读到垃圾" |
| `py_senderdiag.py` | 场景侧 与 Python 侧 的密码机对照，回答"为什么这台还在画" |
| `py_findlink.py` / `py_verifylink.py` | 找/验 GeneratorUnit -> 场景对象 的身份链 |
| `py_findattr.py` | 按属性名反查：找 interned 字符串 -> 找持有它的 dict -> 认出宿主 |
| `py_staticscan.py` | 扫静态段里指向 Python 对象的指针，用来找 sys.modules / 做自愈 |
| `py_owner.py` / `py_climb.py` / `py_findlist.py` | 沿引用往上爬，认出 list/tuple/dict/实例 的宿主 |
| `py_unittypes.py` | 列 `units_by_type` 全表 |
| `heap_dump.py` / `heap_find.py` | 把常驻堆拉到 PC 离线搜（字符串/指针/浮点）。`--only scudo,anon,.bss,libclient.so --tag xxx` |
| `chain_cache.json` | entry 序号缓存，脚本自己维护 |

### 性能：devread 每次 `fetch()` = 三次 adb 往返（~0.4 秒）

这是 PC 侧脚本慢的唯一原因。**必须先收集地址再一次性 fetch**，逐地址读会退化成成百上千次往返。
早期版本挨个试模块的字典去找 `unit_mgr`，几百次 fetch = 好几分钟；
改成按缓存序号直取 + 名字校验后，同样的活 **26 秒**。

反过来，整块 `m.get()` 会因为中间有换出页而**整体返回 None**，所以遍历要按条目粒度读、坏的跳过。

### 堆快照

`heap_dump.py` 把常驻页批量 dd 成一个大文件拉到 PC（scudo 约 400MB / 2.5 分钟，
无名 anon 约 34MB / 10 秒，bss+so 约 42MB / 8 秒）。拉一次之后所有搜索都离线做，不用反复碰活体内存。
**CPython 的堆在 scudo 里，不在无名 anon 段**（NeoX 内嵌的 CPython 走系统分配器，不是独立 pymalloc arena）。

---

## 十、已落地到叠加层的部分

`jni\src\Android_draw\PyProgress.h`（header-only，`draw_Gui.cpp` include 它）：

- 自带后台线程，**100ms 一轮**，跟实体大循环那个 `sleep(3)` 解耦
- 双缓冲发布（写非活跃缓冲 -> 写计数 -> 翻转），绘制线程永远读到完整一份
- 全程按名字查找 + 序号缓存 + 名字校验 + 失败回退全扫
- 连续失败 8 轮就把缓存序号全部作废重找
- 读值带完整防竞态校验（见第四节）
- 对外：`查询(obj, x, y, &进度)`（先指针身份后坐标兜底）、`已破译数()`、`最后一台(&进度)`、`状态文本()`

绘制侧（`draw_Gui.cpp` 的 sender 分支）：`[50.0%] 12.3 米`，头部用进度色
（<20 绿 / 20–60 黄 / >60 红），距离沿用 61–63 米变绿；上方一条 60×5 进度条（进度为 0 不画）；
破译完的机器整个不画。已破译 2 台且还有 ≥3 台有进度时，在预知监管下面画"最后一台"进度条。
全部跟着「显示密码机」这一个开关。

链路取不到时头部显示 `[密码机]`（而不是 `[0.0%]`），**这是区分"进度是0"和"读不到"的信号**。

同一条链路上后来又落地了两个 header（都在 `jni\src\Android_draw\`，被 `draw_Gui.cpp` include）：

- **`PyGenius.h`**（namespace `天赋`，500ms 一轮）：天赋 `genius_id_lv_lst`（按 uid 锁存）、
  监管辅助特质 `support_skill_id` + 剩余冷却（`skill_mgr.skill_dict` 的 `_cd_delta`）、
  绝处逢生消耗 `ability_used[102]`。细节见 `idv-replay-genius` 待办 #6。
- **`PySelf.h`**（namespace `本机`，100ms 一轮）：自身锚点 `g_cam_ctrl.unit.model+0x20`、
  废弃模型黑名单 `another_model+0x20`。见 SKILL.md「自身识别」和「形态切换」两节。

---

## 十一、怎么重新找（热更把偏移打废时照这个复盘）

1. `heap_dump.py --only scudo` 拉堆
2. `heap_find.py str fix_process` 找字符串。**interned 字符串对象**的判据：
   数据前 0x30 字节是合法 `PyASCIIObject` 头（length 对得上、state 低 6 位 == 0x25）。
   命中多处时，落在 marshal 过的 code object 数据块里的那些不是活对象，看头就能排除。
3. `py_findattr.py fix_process` 反查持有它的 dict，值是 str 的基本都是 `co_names`，跳过
4. `py_owner.py <dict地址> --climb N` 一层层往上爬到 UnitManager
5. `py_staticscan.py` 找静态段里的 `sys.modules`（按"前几个键是 builtins/_frozen_importlib"认）
6. `py_chain.py --scan` 重新确定所有 entry 序号，写回 `chain_cache.json`
