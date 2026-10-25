# 第五人格 PC 侧分析脚本

依赖 `C:\Users\31297\Desktop\逆向\_通用工具\procmem\devread.py`（通用内存读取器，自带缺页防护）。
**前提：设备已 root，游戏在前台运行。** 后台时工作集被换到 zram，读取会被安全检查拒绝。

## 主力工具

### `idv_probe.py` —— 游戏更新后第一个该跑的东西

自发现 pid / libbase / bss 段 / 两个签名位置，把整条链走一遍并打分。
不需要改代码、不需要重编译。

```powershell
$py = "C:\Users\31297\AppData\Local\Programs\Python\Python313\python.exe"
& $py idv_probe.py quick       # 只验矩阵链和相机，几秒
& $py idv_probe.py             # 全量，额外列对象表和五人定位
& $py idv_probe.py --redump    # 强制重新 dump bss（默认复用本地缓存）
```

输出怎么判读见 `idv-reverse-resume` skill 的"第零步"。一句话版本：

- 矩阵签名命中 0 处 → 引擎大改，得上活体扫描
- 签名命中但可用槽位 0 个 → 签名到根指针那一跳废了，放宽窗口重扫
- `+0x1a0==450` 的对象数 == 本局实际人数 → 对象结构体完好

## 历史脚本（2026-09-17 那次排查的过程产物，保留作参考）

这些脚本**硬编码了当时的 pid(17226) 和 libbase**，直接跑会失败，
要用的话改文件头的常量。功能都已经并进 `idv_probe.py`，一般不用碰。

| 脚本 | 当时用来干什么 |
|---|---|
| `arrcand.py` | 枚举 bss 里所有满足数组签名的候选，逐个用活体数据判分（确认只有 1 个候选，排除"选错数组"的怀疑） |
| `objlist.py` | 列出全部可读对象的坐标/字段/类名，并落盘 `snap_*.json` 供差分 |
| `final.py` | 五人定位 + 以监管者坐标为基准搜索相机字段 |
| `cam_verify.py` | 同一次读取里同时取 VP 矩阵和候选相机三连，验证"从矩阵反解相机坐标"这条路 |
| `recheck.py` | 局内重新解析矩阵链 + 按 `+0x1a0` 筛玩家 |
| `probe.py` | pagemap 常驻状态连续采样 + 矩阵是否实时更新 + 设备内存压力 |
| `field_finger.py` | **不依赖活体进程**：对旧版 `captures/dump_frame_objs.bin` 做"字段指纹"分析，按值分布反推结构体偏移（指针列/双值列/常量列）。如果哪天类名链也断了、没有 ground truth 了，用这个从帧 dump 里盲推偏移 |

`field_finger.py` 是唯一一个离线可用的，它在旧版存档数据上验证过能自动复现已知的
`+0x20/+0x28/+0x30/+0xf8` 指针偏移和 `+0x70` 状态位。
