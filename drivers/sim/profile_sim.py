# -*- coding: utf-8 -*-
"""性能剖析：1v4（服务端模式 AI 孤岛）先不计时跑若干帧过开局，再用 cProfile 跑 N 帧，打印热点。
用法: python profile_sim.py [帧=300] [种子=0] [预热帧=60] [--out x.prof]
输出：自身耗时 Top、累计耗时 Top、按文件汇总（看时间落在 导航/碰撞/AI/动画 哪一层）。--out 存原始 pstats，可用 snakeviz 等看。"""
import sys, os, collections, cProfile, pstats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simcore
simcore.ensure_hashseed()
from simcore import SimCore

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
FRAMES = int(ARGS[0]) if len(ARGS) > 0 else 300
SEED = int(ARGS[1]) if len(ARGS) > 1 else 0
WARM = int(ARGS[2]) if len(ARGS) > 2 else 60
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None

core = SimCore(verbose=False, server_ai=True, seed=SEED)
import sim1v4
w = sim1v4.make_1v4(core)
core.run(WARM)   # 开局：init_after_loading、挂 AI、修机站位预计算都在前几十帧

prof = cProfile.Profile()
t0 = core.real_time()
prof.enable()
for _ in range(FRAMES):
    core.frame()
prof.disable()
wall = core.real_time() - t0
sim = FRAMES * simcore.DT_MS / 1000.0
print("== 剖析 %d 帧：墙钟 %.2fs，模拟 %.1fs（%.2f 倍速，开 cProfile 会偏慢 1.5~2 倍）；每帧 %.1f ms" % (
    FRAMES, wall, sim, sim / max(wall, 1e-6), wall * 1000 / FRAMES))
print("== tick 异常:", dict(core.tick_errors) or "无")
try:   # 多进程并行时按这个估每个进程占多少内存
    import psutil
    mi = psutil.Process().memory_info()
    print("== 进程内存：当前 %.0f MB，峰值 %.0f MB" % (mi.rss / 2**20, getattr(mi, "peak_wset", mi.rss) / 2**20))
except ImportError:
    pass

st = pstats.Stats(prof)
if OUT:
    st.dump_stats(OUT)
    print("== 原始数据:", OUT)


def short(path):
    p = path.replace("\\", "/")
    for mark in ("/drivers/sim/", "/std_pyc/"):
        if mark in p:
            return p.split(mark, 1)[1]
    return "/".join(p.split("/")[-2:])


def row(key, v):
    (fn, line, name), (cc, nc, tt, ct) = key, v[:4]
    return "%9d %8.2f %8.2f  %s:%d(%s)" % (nc, tt, ct, short(fn), line, name)


stats = st.stats
total = sum(v[2] for v in stats.values())
print("\n== 自身耗时 Top 40（调用次数 / 自身秒 / 累计秒；总自身时间 %.2fs）" % total)
for k, v in sorted(stats.items(), key=lambda kv: -kv[1][2])[:40]:
    print(row(k, v))
print("\n== 累计耗时 Top 40")
for k, v in sorted(stats.items(), key=lambda kv: -kv[1][3])[:40]:
    print(row(k, v))

by_file = collections.Counter()
for (fn, _, _), v in stats.items():
    by_file[short(fn)] += v[2]
print("\n== 按文件汇总自身耗时 Top 30")
for f, t in by_file.most_common(30):
    print("  %6.2fs %5.1f%%  %s" % (t, 100 * t / max(total, 1e-9), f))
