---
name: android-re-toolkit
description: 用户本机 Android 逆向工程环境的工具位置速查表 + 跨项目通用经验（Frida/adb/IDA 的坑，不针对具体某个游戏）。任何时候开始一个新的 Android APP/游戏逆向任务（不管是哪个包名），在动手之前先读这个 skill，把工具路径和已知坑复用起来，不用每次重新摸索 adb/frida-server 在哪、frida 17.x 的 API 怎么变了这些环境层面的东西。跟某个具体游戏/APP 的业务逻辑发现（比如"物种起源"、"荒野日记"、"第五人格"）无关的、纯工具链层面的经验都记在这里；具体某个项目的存档格式/加密key/内存偏移这类发现记在那个项目自己的 SKILL.md 里（通常放在项目文件夹或 `C:\Users\31297\Desktop\逆向\` 下）。用户说"更新一下工具链笔记""记录一下这次踩的环境坑"时，按文末更新规范修改本文件。
---

# Android 逆向工具链速查 + 通用经验

## 一、工具位置

| 工具 | 路径 | 备注 |
|---|---|---|
| adb (主用) | `C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe` | |
| adb (备用) | `D:\MiFlash2020-3-14-0\ADB\adb.exe` | 同一台设备两个 adb 都能连，坏一个换另一个 |
| frida (PC端 CLI) | `C:\Users\31297\AppData\Local\Programs\Python\Python313\Scripts\frida.exe` | 装在 Python 3.13 环境下，注意机器上还有个 Python 3.11，**frida 相关的都用 3.13 那个**，别搞混 |
| frida-server (设备端) | `/data/local/tmp/frida-server` | v17.5.2，**默认不是开机自启的**，每次新会话要手动用 `su -c '/data/local/tmp/frida-server > /data/local/tmp/frida-server.log 2>&1 &'` 启动一次。2026-10-15 新机 warsaw 已 push 并 `chmod 755`（实测 `frida-ps -U` 连通），但**仍不是开机自启**，重启后要重新 `su -c` 启动一次 |
| IDA Pro | `C:\Users\31297\Desktop\逆向\_通用工具\IDA Pro 8.3\idat64.exe` (命令行批处理) / `ida64.exe` (GUI)。**⚠️ 这个路径含中文，直接跑会报 `加载库 pc64.dll 错误: 找不到指定的模块`、ELF 被识别成 Binary file。** 解法：建一个纯 ASCII 路径的目录联接再从联接启动：`New-Item -ItemType Junction -Path <ASCII路径>\ida -Target "<上面的目录>"`。2MB 的 arm64 可执行文件（带 ImGui/FreeType）全量反编译要 10 分钟以上 | 8.3 版，带 Hex-Rays。首次全量 auto-analysis 一个 20MB+ 的 arm64 .so 大概 15~30 分钟，`.i64` 数据库存下来下次能直接复用秒开 |
| frida-server 安装包 (PC 端备份) | `C:\Users\31297\Desktop\逆向\_通用工具\frida-server`(已解压二进制) / `frida-server-17.5.2-android-arm64.xz`(原始下载包) | 设备重启/换设备后不用重新下载，直接 `adb push` 这个已解压的二进制到 `/data/local/tmp/` 再 `chmod`+`su -c` 启动；`.xz` 用 Python `lzma` 模块解压，不需要装额外的 xz 工具 |
| Il2CppDumper | `C:\Users\31297\Desktop\逆向\_通用工具\Il2CppDumper` / `Il2CppDumper-bin` | 跨项目通用，只对**真正的 Unity il2cpp 游戏**有用（先用下面 4.5 的方法确认引擎类型，别对着 cocos2d-js 之类的游戏瞎跑） |
| 进程内存安全读取器 | `C:\Users\31297\Desktop\逆向\_通用工具\procmem\devread.py` | 跨项目通用。PC 侧经 adb+root 读目标进程内存，**自带缺页防护**，用法和原理见第五节。凡是"想验证内存偏移/结构体布局，但不想改代码重编译"的场景，先想到它 |
| il2cpp metadata 魔数校验脚本 | `C:\Users\31297\Desktop\逆向\_通用工具\check_metadata_magic.py` | 读文件头 4 字节，判断是否是 `global-metadata.dat`(魔数 `AF1BB1FA`)，一行命令快速确认拿到的文件对不对，省得跑完整个 dump 流程才发现文件不对 |

## 一点五、写 Android App（注入器/工具 APK）时的环境

- **JDK**：`D:\Java\jdk-22`（Temurin 22.0.2，`JAVA_HOME` 和 PATH 都指这里）。这个目录被用户清理垃圾时删过一次，症状是 `java -version` 直接崩（退出码 0xC0000409）；重装同路径即可，环境变量不用动。PATH 里还留着一条无效的 `D:\Java\jdk-22\jre\bin`（JDK 9 以后没有 jre 目录了），无害。
- **Gradle**：不需要额外装，缓存里已有多个发行版，直接用 `C:\Users\31297\.gradle\wrapper\dists\gradle-8.14-bin\<hash>\gradle-8.14\bin\gradle.bat -p <工程目录> assembleDebug`。AGP 8.7.3 + Gradle 8.14 + JDK 22 实测可用。
- **⚠️ AGP 不接受含中文的工程路径**（报 `Your project path contains non-ASCII characters`）。所以 Android 工程不能放在 `C:\Users\31297\Desktop\逆向\` 下面，要单独放纯英文路径。
- 首次构建要联网拉 AGP 依赖；`local.properties` 里写 `sdk.dir=C\:\\Users\\31297\\AppData\\Local\\Android\\Sdk`。
- **签名/验签工具**：`keytool` 在 `D:\Java\jdk-22\bin\keytool.exe`；`apksigner` 在 `C:\Users\31297\AppData\Local\Android\Sdk\build-tools\36.1.0\apksigner.bat`。`apksigner verify --print-certs <apk>` 看证书指纹，覆盖安装前先比对新旧包指纹是否一致（debug 包和正式包签名不同，不能互相覆盖，只能先卸载）
- **正式包签名配置放 `keystore\signing.properties`**（storeFile/storePassword/keyAlias/keyPassword），`app\build.gradle` 读它，文件存在才签名；目录要进 `.gitignore`。PKCS12 keystore 的 key 密码就是库密码
- **keystore 密码忘了**（2026-10-01 实战）：先排除文件格式问题——Properties 会把行尾空格算进值、把 `\` 当转义、BOM 会让第一个 key 变成 `\ufeffstoreFile`；再用 `keytool -list -keystore x.jks -storepass <候选>` 单独验证，排除 Gradle 的干扰。当初如果是 Claude 在某次会话里用 `keytool -genkeypair` 生成的，**密码就在 `~\.claude\projects\**\*.jsonl` 会话记录里**：grep `storepass`/`keypass`/`storePassword` 提取候选，逐个 keytool 验证。全程只输出长度、是否匹配，**不要把密码打印到对话里**，找到后直接写进 signing.properties

### 安卓版本相关的坑
- **Android 14+ 前台服务必须声明子类型对应的权限**。用 `foregroundServiceType="specialUse"` 就必须加 `FOREGROUND_SERVICE_SPECIAL_USE`，否则 `startForeground` 抛 SecurityException 直接把进程打挂（只加 `FOREGROUND_SERVICE` 不够）。
- **查已安装应用别用 `getInstalledPackages`**：在 HyperOS 上那属于"获取应用列表"权限，每次启动都弹窗。改成在清单里用 `<queries><package android:name="…"/></queries>` 显式列出候选包名，逐个 `getPackageInfo`，不需要任何权限。
- **`Service.onStartCommand` 在主线程**，里面做 `InetAddress.getAllByName` 会抛 `NetworkOnMainThreadException`，要丢到子线程。
- **MIUI/HyperOS 的"上滑清理最近任务"会 force-stop 应用**（日志里是 `ProcessSceneCleaner: SwipeUpClean` + `Killing … due to SwipeUpClean`），前台服务也挡不住。做 VPN/常驻服务类工具时，务必提醒用户别清掉它，否则表现是"功能突然失效"，极难排查。
- **MIUI/HyperOS 拦截 USB 装包**：`adb install -r` 报 `INSTALL_FAILED_USER_RESTRICTED: Install canceled by user`，是要在手机上点确认（或开发者选项里开"USB 安装"）。屏幕坏了/不想点时，用 root 绕过：`adb push x.apk /data/local/tmp/` → `adb shell "su -c 'pm install -r /data/local/tmp/x.apk'"` → 删掉临时文件。验证：`dumpsys package <pkg> | grep lastUpdateTime`
- **`adb shell am start-foreground-service` 启动不了自家的 VpnService**（报 `Requires permission not exported from uid`）。想用 adb 驱动测试，就在 Activity 里加一个隐藏入口（读 Intent extra 后自己调 `startService`），然后 `am start -n <pkg>/.MainActivity --es auto <参数>`。

### 无 root 流量拦截（VpnService）要点
- `addAllowedApplication(pkg)` 只捕获目标应用；`addRoute` 只加需要的 /32，其余流量完全不进 TUN，风险小。
- DNS 劫持：`addDnsServer` 指到一个假 IP 并路由它，自己回 A 记录。**非劫持域名不要自己发 UDP 转发**（在 VPN 环境下容易超时，导致目标应用所有域名解析失败），直接用系统解析器 `InetAddress.getAllByName` 合成应答即可——注入器自身不在 VPN 内，走的是正常网络。
- **AAAA 查询一律回空答案**，否则应用可能走 IPv6 直连绕过拦截。
- **别用自写 TCP 传大文件**。可行的做法是：只用自写 TCP 处理那几个能改写目标地址的小请求，把大文件的下载地址改指到 `127.0.0.1:<高位端口>`，由标准 `ServerSocket` 提供。安卓应用**不能监听 1024 以下端口**，所以纯靠 DNS 劫持 + 本地服务器是不行的，必须先有一个能改写地址的小拦截点。
- 日志一定要落盘到 `filesDir`，logcat 在 MIUI 上几十秒就被刷没了。

## 二、设备信息

- **当前设备（2026-10-15 起换新机）**：型号 `warsaw`(`M332BF`，**REDMI K90 Ultra**)，Android 16 / HyperOS OS3.0（`OS3.0.305.0.WHPCNXM`），内核 **6.6.118**，arm64-v8a，16GB RAM。
- **旧机 `socrates`(`22127RK46C`，Android 15 / HyperOS，内核 5.15) 已退役**——下文（及其它 skill）凡提到"旧 Redmi / socrates""屏幕漏液 / 幽灵触摸 / 开机脚本屏蔽触摸""这台 5.15"都是**旧机历史记录**，对新机不成立：新机屏幕正常、触摸屏是 `goodix_ts`、无需 `phone-screen-fix`。`phone-screen-fix` skill 专属旧机，保持原样不动。
- root 方式：Magisk，`su -c '<cmd>'` 有效（新机实测 `context u:r:magisk:s0`）
- 截图：`adb shell screencap -p /sdcard/x.png` + `adb pull /sdcard/x.png <本地路径>`
- 点击/滑动：`adb shell "su -c 'input tap X Y'"` / `su -c 'input swipe X1 Y1 X2 Y2 duration_ms'`（**普通 `adb shell input tap` 在这台设备上会报 `SecurityException: 需要 INJECT_EVENTS 权限`，必须套一层 `su -c`**）
- 截图坐标系是**设备原始分辨率**(比如 1440x3200)，如果截图工具显示的是缩放后的尺寸(比如 900x2000)，点击坐标要按比例换算回原始分辨率再传给 `input tap`
- **2026-09 起这台手机屏幕漏液损坏**：触摸屏默认被开机脚本屏蔽，上方 41% 触摸硬件失灵。操作它先看 `phone-screen-fix` skill（`桌面\PhoneScreenFix`，插电脑跑 `.\fix.ps1`）。现在 `persist.security.adbinput=1` 已开，普通 `adb shell input` 不再需要 `su`

### 投屏/远程操控
- scrcpy 用 scoop 装的（`scoop install scrcpy`，v4.1，自带 adb）。输入注入同样受 MIUI「USB调试（安全设置）」限制，报 `INJECT_EVENTS` 就是没开。
- **MIUI「USB调试（安全设置）」= 系统属性 `persist.security.adbinput`**。屏幕坏了没法点开关时，root 下 `setprop persist.security.adbinput 1` 然后**重启**才生效（只 setprop 不重启，`input` 照样报 INJECT_EVENTS）。
- 锁屏密码界面是 FLAG_SECURE，scrcpy 里是黑的，但输入照常送达：点窗口后直接键盘输密码回车。
- scrcpy 默认键盘模式打不了中文（日志 `Could not inject char u+xxxx`）：`Ctrl+V` 粘贴，或 `--keyboard=uhid` 用手机输入法。

### 屏蔽/过滤某个输入设备（坏屏幽灵触摸、按键短路）
- 内核层开关：`echo 1 > /sys/class/input/inputN/inhibited`（Linux 5.10+ 有，这台 5.15），写 0 恢复，重启失效。inputN 编号**重启会变**，按 `/sys/class/input/input*/name` 找名字，别写死编号。开机要持久就放 Magisk `/data/adb/post-fs-data.d/`（在 zygote 前执行）。
- 看是哪个设备在报事件：`getevent -lt`（抓全部），不要先入为主。
- 只过滤部分触点：root 程序 `EVIOCGRAB` 独占真实设备 + uinput 克隆一个（抄 `EVIOCGABS` 各轴范围 + `INPUT_PROP_DIRECT`），Android 会认成内屏触摸屏。现成实现：`桌面\PhoneScreenFix\src\evfilter.c`（NDK 28 在 `Sdk\ndk\28.2.13676358`，`aarch64-linux-android30-clang.cmd` 直接编）。
- **Android 14+ 触摸屏上有指针一直按着（比如一个卡住的幽灵触点）时，InputDispatcher 会丢掉其他设备（scrcpy/`input`）注入的点击**，现象是"电脑突然点不了"。查 `dumpsys input` 里的 `touchingPointers=[Pointer(...FINGER)]`。
- 有些"触摸引起的行为"不走 input 设备：小米锁屏的「大面积触摸自动息屏」走的是传感器（`xiaomi.sensor.large_area_detect`），屏蔽触摸 input 挡不住；息屏原因看 `dumpsys power` 的 `mLastSleepReason` + logcat 的 `Going to sleep due to` / `goToSleepInternal ... pid`。
- 看到电源键事件别急着认定是硬件短路——先问用户是不是自己在按（这次就误判过，把用户的电源键屏蔽了）。

## 三、Frida 使用要点(反复踩过的坑)

### 3.1 `-t`/`--timeout` 单位是秒，不是毫秒！
第一次犯这个错：把 `-t 6000` 当成"6秒"用，实际是 6000 秒(≈100分钟)，导致命令"卡住不动"——其实是正常干完活了，只是连接还没到超时时间不会自己退出。**一次性小任务用 `-t 5`~`-t 10` 就够**，需要长期常驻纠正的场景才用大数字（比如 `-t 3600`）。

### 3.2 Frida 17.x 的 API 变化
- `Module.findExportByName(null, name)` 不行了，全局搜索改用 `Module.findGlobalExportByName(name)`，或者先 `Process.getModuleByName(moduleName).base` 拿基址自己加偏移，或者 `Module.getExportByName(moduleName, name)`(必须指定模块名)
- `Memory.readU16(ptr)` / `Memory.readU8(ptr)` 这种全局静态方法已删，改成 `ptr.readU16()` / `ptr.readU8()` 挂在 NativePointer 上的方法链式调用
- `Module.findBaseAddress(name)` 也不行了，用 `Process.getModuleByName(name).base`

### 3.3 spawn 模式在这台设备上必超时
`frida -U -f <package> -l script.js` 这种 spawn 模式，在**旧机**(socrates, Android 15 / HyperOS, frida-server 17.5.2)上稳定复现 `Failed to spawn: unexpectedly timed out while waiting for signal from process`，换 SELinux permissive、换干净 frida-server 都没用，具体原因没查清（怀疑是 Android 15 zygote/USAP 池变化）。**必须用 `frida -U -p <PID>` attach 模式**，PID 先用 `adb shell pidof <包名>` 查出来再传。（新机 warsaw / Android 16 尚未复测此坑；在新机上首次 spawn 若超时，直接套用 attach 兜底即可。）

### 3.4 跨线程调用 JS 引擎的 evalString 会崩进程
`ScriptingCore::evalString`/`se::ScriptEngine::evalString` 这类"从原生代码执行一段 JS"的函数，**如果从 Frida 自己的线程直接调用会导致 access violation，把游戏进程直接打挂**(在"荒野日记"项目上验证过两次，都是直接崩)。

**安全做法**：`Interceptor.attach` 的 hook 回调是在"被 hook 函数原本所在的线程"同步执行的，不是 Frida 另开的线程。找一个**本来就跑在游戏主线程/JS线程上、每帧必然被调用一次**的原生函数作为锚点（cocos2d-x 系列引擎可以用 `cocos2d::Scheduler::update(float)`，这个函数在几个不同游戏的 build 里都稳定存在），在它的 `onEnter` 里再调用 `evalString`，线程就是对的，反复验证过安全、不会崩。

标准模板：
```javascript
var soName = "libXXX.so"; // 具体引擎库名
var base = Process.getModuleByName(soName).base;

// 先用 IDA/objdump 找到这几个符号在目标 build 里的偏移
var schedulerUpdateAddr = base.add(SCHEDULER_UPDATE_OFFSET);
var scGetInstance = new NativeFunction(base.add(SC_GETINSTANCE_OFFSET), "pointer", []);
var scEvalString  = new NativeFunction(base.add(SC_EVALSTRING_OFFSET), "bool", ["pointer", "pointer"]);

var script = Memory.allocUtf8String('/* 你要跑的 JS 源码 */');
var done = false;
Interceptor.attach(schedulerUpdateAddr, {
    onEnter: function (args) {
        if (done) return;
        done = true;
        var ret = scEvalString(scGetInstance(), script);
        console.log("[inject] ret=" + ret);
    }
});
```
**这个技术已经在"物种起源"项目上反复大规模使用，稳定可靠**，是目前对付"游戏逻辑打包成字节码、静态分析不动"这类场景最有效的手段——不用真的读懂字节码，直接在运行时借游戏自己的 JS 引擎跑任意查询/修改代码。

### 3.5 注入脚本的 console.log 输出在哪
如果用 3.4 这套"借用游戏自己引擎执行 JS"的技术，**注入脚本里的 `console.log` 走的是游戏自己的原生日志通道(Android logcat)，不是 Frida 自己的 stdout**！Frida 脚本自己(运行在 Frida 那个独立 JS 运行时里)的 `console.log` 才会出现在 `frida -q` 命令的终端输出里。这两个日志通道完全分开，第一次遇到这种技术时很容易搞混，以为脚本没执行，其实是看错了地方。

### 3.6 logcat 环形缓冲区会被系统噪音快速挤掉
系统噪音(MIUI/HyperOS 组件日志、音频驱动刷屏等)能把日志缓冲区快速挤满，导致 `adb logcat -d | grep xxx` 事后去捞经常捞空，**不代表事情没发生，只是被冲掉了**。（旧机 socrates 缓冲区只有 128KB，**20~30 秒**就满；新机 warsaw 的 `persist.logd.size` 是 4MB，没那么急，但 HyperOS 噪音仍大，下面的流式监听习惯照样该保持。）

**要抓稀疏或限时的事件，用实时流式监听而不是事后快照**：
```bash
adb logcat -v brief | grep --line-buffered -E "你要找的关键字"
```
（Claude Code 环境里对应用 Monitor 工具挂一个持续监听的 grep 管道）

### 3.7 多个残留的 frida.exe 进程会互相打架，产生完全误导性的现象
测试过程中如果连续跑了很多次 `frida -U -p PID -l script.js`，**一定要确认上一个真的退出了再跑下一个**。曾经因为好几个旧脚本(目标数值互相冲突)同时挂在同一个进程的同一个属性上，产生了"数值每秒被神秘重置"这种完全是假象、但排查起来极其真实可信的现象，浪费了大量时间才发现是自己的残留进程在打架。

**每次开始一轮新测试前**：
```powershell
Get-Process frida* -ErrorAction SilentlyContinue | Stop-Process -Force
```
**怀疑数据已经被污染时，最彻底的做法是连 frida-server 也一起在设备上 `pkill` 重启**，不要只信任"上一个命令应该已经退出了"这种假设。`TaskStop`(或类似的"停止后台任务"操作)停的是外层包装的 shell 命令，不保证底层 `frida.exe` 进程真的退出了。

### 3.8 JS 引擎里的 monkey-patch 是进程级持久的，跨 Frida 连接有效
用 3.4 的技术给目标 JS 对象挂的 `Object.defineProperty` 陷阱、重写的全局函数（比如 `Date.now`）等，**只要目标 APP 进程不重启，就会一直留在它的 JS 全局状态里**，即使 Frida 断开重连、换一个全新的 `frida -U -p PID` 会话，这些补丁依然生效（因为补丁改的是目标进程自己的内存状态，不是 Frida 侧维护的）。

**这既是优点也是坑**：
- 优点：不需要长期占用一个 Frida 连接，装完补丁可以直接断开
- 坑：想要"干净重测"、排除历史补丁干扰时，**光断开 Frida 连接不够，必须真正杀掉目标 APP 进程再重新拉起**（`am force-stop` 在部分设备/场景下不可靠，见下一条，稳妥做法是 `su -c 'kill -9 <pid>'` 后 `ps -ef | grep` 确认真的没了）

### 3.9 `am force-stop` 不总是可靠
实测出现过 `am force-stop <package>` 执行完、`pidof` 查出来的进程 pid 和启动时间完全没变的情况（等于没杀掉）。**想确保进程真的被杀干净，用 `su -c 'kill -9 <pid>'` 后再 `ps -ef | grep <package>` 确认**，比信任 `am force-stop` 靠谱。

### 3.10 cocos2d-x / Cocos Creator 游戏：在 Java 层只读抓 HTTP（2026-09-30，荒野日记验证）
cocos 的 `XMLHttpRequest` / `HttpClient` 在 Android 上最终走 Java 类 **`org.cocos2dx.lib.Cocos2dxHttpURLConnection`**，hook 它的三个静态方法就能拿到全部请求，**完全不碰 JS 引擎，没有 3.4 那种跨线程崩溃风险**：
- `createHttpURLConnection(String url)` → URL（GET 参数都在这里）
- `sendRequest(HttpURLConnection conn, byte[] body)` → POST 体
- `getResponseContent(HttpURLConnection conn)` → 响应体（`byte[]`，`Java.use("java.lang.String").$new(b, "UTF-8")` 转字符串）

要点：
- frida 17.5.2 CLI 的 `-l` 脚本里 `Java.perform` 直接可用（CLI 自带 Java bridge），attach 模式：`frida -U -p <pid> -l x.js -q -t 1800 *> log.txt`，放后台跑，日志落本地文件
- 先在 `classes.dex` 里搜 `Lorg/cocos2dx/lib/Cocos2dxHttp` 确认类名存在
- 在 `createHttpURLConnection` 的 implementation 里改 url 再传给原方法，就能改写请求参数——**这属于改服务器请求，必须用户明确要求才做**（荒野日记那次第一次尝试被权限分类器拦了，用户明确要求后才做的对照实验）
- 换 hook 前务必杀干净旧 frida（3.7），后台任务报 `failed exit 255` 是被主动杀掉，正常
- 现成脚本：`逆向\荒野日记：孤岛_1.8.9.0\scripts\frida_http_logger.js`（只读版），其他 cocos 游戏可直接复用

## 四、静态分析要点

### 4.0 PowerShell 工具本身的坑（2026-10-01）
- **一条命令里既有 `@'…'@ | python -` 又有 `Remove-Item`**，工具的安全检查会把 here-string 里的 Python 代码（比如 `"\n".join`）误当成 Remove-Item 的路径，报 `Remove-Item on system path … is blocked`，整条都不执行。拆成两条命令分别跑，删除用 `Remove-Item -LiteralPath '<完整路径>'`
- 权限分类器偶尔返回 "no verdict (error)"，是临时故障不是拒绝；只读排查可以先改用 Grep/Read 工具继续，不用干等

### 4.1 Git Bash / PowerShell 下 adb 操作设备路径的坑
Git Bash (MSYS) 会自动把形如 `/sdcard/xxx` 这种看起来像 Unix 绝对路径的字符串，当成本地路径做转换(比如转成 `D:/xxx/sdcard/xxx`)，导致 `adb push`/`adb pull`/`adb shell` 里涉及设备端路径的命令全部失败，而且报错信息很有迷惑性("文件不存在"，而不是"路径被改写了")。**用 Git Bash 操作 adb 设备端路径前，先 `export MSYS_NO_PATHCONV=1`**。

**2026-10-15 换新机 push frida-server 时又撞到，补几条实证与更省事的替代法：**
- 本构建里的具体转换形态：`adb push <本地> /data/local/tmp/x` 把远端目标转成 `D:/Git/data/local/tmp/x`，报 `remote secure_mkdirs() failed: No such file or directory`（甚至还会打印一行 `1 file pushed` 迷惑你，其实没落到位）。`adb pull /sdcard/x.png` 同理转成 `D:/Git/sdcard/x.png`。
- **只有"裸露的、以 `/` 开头的参数"会被转**。`adb shell "su -c 'cat /data/.../x'"` 里远端路径在**单引号**内，MSYS 不碰——所以带管道/`grep`/`$` 的 `adb shell` 侦察命令用 Bash 工具反而最顺（pwsh 里 `\"` 会把双引号字符串提前截断，命令散架，见 4.1.1）。
- **最省事的拉包法：`adb exec-out "su -c 'cat <设备端绝对路径>'" > <本地文件>`**。远端路径在单引号里不被转换，`exec-out` 二进制安全，还能直接读 root-only 的 `/data/data/<pkg>/...`，一步到位——**不用先 `cp` 到 `/sdcard` 再 pull**（也就绕开了下一条 pwsh 的 `/sdcard` 守卫）。本次拉微信 wxapkg 就是这么拉的。
- 要用 pwsh 做 `push`/`pull`（它不转路径）时注意：**pwsh 的工具安全守卫会拦截对 `/sdcard` 的 `rm`/`Remove-Item`**（报 `Remove-Item on system path '/sdcard' is blocked`），哪怕 `rm` 是写在 `adb shell "..."` 字符串里也拦，整条脚本不执行。所以优先用上面的 `exec-out | cat` 彻底不碰 `/sdcard`。

### 4.1.1 PowerShell 往 adb shell 传复杂命令：写成 .sh 推上去再跑
`adb shell "su -c '...'"` 里一旦出现 `$(...)`、`\$`、嵌套引号、正则，PowerShell / 设备 sh / su 三层转义几乎必出错（`syntax error: unexpected '('`，或 PowerShell 把 `\d+`、`\$` 当路径，被安全检查拦下）。**稳妥做法**：`[IO.File]::WriteAllText` 写一个 LF 结尾的 `.sh` → `adb push` 到 `/data/local/tmp/` → `su -c 'sh /data/local/tmp/x.sh'`。
另外 **`pkill -f "<关键字>"` 会把正在执行这条命令的 `su -c` shell 也杀掉**（它的命令行里也有这个关键字），表现是输出一个 `Terminated`，后面的命令都没执行。用 `kill $(pidof <进程名>)`。

### 4.1.2 从 /system 拉 APK、只反编译一个类
`adb pull /system_ext/priv-app/...apk` 报 Permission denied 时，先 `su -c 'cp ... /data/local/tmp/; chmod 644 ...'` 再 pull。反编译单个类不用全量跑 jadx：先在各 `classes*.dex` 里搜类名字符串定位是哪个 dex，再 `java -cp C:\Users\31297\.local\share\jadx\lib\jadx-1.5.6-all.jar jadx.cli.JadxCLI --single-class <全限定类名> -d out classesN.dex`，几十 MB 的 SystemUI 也是秒出（`~\.local\bin\jadx` 是 sh 脚本，Windows 下直接调 jar）。

### 4.1.3 改 `settings_ssaid.xml`（Android ID / SSAID）必须走 ABX（2026-10-18 实测）
- A12+ 的 `/data/system/users/0/settings_ssaid.xml` 是**二进制 ABX**（Android Binary XML，magic `41 42 58 00` = `ABX\0`，`od -An -tx1 <file> | head` 一眼鉴别）。**纯文本/Java-DOM 解析会静默失败**（读不出、写进去游戏/框架不认）。
- 正确往返：`/system/bin/abx2xml <abx> <txt>` 改完 `/system/bin/xml2abx <txt> <abx>`；两者都支持 `-` 走 stdin/stdout。改完 `chmod 600 + chown system:system + restorecon`。
- 改某包 SSAID 时**连 `defaultValue` 一起改**（只改 `value` 开机会被 default 回填）。往返不保证字节一致（字符串池重排）但语义完整、SettingsProvider 正常读。
- 实证：闭源 app `com.silverlab.app.deviceidchanger.free` 没 ABX 处理 → 在 A12+ 静默失效。自建 KSU WebUI 模块在 `桌面\逆向\ssaid-changer-ksu\`（A16 实测往返无损、重启持久化）。详见 `idv-reverse-resume/device-identity.md` 第 9.9 节。

### 4.1.4 adb push 本地路径：MSYS_NO_PATHCONV 下本地源要用 `C:/...` 盘符形式
`export MSYS_NO_PATHCONV=1` 解决的是**远端**设备路径被改写（见 4.1），但它会让**本地源路径** `/c/Users/...` 也原样传给 Windows 版 adb → `adb: error: cannot stat '/c/Users/...'`。解法：本地源路径写成 **`C:/Users/...`（盘符 + 正斜杠）**，远端 `/data/local/tmp/...` 保持不转，一条 `adb push` 两头都对。

### 4.1.5 NetEase/NeoX 游戏内嵌 CPython 砍了 `_ctypes`（进程内探针注意）
第五人格(NeoX)内嵌 CPython **3.11.6 没有 `_ctypes` 模块**，`import ctypes` 直接 `ModuleNotFoundError` 崩掉整段注入脚本。进程内探针要读系统属性别用 ctypes `__system_property_get`——改走游戏自己暴露的 Python 绑定（如 `unisdk.getPropStr(key)`）或直接读文件。读 root 真值：`unisdk.getPropStr('UNISDKUTILS_IS_DEVICEROOTED3')`（`'0'`=未root，native 现算），比 cat 那个一次性写死的 `unisdk_devices_infos_file.xml` 可靠。详见 `idv-reverse-resume/device-identity.md` 第 9.5-9.7。

### 4.2 IDA Pro 复用 `.i64` 数据库前，先清残留文件
如果上一次 IDA 分析中途被杀掉、留下了解包后的工作文件(`.so.id0` / `.so.id1` / `.so.nam` / `.so.til`)，下次打开对应的 `.i64` 会卡在"发现解压缩版本，是否还原"的确认框，命令行批处理模式的 `-A` 参数**不会自动跳过这个提示**，进程会一直挂着直到被外部杀掉。**打开前先删掉这四个残留文件**，就能正常打开。

### 4.3 SpiderMonkey/cocos2d-js 字节码 vs 加密壳，先鉴别再决定路线
同样是 cocos2d-js 引擎的游戏，`project.jsc` 可能是两种完全不同的东西，**开工前先看文件开头 4 个字节区分**：
- 如果是 `PK\x03\x04`(ZIP 头)：大概率是"XXTEA 加密的 ZIP 包，解密后是明文 JS"这种套路(用 native 符号 `xxtea_decrypt`/`jsb_set_xxtea_key` 能在 IDA 里直接找到硬编码 key)，静态分析路线可行，直接改明文 JS 重新加密回去就行
- 如果是别的 magic(比如 `2C C0 73 B9`)：是**真正的 SpiderMonkey XDR 字节码**，没有现成反编译工具，静态改字节码的工作量是"重写一个这个引擎专属的编译器"级别，不建议走这条路，优先用 3.4 的运行时注入技术绕过去

### 4.4 存档加密 key 可能就藏在打包器的模块哈希 ID 里
遇到过 DES/AES 加密的存档，一开始满世界找"哪个字符串像 key"，最后发现**key 本身就是 browserify/webpack 打包时给某个依赖模块分配的、看起来完全随机的哈希 ID**(混在几百个同样长相的模块哈希字符串里，人眼扫描根本分不出来)。如果人工翻找无果，**对所有长度符合 key 长度(比如 DES 8字节)的候选字符串做字典式暴力尝试**(逐个当 key 解密，检查解出来是不是合法 JSON)往往比继续人工分析更快出结果。

### 4.5 先鉴别引擎类型，再选工具链，别被文件名/历史假设带偏
`libil2cpp.so`/`global-metadata.dat` 存在 → 才是真 Unity il2cpp，上 Il2CppDumper。**同样是 native 库 + 打包字节码，也可能是 cocos2d-js/Cocos Creator**(特征：`libcocos2djs.so`，没有 `libil2cpp.so`)，这种情况 Il2CppDumper 完全用不上，静态分析要走"XXTEA/字节码解密找明文 JS"的路线(见 4.3)。**在"荒野日记"项目上吃过一次亏**：早期建的 skill 文件名/内容都假设是 il2cpp，跟着这个假设走了不少弯路，直到反编译 native 库才发现引擎判断错了。**开工前先花一分钟用 `adb shell find /data/app -iname "libil2cpp.so"` 或者直接看 APK 的 `lib/` 目录下有什么 .so，确认引擎类型再决定用哪套工具链**，不要凭包名/游戏类型/过去某次经验想当然。

## 五、PC 侧直接读目标进程内存（root，强烈推荐）

设备已 root，所以**不需要往目标进程里注入任何东西**，就能从 PC 侧只读验证内存偏移。
这比"改代码 → 重编译 → 推设备 → 跑起来看日志"的循环快一个数量级，
而且完全不动目标进程。工具：`逆向\_通用工具\procmem\devread.py`。

```python
import sys; sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
from devread import Mem, sh
m = Mem(pid)                 # 自动拉取最新 maps
m.fetch([addr1, addr2, ...]) # 批量取这些地址所在的页（做安全检查）
m.q(addr)  # u64    m.d(addr)  # u32    m.f(addr)  # float
```

### 5.1 必须做缺页防护——这是反作弊能观测到的行为

读 `/proc/<pid>/mem` 时，如果碰到**没有常驻的页**，内核会替目标进程把页faults回来。
这个行为是目标进程可观测的。所以读之前必须查 `/proc/<pid>/pagemap`：

```
每页 8 字节，偏移 = (vaddr >> 12) * 8
bit63 = present(常驻)    bit62 = swapped(被换到 zram)
```

**只读 bit63=1 的页**。`devread.py` 已经内建这个检查，遇到非常驻页会打印
`[跳过] 页 0x... 读它会触发缺页` 并跳过。

### 5.2 目标必须在**前台活跃**，否则读不到东西

Android 会冻结后台应用并把工作集换到 zram。实测：游戏切后台几十秒后，
连"每帧都要遍历的对象数组"那两页都变成 `swapped`，于是安全检查把所有读取全拒了，
现象是"突然什么都读不出来"，极易误判成偏移失效。

**反过来理解才是正确姿势**：目标前台活跃时工作集本来就常驻，
**此时读取零缺页、零风险**——那就是唯一正确的读取窗口。
所以流程是"让用户把 APP 切到前台 → 立刻读"，而不是"想办法绕过检查"。

判断是否前台：`cat /proc/<pid>/oom_score_adj`，前台是 `0`。

### 5.3 maps 必须每次重新拉，过期 maps 会造成"未映射"假象

目标运行中会不断新增/释放映射（实测 40 分钟内 maps 从 8053 行涨到 9649 行）。
如果用会话开始时抓的那份 maps 做地址合法性判断，**目标后来新分配区域里的地址会被
误判成"未映射"而拒读**。

这个坑非常隐蔽：表现是"一部分对象能读、一部分读不出来"，
看起来特别像"这些对象的偏移变了"，实际上偏移完全正确。
在第五人格那次排查里，它直接导致我一度以为"数组签名命中的不是正确的数组"。
`devread.py` 现在默认每次 `Mem(pid)` 都重新拉 maps。

### 5.4 Scudo 分配器的 PROT_NONE 区不是反作弊陷阱

Android 14+ 用 Scudo 做 native 堆。maps 里会看到大片 `---p` 的
`[anon:scudo:primary_reserve]`——那是**预留但未提交的虚拟地址空间**，正常现象，
不是绊线页。指向这种区域的指针，含义是"这个槽位已经死了/还没提交"，
目标自己的代码也不会去读。直接跳过即可，不用当成检测机制去研究。

真实堆数据在 `[anon:scudo:primary]`(小对象) / `[anon:scudo:secondary]`(大对象)，都是 `rw-p`。

### 5.5 批量读：打包成一个设备端脚本，只来回一次

逐个地址调 `adb shell` 的话，每次 100~300ms，几百页就是几分钟。
正确做法是把几百条 `dd` 拼成一个 `.sh`，`adb push` 上去跑一次，输出重定向到一个文件，
再 `adb pull` 回来按页切分：

```sh
dd if=/proc/<pid>/mem bs=4096 skip=<页号> count=1 2>/dev/null   # 每页一行，追加到同一个输出
```

用 `bs=4096 skip=<页号>` 做页对齐读，**不要用 `bs=1 skip=<字节地址>`**——
那会让 dd 逐字节读到偏移位置，慢到不可用。

### 5.6 Windows 上 adb 拉不动含中文的本地路径

`adb pull <设备路径> <含中文的本地路径>` 会**静默失败**：命令不报错，但文件根本没生成，
下游代码报 `FileNotFoundError`，看起来像是程序逻辑 bug。
所有 adb 中转文件走纯 ASCII 临时目录（`devread.py` 用 `%TEMP%\procmem_tmp`），
脚本本身放中文目录没问题。

## 六、通用方法论

- **APP"卡死不动"先分清是 JS/逻辑卡住还是原生死锁**（2026-10-14 荒野日记）：`top -H -p <pid>` 看 CPU（死循环会占满一个核，死锁是 0%）；logcat 看 JS 线程的 tid 最后一行日志在哪；然后 root 下 `su -c 'debuggerd -b <pid>'` 一次拿到全部线程的原生栈（不杀进程），直接看渲染/JS 线程停在哪个 futex 上、跟谁在抢锁。那次 JS 层静态分析、模拟了一整天都没找到原因，抓一次栈就看出是 cocos `AudioEngine::stop` 销毁刚建的 `UrlAudioPlayer` 时和 OpenSL ALooper 的 prefetch 回调互锁（logcat 特征 `libOpenSLES ... locked by pthread`）。**cocos2d-x 游戏里"刚 play 就 stop"同一首长音频是已知会死锁的模式**
- **能动态验证就不要死磕静态分析**：字节码/字符串表能告诉你"有哪些函数、大概是干什么的"，但具体参数、具体触发条件、具体公式，靠运行时直接查询/hook 往往比純静态推断快一个数量级，尤其是配合 3.4 的注入技术之后
- **多个值同时异常时，先查它们之间有没有因果依赖，别当成多处独立失效**：在第五人格那次，面板上"矩阵地址/数组地址/矩阵偏移"三个值同时为 0，看起来是三处全废；实际上扫描循环的退出条件是"矩阵和数组都命中"，矩阵没命中就出不了循环，后面给数组地址赋值那行**压根没执行到**。真正坏的只有一处。**先读一遍代码确认数据流，再下"坏了几处"的结论。**
- **让用户提供可控的 ground truth，比自己猜数值范围强得多**：需要在内存里认出某个字段时，与其扫"哪些值看起来像合理坐标"，不如请用户把场景固定下来并说明真实情况（"我是小丑，四个人机是心理学家/邮差/佣兵/调香师，都不动"）。有了确切的真值和数量，就能用"某字段==某值的对象个数是否等于实际人数"这种**硬校验**一次锁定，而不是靠像不像。差分实验同理：让用户只改变一个变量（只动自己、只转视角），变的那部分就是目标字段。
- **别只给指针合法性判断卡下界**：`p > 0x5000000000` 这种单边判断会让浮点垃圾（实测 `0x400674954293DF`）也被当成合法指针，制造出一堆"看起来能走通"的假候选。要同时卡上界（本机用户态指针在 `0x77xx/0x79xx` 段，`< 0x8000000000`），并且尽量**用"整条链都走得通"做校验**，而不是只看单跳。
- **修偏移时优先改成自愈式，不要把旧常量换成新常量**：如果发现某个写死的偏移从 `+0x430` 变成了 `+0x440`，先看看它周围是不是一组等间隔的同类项（那次是三个间隔 `0x88` 的指针，三个都能走通）。是的话说明整体位移过，写死新值下次照样废。改成"在窗口内扫，用能否走通后续链路做校验"，这一类失效以后就自己吸收了。有数学关系可用时（比如相机世界坐标能从 VP 矩阵反解出来），用它当校验器去挑字段，比任何硬编码都稳。
- **观测到"数值不对/行为诡异"时，第一反应排查环境是否被污染**(见 3.7)、或者"是不是有人在操作设备"(自己的测试 vs 用户的正常操作叠在一起，很容易互相掩盖，导致误判)。不要在没有做"控制变量"的对照实验之前，就急着下"这是游戏机制"这种结论
- **对照实验要带"阳性对照"**（2026-09-30 荒野日记）：改写请求参数后得到"没效果"，先要证明改写这条路本身是通的，否则无法区分"服务器真的不给"和"改写没被识别"。那次的做法是：只留图纸 → 0 张；只留 `script` → 2/2 次都出 → 证明服务器确实读了改写后的参数，前者结论才可信。**阴性结果之前先准备好一个预期必然有反应的对照组**；样本少的组（只抽了 1 次）不要拿来下结论
- **推断被数据否定时，直接说"我原来的推断错了"**，别把原假设改头换面继续保留。那次先推断"天赋挤占奖池导致不出图纸"，对照实验把天赋全去掉照样 0 张，就明确推翻并记进项目 SKILL 的排除表
- **在配置表里找东西按 ID/结构遍历，别按名字关键词搜**：按"图纸"两个字搜 shop 表，漏掉了名字叫"配方：xxx""种植法：xxx"的同类商品，还误下了"表里没有"的结论。先确定编号范围，再按 `ID` 字段全量列出
- **给用户的方案如果依赖 Frida 常驻连接才能维持效果，要在第一句话说清楚**"能不能断开/关窗口"，不要等用户自己发现"怎么又失效了"
- **改完东西要截图或读日志确认，不要假设"应该生效了"**——运行时环境的很多问题(缓冲区被冲、对象被替换、多进程打架)光看代码逻辑是发现不了的，必须实际验证
- **每个项目的 SKILL.md 放在该项目自己的文件夹最外层**(比如 `逆向\物种起源_1.3.3\SKILL.md`、`逆向\荒野日记：孤岛_1.8.9.0\SKILL.md`)，不要堆在 `逆向\` 根目录当散文件(比如曾经的 `SKILL_new.md`)，否则文件一多很难找。跨项目通用的工具二进制(frida-server、Il2CppDumper 等)放 `逆向\_通用工具\`。**项目文件夹内部按用途分子目录**(`scripts\`/`ida_analysis\`/`patch_deploy\`/`device_dumps\`/`screenshots\`)，中间迭代产物(比如反复 patch 试错留下的几十个 `xxx_patchedN.jsc`)只保留最新验证生效的一份，其余定期清掉，别让磁盘和目录膨胀到"找不到东西"

## 七、更新规范

当用户说"更新一下工具链笔记""记录一下这次踩的环境坑"时，修改本文件：

- 新的工具路径/版本 → 补充到第一节
- 新的 Frida/adb/IDA/内存读取环境坑 → 追加到第三、四、五节，写清楚现象和排查方法，不只是结论
- 新的通用方法论教训 → 追加到第六节
- **具体某个游戏/APP 的业务逻辑发现(存档格式、内存偏移、函数名、破解方案)不要往这里塞**，那些属于对应项目自己的 SKILL.md(比如物种起源的在 `C:\Users\31297\Desktop\逆向\物种起源_1.3.3\SKILL.md`，荒野日记的在 `C:\Users\31297\Desktop\逆向\荒野日记：孤岛_1.8.9.0\SKILL.md`)
