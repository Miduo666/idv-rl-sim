# 第五人格 设备标识 / 指纹 / 跨安装关联（2026-10-17 实测建立）

**什么时候读这个**：用户问"换账号/删游戏/删文件能不能让本机变干净""服务器凭什么认得这台机""设备 ID 存在哪、改哪一个有用""卸载重装还会不会被认出来"——这类**设备追踪 / 脏环境 / 重置可行性**问题，而不是玩法数据（玩法看 `python-layer.md` / `ruochen-teardown.md`）。

本文件是**结论 + 实证值 + 复现方法**三合一，下次别再从头扫一遍。第 0-8 节数据来自 2026-10-17 旧机（Redmi socrates, `22127RK46C`, HyperOS/Android 15, Magisk root, 游戏 UID `u0_a409`）。

> **★ 2026-10-18 新机大更新看第 9 节**（warsaw / Android 16 / Shamiko 白名单，游戏从旧机整盘迁移）。第 9 节**坐实了两层身份模型、device_id=SSAID、IS_ROOT 真值读法，并更正了第 5 节的过度猜测和第 0/2.4 节 `IS_ROOT=true` 的陈旧性**。旧机结论读旧节、现用结论优先看第 9 节。

---

## 0. 一句话结论（最重要，先看这个）

> **游戏自己"写进手机"的东西，没有一个能跨卸载存活**——全在卸载即抹的沙箱里，公共区实测干净（只有用户自己的截图）。
> **真正让"重装还被认出来"的，不是游戏留下的文件，而是游戏"读"的几个系统级 ID**（Android ID / OAID / GAID / DRM / 硬件指纹）——它们不属于游戏、删游戏删不掉，重装后被原样读回。
> **所以单删本地文件、单换账号都无效**，要真·干净只有：**换物理设备 + 换账号 + 不 root**（root 状态 `IS_ROOT=true` 本身也在上报）。

这条和 skill 顶部的反作弊是同一主题的两个面：顶部讲"读内存会被 /proc 探针逮"，这里讲"设备身份怎么被持久追踪"。

---

## 1. Android 卸载规则（决定什么算"持久"）

| 位置 | 卸载 `com.netease.dwrg` 时 | 游戏写的东西在不在这 |
|---|---|---|
| `/data/data/com.netease.dwrg/`（内部私有） | **系统自动抹** | shared_prefs（vkey/伪IMEI/设备画像）、files | 
| `/sdcard/Android/data/com.netease.dwrg/`（外部私有沙箱） | **系统自动抹** | `DeviceId.txt`、各 SDK 缓存 |
| `/sdcard/Android/obb/com.netease.dwrg/`（obb 沙箱） | **系统自动抹** | 资源包 |
| `/storage/emulated/0/` 下**非 `Android/`** 的公共区 | **不动** | **实测：游戏什么都没往这写** |
| 系统级存储（`/data/system/...`、vendor OAID、DRM） | **不动** | 游戏只**读**不写（见第 4 节） |

**"卸载后还在、重装会被读"⇔ 落在后两行。实测游戏在公共区零落点，所以答案全在系统级那一行。**

---

## 2. 游戏写的设备标识文件全表（实证值，全在沙箱 → 卸载即丢）

### 2.1 `shared_prefs/`（内部私有，卸载抹）

| 文件 | 实测内容 | 性质 |
|---|---|---|
| `UNISDK DeviceUtils.xml` | `first_deviceId_cached = <另一ID前缀>-3211-471a-8575-a7f513b10b89-2a13` | unisdk 自造的 UUID 式设备 ID（随机生成持久化，**非** Android ID） |
| `unisdk_devices_infos_file.xml` | 硬件/传感器快照，见 2.3 | 一次性写死缓存 |
| `virtualImeiAndImsi.xml` | `virtual_imei=<虚拟IMEI>` / `virtual_imsi=<虚拟IMSI>` | Android 10+ 拿不到真 IMEI，SDK 自造一个持久化 |
| `vkeyid_profiles_v4.xml` | `key_deviceid_v4 = 一长串加密 hex` | 网易 vkey 设备指纹，加密存，最硬 |
| `device_feature_prefs_name.xml` | `device_feature_prefs_key = 3CE2E698…`（hex） | 加密的设备特征 blob |
| `snssdk_openudid.xml` / `device_register_oaid_refine.xml` | **本次不存在**（可能在 `files/keva`、`files/zeus_p` 里） | 字节 OAID/openudid，待查 |
| `GaidUtils.xml` | — | Google 广告 ID 缓存 |
| `zeus_gbsdk.plugin.*` | — | 字节游戏安全 SDK（Zeus/GBSDK） |

### 2.2 `files/`（内部私有，卸载抹）

| 文件 | 内容 | 性质 |
|---|---|---|
| `ntunisdk_so_uuids`（5258B） | 73 个 native so 的 md5（`libclient`、`libsec-lib`…） | **so 完整性基线，每次启动重算**（见第 6 节，和注入强相关） |
| `unisdk_gm_<账号uid_A>` / `unisdk_gm_<账号uid_B>` | gmsdk 会话（JWT / `gmsdk.gameyw.netease.com`） | **按账号分文件**：`<账号uid_A>`=用户 `unique_id`、`<账号uid_B>`=acsdk role_id |

### 2.3 `/sdcard/Android/data/com.netease.dwrg/files/DeviceId.txt`（外部沙箱，卸载抹）

```
device_id:<DeviceId>
```

**★ 重大更正（推翻之前记录）**：
- 以前说这个文件"卸载重装都不清、真·设备级持久"——**错的**。它在**外部私有沙箱**里，卸载照样被系统抹。
- 它的值 `<DeviceId>` **≠** 系统给游戏的真 Android ID（`<SSAID_旧机>…`，见第 4 节）。所以它是**网易另算的一个内部 ID**，存沙箱、重装即丢重建，**不是跨安装的根**。

### 2.4 `unisdk_devices_infos_file.xml` 是"一次性写死"缓存（2026-10-17 删除重建实验）

- 文件 3745B，md5 `a31ce5420f82438b2a0a9517df7d89a5`，mtime 停在 **2026-01-04**（首次安装那次写的，之后再没动过）。
- 内容是**纯硬件/传感器快照**，无任何秘密 ID：`FINGERPRINT=Redmi/socrates/socrates:15/...`、`MODEL=22127RK46C`、`GL_RENDERER=Adreno (TM) 740`、`CPU_NAME=SM8550`、`BOARD=kalama`、`IS_ROOT=true`、`SCREEN_RESOLUTION=2915*1440`，外加一堆 `IS_SUPPORT_*` 传感器位。
- ⚠ **`TOTAL_MEMORY=7200`（≈7GB）是陈旧值**（本机是 16GB），传感器位全 `false` 也可疑 → 证明这文件是换机前/首装时采的、**平时根本不重采**。
- **删除实验结论**：删掉它后，**强启游戏 + 完整重新登录都不重建它**（mpay/zeus/`ntunisdk_so_uuids` 都刷新了，就它不写）。说明设备信息是游戏**内存里现采现传、不回写磁盘**；磁盘持久化只在"首次安装 / 该 SDK 版本首跑 / 清数据"这种罕见触发点发生。
- **含义**：删这个文件对服务器看到的东西**零影响**（硬件指纹每次会话 live 重算）。它不是"设备身份"的根，只是一份硬件快照缓存。
- **还原方法**（实验后恢复基线，已验证）：
  ```powershell
  # 实验前先备份: su -c "cp -p <file> /data/local/tmp/unisdk_devinfo.bak"
  $f = "/data/data/com.netease.dwrg/shared_prefs/unisdk_devices_infos_file.xml"
  & $adb shell "su -c 'cp -p /data/local/tmp/unisdk_devinfo.bak $f && chown u0_a409:u0_a409 $f && chmod 600 $f && restorecon $f'"
  # restorecon 必须做, 否则 SELinux 上下文不对游戏读不了; 正确上下文 u:object_r:app_data_file:s0:c153,c257,c512,c768
  ```

---

## 3. 生成链：`get_udid` / `machineId`

```
Python get_udid  →  unisdk.getUdid()  (libntunisdk.so, native)
    └─ 综合 Android ID / 虚拟IMEI / vkey  →  缓存到上面那堆 xml/txt

machineId(4E45-… 开头)  →  acsdk native 综合设备特征生成
```

那堆文件都是 **native 层算完后的缓存**，不是源头。源头 = 系统取值（Android ID）+ SDK 自造值（虚拟 IMEI/UUID）+ 服务器下发绑定（vkey）。
每次联网这套指纹跟着上报：acsdk 心跳带 `udid`/`machineId`、unisdk 上报 `vkey`、`IS_ROOT=true` 也在内。
**未深挖**：逆 `libntunisdk.so` 的 `getUdid` 确认 `first_deviceId_cached` 那个 UUID 删了会重建成新随机值还是重算同值（决定"改 UUID"有没有用）。

---

## 4. 跨卸载的真·持久标识（系统级，游戏读不写）

| 标识 | 本机实测值 / 位置 | 卸载后 | 谁能清 |
|---|---|---|---|
| **Android ID (SSAID)** | **`<SSAID_旧机>`** | 装回**同一官方签名**的 APK → 系统照旧发同一个值 | 改 SSAID（见下）、工厂重置 |
| **OAID**（MSA 移动安全联盟，厂商级广告 ID） | 小米系统提供，全 App 共享 | **卸载不变** | 系统设置→隐私→广告，手动重置 |
| **GAID**（Google 广告 ID） | 系统级 | 卸载不变 | 系统设置重置 |
| **Widevine / MediaDRM ID** | 系统级 | 卸载不变 | 工厂重置 |
| **硬件指纹**（型号/ROM/GPU/CPU/屏幕） | 从系统现读 | 不是 ID 但**可原样重算** | 换硬件 |

**Android ID 权威存储**：`/data/system/users/0/settings_ssaid.xml`，按"包名 + 签名证书 + uid"记。本机该文件里 `com.netease.dwrg → <SSAID_旧机>`（uid 10409）。

**服务器端**：账号 `unique_id`（本机 `<账号uid_A>`）+ 网易服务器按上面这些建的画像——**在网易服务器，不在手机**，本地做什么都清不掉。

---

## 5. "重置本机"可行性排序（⚠ 已被第 9 节部分更正，别照旧机这版下死结论）

> **更正（2026-10-18）**：下面原话"换物理设备+换账号+不 root 才是唯一干净组合""服务器多维交叉关联"是**过度猜测**（假设网易全能防御）。用户实战验证的有效手段其实只是：**清 B 层沙箱缓存（卸载/pm clear）+ 改 SSAID**——没碰 OAID/DRM/硬件/root 照样有效，说明封号权重落在 B 层 + SSAID，不是我原先设想的全维交叉。详见第 9.1/9.3。别再往"全能防御"方向堆维度。

原始排序（保留作对照，勿当现用结论）：
- ❌ 删游戏 / 删文件 / 清 App 数据 → 当时判"无效"。**9.3 更正**：清 B 层是有效的一半，只是单独清不够、要配合改 SSAID。
- 🔸 改 Android ID（`com.silverlab.app.deviceidchanger.free` 在 A12+ 其实静默失败，见 9.9；现用自建 KSU 模块）。
- 🔸 重置系统 OAID + 改多维。
- ✅ 换物理设备 + 换账号 + 不 root ← **这条是过度猜测，实战不需要做到这个程度**。

---

## 6. 对注入 / 改 so 的牵连（和叠加层直接相关）

`ntunisdk_so_uuids` = **73 个 native so 的 md5 完整性基线**（含 `libclient.so`、`libsec-lib.so`），`files/` 里，**每次启动重算**。

| 动作 | 动不动基线 md5 | 风险 |
|---|---|---|
| `dlopen` 注入**新** so（`.idv_hook`） | **不改**原 so md5 | 原 so 完整性过得去 |
| 但进程 `maps` 多出不在清单里的模块 | — | ★ **`libsec-lib` 的 maps 扫描（`allHookInfo`）正好逮这个** |

这和 skill 顶部的 /proc 红线是 `libsec-lib` 环境自检的两条不同探针：一条逮"外部进程读 /proc/mem"，一条逮"进程内多了未知注入 so"。叠加层走内核驱动（ioctl，不碰 /proc）+ probe2（进程内 getattr）正是为同时绕开这两条。呼应用户收到过的"检测到修改客户端"警告。

---

## 7. 复现 / 验证方法（含三个踩过的坑）

```powershell
$adb = "C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe"
# 公共区搜设备 ID 明文（务必用 /storage/emulated/0，不是 /sdcard，见坑1）
& $adb shell "su -c `"grep -rlI -e <DeviceId前缀> -e <另一ID前缀> /storage/emulated/0 --exclude-dir=Android 2>/dev/null`""
# 公共区目录树 / 隐藏项（find 无通配，PC 侧过滤，见坑2）
$all = & $adb shell "su -c `"find /storage/emulated/0 -maxdepth 4 2>/dev/null`""
$all | ? { $_ -notmatch '/Android/' } | ? { ($_ -split '/')[-1].StartsWith('.') }
# 游戏的系统 Android ID
& $adb shell 'su -c "cat /data/system/users/0/settings_ssaid.xml"'   # 找 com.netease.dwrg 那条
```

**坑 1（最关键）**：Magisk su 下 `/sdcard` 是**符号链接，find 不跟进**（`find /sdcard` 只回显 `/sdcard` 本身）。
在 `/sdcard` 上跑的 `find`/`grep -r` 会在**空目录**上返回空 → 误判"没有"。**一律用 `/storage/emulated/0`**。
（`ls /sdcard/` 正常，所以只有递归工具中招，很隐蔽。）

**坑 2**：别把含通配符的 pattern（`*/Android/*`、`-name ".*"`）塞进 `su -c "..."`——内层 sh 会**再 glob 一遍**污染参数，返回假空。
用无通配的 `find ... -maxdepth N`，然后在 PowerShell 侧 `Where-Object` 过滤。

**坑 3（PowerShell 引号）**：双引号 PS 串里 `\"` 会**提前结束字符串**，里面的 `|` 泄漏成 PS 管道（`grep -E "a|b"` 直接报错）。
外层用**单引号 PS 串** + 内层 `su -c "..."` 双引号；或像上面那样用反引号 `` `" `` 转义内层双引号。

---

## 8. 未决 / 下次可做

1. ✅ **已解（9.3）**：删 `first_deviceId_cached`（UUID）后重建成**新随机值**（`<另一ID前缀>…`→`a46aff9d…`），不跟 SSAID 走 → 删它=白赚一个新 per-install 维度，值得清。
2. 找 OAID/openudid 当前落点（shared_prefs 里不在，查 `files/keva`、`files/zeus_p`、`files/volc_log`）。**仍未决**。
3. ✅ **已解（9.3）**：改 SSAID 后，`DeviceId.txt` 的 `device_id` **重建为当前 SSAID**（证明 device_id=SSAID）；但要先清沙箱缓存才会重读，光改 SSAID 不清缓存无效。

> 设备端基线备份：`/data/local/tmp/unisdk_devinfo.bak`（`unisdk_devices_infos_file.xml` 原件，md5 `a31ce542…`）。
> PC 侧实验产物：scratchpad `unisdk_diff\before.xml`（会话级，可能已清）。

---

## 9. 2026-10-18 新机实证大更新（warsaw / Android 16 / Shamiko，游戏整盘迁移自旧机）

### 9.0 环境
- 新机 **warsaw**（REDMI K90 Ultra, Android 16, HyperOS OS3.0），Magisk **30.7** + Zygisk(`zygisk=1`) + **Shamiko 白名单模式**（`denylist=0`，Shamiko 反转语义：名单内可见 root、名单外被藏；第五人格不在名单→被藏）。
- 游戏从旧机 socrates **整盘迁移**而来，UID 仍 `u0_a409`(10409)。
- SSAID 已用自建 KSU 模块改为 **`<SSAID_新>`**（旧机是 `<SSAID_旧机>`）。
- ⚠ **不要再用分析 Magisk denylist 的方式判"游戏看不看得到 root"**——Shamiko 白名单会反转，denylist 开关不作数。要判就看游戏**进程内实际读取**（9.5）。

### 9.1 两层身份模型（核心框架，取代旧的"一锅端"直觉）
- **A 层·现读系统 ID**：SSAID / OAID / GAID / DRM / 硬件指纹。每次启动现读，游戏基本不持久写（设备信息是内存现采现传，见 2.4）。改它要动系统（SSAID 用我们的 KSU 模块）。
- **B 层·一次性写死沙箱缓存**：UUID(`UNISDK DeviceUtils.xml`) / 伪IMEI(`virtualImeiAndImsi.xml`) / device_feature / vkey / `DeviceId.txt`。首次生成后只读不写，**扛重启、扛改 SSAID、扛换机迁移**。
- **改 SSAID 清不掉 B 层；pm clear/删文件清不掉 A 层。两层独立，各打各的，缺一不彻底。**

### 9.2 换机迁移证据：B 层"写死"，游戏除非清数据根本不重写
- 迁移后这些身份文件 mtime 停在**旧机时代**（2026-01-04 / 02-05），`MODEL=22127RK46C`、`TOTAL_MEMORY=7200`(旧机值) 都在。
- 今天完整登录：`HTTPQ_*`/`applog_*`/`cookieStore`/mpay 等**大量文件刷到 10-18**，唯独 UUID/伪IMEI/device_feature/vkey/DeviceId **纹丝不动**。
- **结论**：游戏对 B 层只读不写 → 换机迁移把旧机身份整盘搬过来，游戏到现在就这几维仍"认旧机"。这就是用户"换机后有些旧信息没改过来"的机制答案。

### 9.3 清理实测（pm clear + 删外部）与各文件重建行为
- `pm clear` = 清内部 `/data/data`（本次仅 **270MB**，大头是 `app_so_uf` 253MB native 库；游戏资源**不在内部**）。权限/SELinux 自动复位。
- 外部 `/sdcard/Android/data`：pm clear **不保证清**（版本/OEM 相关），须**单独 `rm`**。
- **SSAID 不受 pm clear 影响**（在 `/data/system`，清完仍 `<SSAID_新>`）。obb 空（3.5K），"保留 obb"没省到任何东西。
- 重登后重建（实测）：
  | 文件 | 清前(旧机迁移) | 重登后 | 性质 |
  |---|---|---|---|
  | UUID `first_deviceId_cached` | `<另一ID前缀>-…-2a13` | **`a46aff9d-…-649a`** | 纯随机，≠SSAID |
  | **`DeviceId.txt` 的 `device_id`** | `<DeviceId>` | **`<SSAID_新>`** | **= 当前 SSAID！** |
  | 伪IMEI / device_feature / vkey / unisdk_devices_infos | (有值) | 登到主界面**仍未重建** | 懒加载，疑似进对局/反作弊 init 才写 |
- **因果链（回答"免卸载清环境"）**：
  - 只改 SSAID 不清沙箱 → `DeviceId.txt` 留旧缓存，游戏仍认旧 device_id（**= 换机后的状态**）。
  - 只清沙箱不改 SSAID → `DeviceId.txt` 重建但重读的还是旧 SSAID，等于没换。
  - **改 SSAID + 清沙箱**（齐做）→ device_id 真正变新。
  - 替代卸载重装：`pm clear` + `rm DeviceId.txt` + 改 SSAID = 等效且秒级、不用重下客户端（但见 9.4 别乱删）。

### 9.4 资源位置与"别触发重下"（踩过的 7GB 坑）
- **全部 ~7GB 游戏资源在 `/sdcard/Android/data/com.netease.dwrg/files/netease/`**；`DeviceId.txt` 是 `files/` 下的**同级小文件**。
- 清身份**只删 `files/DeviceId.txt`**，别 `rm -rf` 整个外部目录——否则 `netease/` 被端 → **全量重下**。迁移来的是**不完整 3.5GB**，一旦重铺要的是**完整客户端 7GB**。
- 内部 270MB native 库 pm clear 后会便宜重铺；`app_uf_ver`/`app_uf_unity_info`(资源版本标记)在内部，pm clear 会重置它 → 理论上可能触发资源校验（本次重下实为我们 `rm -rf` 外部所致，非 pm clear；待下次纯净验证）。

### 9.5 ★ IS_ROOT 真值读法（取代旧的 cat 陈旧快照）
- **旧法（本 doc 2.4）靠不住**：cat `unisdk_devices_infos_file.xml` 里的 `IS_ROOT=` ——那是"一次性写死"**陈旧快照**（旧机 socrates 首装值），不是 live 值，清掉后还不重建。旧 doc 0/2.4 节的 `IS_ROOT=true` 就是这个陈旧值。
- **新法（稳定可复现，强烈推荐）**：probe2 进程内调游戏**自己的 getter**，拿 native 现算值：
  ```python
  import unisdk
  unisdk.getPropStr('UNISDKUTILS_IS_DEVICEROOTED3')   # '0'=未root  '1'=root（libntunisdk 现算现判）
  ```
- **新机实测 = `'0'`（false）**。文件层探测（su/magisk/挂载进程内全不可见）与原生判定（`'0'`）两边一致 → **Shamiko 白名单把 root 对第五人格藏住了，游戏看你是没 root 的**。
- **更正**：旧 `IS_ROOT=true` 是旧机陈旧快照；新机 live 值 = **false**。root 这维当前干净，且和"procedure 一直在 root 下跑却有效"吻合——root 不是封号点。

### 9.6 unisdk Python 绑定速查（probe2 通道里可直接调）
- getter：`unisdk.getPropStr(key)` / `unisdk.getPropInt(key, default)`（**Int 需 2 个参数**，少传报 `function takes exactly 2 arguments`）。
- 实测值：`getUdid()` / `getPropStr('UDID')` = **`<UDID>`**（综合 udid，≠SSAID≠DeviceId.txt）。`getPropStr('UNISDKUTILS_GET_CPUNAME')` 返回 None（该 key 走别的路径，不影响）。
- key 常量：`UNISDKUTILS_IS_DEVICEROOTED3`、`UNISDKUTILS_GET_CPUNAME/CPUCORE/CPUMHZ`、`UDID`、`USERINFO_*`、`NT_AUTH_NAME_*`、`SDC_LOG_*`。
- 相关对象：`core.sdk.PharosPy.DeviceProbe`（Pharos 反作弊设备探测，host `whoami.nie.netease.com`，`PROBE_URL=/v6`）、`common_cs.h55_utils.utils_device.UtilsDevice`（偏硬件/触感，无 is_root）。

### 9.7 probe2 命令通道用法（本会话工作流）
- payload：`injection-research/payload_probe2_beautify.py`（IdentityV repo），注入后进程内常驻。
- 通道：写 Python 到 **`/sdcard/Android/data/com.netease.dwrg/files/idv_cmd.py`** → 探针每 ~2s `exec`、删该文件、结果写 **`idv_cmd_out.txt`**。注入 globals 提供 `P()`(print)、`R()`(repr 截断)、`S()`(安全取值)、`GK()`、`mgr` 等。
- 内嵌 CPython = **3.11.6，砍掉了 `_ctypes`**（`import ctypes` 直接 `ModuleNotFoundError` 崩整段）→ 别用 ctypes；读系统属性走 `unisdk.getPropStr` 或读文件。
- 本会话取数脚本：scratchpad `wait_read.sh`（删旧 out→cp cmd→设备侧 `while` 等 out→cat），`su -c sh` 跑，绕开主机 sleep 限制和多层转义。
- **adb push 本地路径坑**：Git Bash 下 `export MSYS_NO_PATHCONV=1` 会让 `/c/...` 原样传给 Windows adb → `cannot stat`。**本地源路径用 `C:/...` 盘符形式**，远端 `/data/local/tmp` 保持不转，一条命令两头都对。

### 9.8 注入暴露（/proc/self/maps 自曝，呼应第 6 节红线）
- maps 里注入 = **`/data/local/tmp/.idv_hook_<rand>.so (deleted)`** 三段（r-xp/r--p/rw-p）。`(deleted)` 删磁盘文件**不会从 maps 抹掉路径名** → 反作弊扫自己的 maps 即可发现（`/data/local/tmp`、`.so (deleted)`、`idv`/`hook` 任一字样都是信号）。
- 在场反作弊 native（都能扫 maps）：`libpharos.so`、`libAwometasec_ml.so`(gbsdk ML 风控)、`libzeusflipped.so`、`libsecsdk.so`、`libEncryptorP.so`、`libntunisdk.so`/`libNtUniSdkRoostX.so`、`libmagtsdk.so`、`libappdump_core.so`、`libAndroidCrashHandler.so`。`.idv_hook_*` 是唯一外来可执行段。
- `memfd` 7 个大多正常（`jit-cache`/`jit-zygote-cache` = ART），非注入。
- 降暴露方向（按性价比）：① memfd 加载（maps 显示 `/memfd:`，混进 ART）② 换落地路径 + 仿游戏库名（放 `app_so_uf/.../lib/`、名仿 `libAudioXXX.so`）③ 加载后匿名化 maps 路径（工程量大）。

### 9.9 新建工具：SSAID Changer KSU WebUI 模块
- 路径：**`C:\Users\31297\Desktop\逆向\ssaid-changer-ksu\`**（`module.prop` / `webroot/index.html` / `README.md` / `ssaid-changer-webui.zip`）。单页免构建，刷了就用。
- 来源：逆 `com.silverlab.app.deviceidchanger.free`(闭源)行为规格 + 参考 `sidex15/deviceidchanger`(AGPL-3.0)。
- 功能：①列有 SSAID 的包 + 改 + 随机（**同时改 `value` 和 `defaultValue`**）②记住上次操作的包（存 `/data/adb/ssaid_changer_last.txt`，抗清理）③两档清理——**极简**(删 `shared_prefs` 里 UUID/伪IMEI/device_feature/unisdk_devices_infos 四个 xml + `files/DeviceId.txt`，不 pm clear，**零重下/不掉登录**) / **稳妥**(`pm clear` + 删 `DeviceId.txt`，等效卸载内部)；两档都点两下确认、都不动 SSAID ④重启。
- 关键修：WebUI(KSU/WebUI-X) webview 的 **`window.confirm` 默认返回 false**（按钮点了没反应）→ 改两段式点确认；reboot 用 `svc power reboot || setprop sys.powerctl reboot || reboot`。
- **ABX（最要紧）**：A12+ 的 `settings_ssaid.xml` 是二进制 **ABX**（magic `41 42 58 00`），必须 `/system/bin/abx2xml`↔`xml2abx` 往返；改完**连 `defaultValue` 一起改**，否则开机被 default 回填。Silverlab app **没有 ABX 处理 → 在 A12+ 静默失败**（这是它除"app 自身要不到 su"之外的第二个死因）。实测 A16 往返无损、改动精确、重启持久化（`<SSAID_新>` 重启后仍在）。
