# 007-free 动态分析 · 运行手册

> 2026-10-15 备好,**等设备回来即可开跑**。配套静态结论见 `..\SKILL.md`、skill `touch-inject-arbitration`。
> 环境细节(frida/adb/IDA 路径、坑)见 skill `android-re-toolkit`——本手册只写增量。

## 0. 当前阻塞(2026-10-15)
`adb devices` 两个 adb 都空列表 → **手机没插/adb 没连**,无法做任何动态。套件已就绪,接上设备从第 2 步开始。

## 1. 前置条件(缺一不可,决定能跑到哪一步)
| 条件 | 用途 | 缺了会怎样 |
|---|---|---|
| 设备连上 adb + Magisk root | 全部 | 无法开始 |
| frida-server 17.5.2 跑起来(`/data/local/tmp/frida-server`) | 全部 | 连不上 |
| **只测授权协议**:无需游戏、无需有效卡密 | `hook_boundary.js` 的网络/ioctl/prop | — |
| wuwa `.ko` 能 insmod(007 自装) | ioctl 触摸命令、驱动握手 | 驱动相关 ioctl 看不到;007 可能退化但授权线程仍在 |
| 第五人格在**前台**跑 + 007 连上游戏 | `hook_native.js` 的砸板/gate 决策 | 决策逻辑无输出(007 在 `libclient.so not found` 重试循环里空转) |
| 有效卡密 + 服务器可达 | 完整授权成功 → 下发 offset 程序 | 授权被 REJECT;但**请求构造在联网前发生,明文照样抓得到** |

> ★ 关键利好:**游戏没跑时 007 不会退出**,会卡在 BattleSnapshot 重连/等 `libclient.so` 的循环里(静态 SKILL §5 证据),所以 **attach 窗口是敞开的**,不怕来不及挂。授权请求一般开机即发,也会重试。

## 2. 启动 frida-server
```powershell
$adb = "C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe"
& $adb devices                        # 先确认设备在
& $adb shell "su -c 'pidof frida-server || (/data/local/tmp/frida-server > /data/local/tmp/fs.log 2>&1 &)'"
& $adb shell "su -c 'pidof frida-server'"   # 拿到 pid = 起来了
```

## 3. 把 007 跑起来(独立 root 可执行,不是 app)
```powershell
# 007 本体就是 007-free.sh(ELF)。推上去、改权限、后台跑
& $adb push "C:\Users\31297\Desktop\逆向\007\007-free.sh" /data/local/tmp/007bin
& $adb shell "su -c 'chmod 755 /data/local/tmp/007bin'"
& $adb shell "su -c 'cd /data/local/tmp; ./007bin > /data/local/tmp/007.log 2>&1 &'"
& $adb shell "su -c 'pidof 007bin'"   # ← 记下 PID
# 若秒退:看 007.log(多半是缺 .ko / 缺配置)。授权线程通常在退出前已发过请求,boundary 若没抓到就需让它常驻:
#   先不给游戏,让它卡在重试循环;或用 frida spawn(见 §5 备选)在 main 之前挂好。
```
> `.sh` 是伪装后缀,`chmod +x` 当 ELF 直接执行;**不要** `sh 007bin`。

## 4. 挂 hook(attach 模式,spawn 在本机必超时——android-re-toolkit §3.3)
```powershell
# 每轮前先杀干净残留 frida(§3.7)
Get-Process frida* -ErrorAction SilentlyContinue | Stop-Process -Force
$frida = "C:\Users\31297\AppData\Local\Programs\Python\Python313\Scripts\frida.exe"
$PID007 = <上一步的PID>

# A. 边界 hook —— 授权协议 + 驱动 ioctl(无需游戏)
& $frida -U -p $PID007 -l "C:\Users\31297\Desktop\逆向\007\dynamic\hook_boundary.js" -q -t 3600 *> "C:\Users\31297\Desktop\逆向\007\dynamic\boundary.log"

# B. 原生决策 hook —— 砸板/gate(需游戏在跑;且先按脚本注释用 IDA 填 ENTRIES 入口)
& $frida -U -p $PID007 -l "C:\Users\31297\Desktop\逆向\007\dynamic\hook_native.js" -q -t 3600 *> "C:\Users\31297\Desktop\逆向\007\dynamic\native.log"
```
`-t` 单位是**秒**(§3.1);放后台跑,日志落文件,报 `failed exit 255` = 被主动杀,正常。

## 5. 备选:spawn 模式(仅当 007 秒退、attach 来不及)
```powershell
# frida 对【裸可执行】的 spawn 可能和 app 包不同(§3.3 的超时是 app 包场景)。值得一试:
& $frida -U -f /data/local/tmp/007bin -l hook_boundary.js -q
# 若同样超时:退回 §3 让 007 卡在重试循环(不启动游戏)再 attach。
```

## 6. 预期产出 → 回答哪些问题
| 日志里看什么 | 回答(对应 SKILL) |
|---|---|
| `[connect] -> x.x.x.x:port` | **真实服务器端点**:是不是 `198.51.100.73:61077` 占位,还是运行时另有来源(§5.1 存疑点 1) |
| `[sendto]/[write]` 的 HEX/ASCII | 授权请求体(加密后);配合时序定位加密边界 |
| `[recvfrom]/[read]` | 服务器响应(可据此找解密点) |
| `[prop]` 读了哪些 `ro.*`/`persist.*` | **hwid 设备指纹的输入**(§10.3.3 hwid 派生) |
| `[ioctl] ...magic 'E'... _IOW(...)` + arg buf | **触摸注入的 `_IOW` 命令号 + 结构**(touch-inject-arbitration §3.3 未定位项);以及读内存的 `_IOR` 握手 |
| `[open] /proc/inte_ko` / config | 驱动节点 / 本地配置文件路径 |
| native.log 的 `finger-outside-gate` 命中时机 | **finger-outside-gate 的真实 polarity**(§2 存疑):看它在"真手指在键区内"还是"外"时被判 reject |

## 7. 下一步(拿到明文后)
1. 定位加密边界:`sendto` 看到的是密文,往回 hook mbedtls AES(或授权簇函数入口,IDA 现查)拿**明文 JSON** + **AES key 来源**(硬编码 `e097…` 还是 card/hwid 派生 → 钉死 §10.3.3)。
2. 解密响应 → 提取**下发的 offset 程序**(拿到 007 字段字典,反哺 IdentityV,§10.4)。
3. 反调试/反篡改先处理:TracerPid 检测 + 执行器自校验(SKILL §9)——attach 只读一般不触发写校验,但若 007 检测到 TracerPid 可能行为异常,留意 `007.log` 的异常退出。
