# -*- coding: utf-8 -*-
"""模拟器内核：无引擎跑本地对局世界（客户端 + MODE_CS 本地服务端）。
    core = SimCore(); w = core.make_world(WorldCls, scene_id, self_pid); core.run(frames)
游戏原本靠引擎/加载界面/相机推进的几处生命周期节点，这里按真机顺序补上（见 _on_game_start）。"""
import sys, os, traceback, collections, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simboot, simenv

DT_MS = 33.333

# 纯视觉组件：整类替换成记录型空对象（构造即返回桩，所有调用都是空操作）
VISUAL = [("core.FogManager", "FogManager"), ("core.CorrManager", "CorrManager"),
          ("core.WeatherManager", "WeatherManager"), ("core.WeatherParticleManager", "WeatherParticleManager"),
          ("core.OutlineManager", "OutlineManager"), ("core.PostProcessManager", "PostProcessManager"),
          ("core.DissolveManager", "DissolveManager"), ("core.SunFlareMgr", "SunFlareMgr"),
          ("core.VegetationManager", "VegetationManager"), ("core.sound.SceneMusicMgr", "SceneMusicMgr"),
          ("core.TransparentManager", "TransparentManager"), ("core.ChangeDiffuseManager", "ChangeDiffuseManager"),
          ("core.ColorBindLessMgr", "ColorBindLessMgr"), ("core.SfxManager", "SFXManager")]


class SimCore(object):
    def __init__(self, verbose=True, server_ai=False):
        self.verbose = verbose
        self.GK = GK = simboot.boot(verbose)
        import game3d, math3d, simpatch
        self.game3d, self.math3d, self.simpatch = game3d, math3d, simpatch
        nulled = []
        for mod, cls in VISUAL:
            try:
                m = importlib.import_module(mod)
                if hasattr(m, cls):
                    setattr(m, cls, simenv.Stub(mod + "." + cls)); nulled.append(cls)
            except Exception:
                pass
        bad = [x for x in simpatch.apply() if x[3] != "ok"]
        self.real_time = simpatch.install_clock()   # 之后 time.time() 是模拟时间；墙钟用 real_time()
        simpatch.install_traceback_capture(echo=verbose)
        self._log("[core] 视觉组件置空 %d 个；表现层补丁%s" % (len(nulled), " 异常: %r" % bad if bad else "全部生效"))

        for k in dir(GK):
            if not k.startswith("__") and getattr(GK, k) is None:
                setattr(GK, k, simenv.Stub("GK." + k))
        from core.AsyncManager import AsyncManager
        GK.g_async_mgr = AsyncManager()
        GK.g_world_mgr = _make_world_mgr()
        GK.g_jank_mgr = simenv.Stub("GK.g_jank_mgr")  # GK 上本来没有这个属性（不是 None），init_after_loading 要用
        self.world = None
        self.started = False
        self.tick_errors = collections.Counter()
        self.on_start = []          # 开局回调：fn(world)
        self.server_ai = install_server_ai_island(self._log) if server_ai else None

    def _log(self, s):
        if self.verbose: print(s)

    # ---- 世界生命周期 ----
    def make_world(self, world_cls, scene_id, self_pid, world_type=None, **info):
        GK = self.GK
        w = world_cls()
        # 开局环绕镜头(start_init_view)靠相机每帧推进到时长后回调开战；模拟器不跑相机，用游戏自带的 skip_opening 直接回调。
        # 不跳过则相机停在 ROTATE_Y_MODE，WorldBattleBase.game_tick 在 unit_mgr.tick 之前就 return
        w.skip_opening = True
        GK.g_world_mgr.cur_world = GK.g_world_mgr.battle_world = w
        if world_type is None:
            world_type = w.world_type
        info_dict = dict(scene_id=scene_id, guuid="sim%04d" % scene_id, world_type=world_type, player_id=self_pid, **info)
        w.set_info({"info_dict": info_dict, "scene_id": scene_id, "world_type": world_type})
        w.init_scene(dict(info_dict))
        self.world = w
        return w

    def _on_game_start(self, w):
        GK = self.GK
        # 真机由加载界面结束回调触发（WorldManager.change_world_extra_load*）；不调则 WorldBattleBase.game_tick 第一句就 return
        w.init_after_loading()
        # game_tick 里 `if not GK.input: return False`。建单位阶段必须保持假：
        # 真机那时输入还没建，ItemBase._get_item_ability 的 fix_item_pos 分支走不到（走到会读不存在的 have_fix_item_pos）
        GK.input = simenv.TStub("GK.input")
        for fn in self.on_start:
            fn(w)
        self.started = True

    def frame(self):
        """推进一帧：到期回调 → 世界 tick（加载期是 loading_tick，之后切成 game_tick）。"""
        import time as _t
        w = self.world
        self.game3d.advance(DT_MS)
        self.GK.g_world_mgr.now = _t.time()
        if not self.started and getattr(getattr(w, "tick", None), "__name__", "") == "game_tick":
            self._on_game_start(w)
        try:
            w.tick()
        except Exception:
            key = traceback.format_exc().strip().splitlines()[-1]
            if not self.tick_errors[key] and self.verbose:
                print("[tick 异常 @帧%d] %s" % (self.game3d.frame_id(), "".join(traceback.format_exc(limit=-6).splitlines(True)[-14:])))
            self.tick_errors[key] += 1

    def run(self, frames, every=None, cb=None):
        t0 = self.real_time()
        for i in range(frames):
            self.frame()
            if every and cb and i % every == 0:
                cb(i)
        wall = self.real_time() - t0
        sim = frames * DT_MS / 1000.0
        self._log("== 墙钟 %.2fs 跑了模拟 %.1fs（%.1f 倍速）" % (wall, sim, sim / max(wall, 1e-6)))

    # ---- 观测 ----
    def characters(self):
        um = self.world.unit_mgr
        return [u for u in um.units.values() if getattr(u, "is_civilian", False) or getattr(u, "is_butcher", False)]

    def report(self, top=25):
        g = self.game3d
        print("== 被吞异常 %d 种:" % len(self.simpatch.SWALLOWED))
        for k, n in self.simpatch.SWALLOWED.most_common(12):
            print("  %5d  %s" % (n, k[:200]))
        print("== tick 异常 %d 种:" % len(self.tick_errors), [(k[:160], n) for k, n in self.tick_errors.most_common(6)])
        seen = collections.Counter(e.strip().splitlines()[-1] for e in g.ERRORS)
        print("== game3d 回调错误 %d 条:" % len(g.ERRORS), seen.most_common(6))
        print("== 模拟时间 %.1fs 帧 %d  待执行回调 %d" % (g.now_ms() / 1000, g.frame_id(), g.pending()))
        print("== math3d 缺失:", sorted(self.math3d.MISSING.items(), key=lambda x: -x[1])[:20])
        import physx_collision
        print("== 碰撞查询:", dict(physx_collision.QUERIES), " 其中命中:", dict(physx_collision.QUERY_HITS))
        print("== 碰撞形状未登记（查询未命中 / 动态体没放进世界）:", dict(physx_collision.UNSUPPORTED))
        print("== scn_col 载入:", physx_collision.LOADED, " 静态过滤属性来源:", physx_collision.STATIC_SOURCE[0])
        for name, samples in sorted(physx_collision.QUERY_SAMPLES.items()):
            print("   [%s]" % name)
            for where, args in samples:
                print("      %s  %r" % (where, args))
        import detour
        print("== 导航载入:", detour.LOADED)
        print("== 导航查询:", dict(detour.QUERIES), " 回退到 AI 导航:", dict(detour.FALLBACK),
              " 终点不可达(部分路径):", dict(detour.PARTIAL), " 推断/空操作:", dict(detour.UNIMPL))
        simenv.report(top)


class _ServerModeDevConfig(object):
    """给 AI 模块用的 dev_config：只把 SERVER_MODE 换成 True，其余属性实时转发给真 dev_config（不做快照，免得之后改的值看不到）。"""
    def __init__(self, real):
        object.__setattr__(self, "_real", real)

    def __getattr__(self, n):
        return True if n == "SERVER_MODE" else getattr(self._real, n)

    def __setattr__(self, n, v):
        setattr(self._real, n, v)


def install_server_ai_island(log=print):
    """服务端模式 AI 孤岛（SKILL §9.9）：人机 AI 的完整逻辑只在 SERVER_MODE 下开启，且 AI 模块都是调用时读 dev_config.SERVER_MODE。
    做法同 exp_servermode.py：servercommon.Netease 指向 GK → 清掉已加载的 common_cs.ai.* → SERVER_MODE=True 下全量重导入（bt_code 除外）
    → 恢复 False → 给这些模块换成 SERVER_MODE 恒为 True 的 dev_config 代理。必须在导入 worlds.WorldBattleClientBase（带进旧 AICommonTrigger）之前做。
    不填任何服务端专有成员的占位值；缺什么由运行期报错暴露，逐条按调用处推断后补进 sim1v4.ServerRoomShim。"""
    import types, game_kernel
    from etc import dev_config
    stale = [m for m in ("worlds.WorldBattleClientBase", "worlds.WorldBattleBase") if m in sys.modules]
    sc = types.ModuleType("servercommon"); sc.Netease = game_kernel; sc.__path__ = []
    simenv.REAL["servercommon"] = sc
    for m in [m for m in sys.modules if m == "common_cs.ai" or m.startswith("common_cs.ai.")]:
        del sys.modules[m]
    root = os.path.join(simenv.ROOT, "common_cs", "ai")
    ok, bad = 0, collections.Counter()
    dev_config.SERVER_MODE = True
    try:
        for dp, dn, fn in os.walk(root):
            if "bt_code" in dp:
                continue
            for f in sorted(fn):
                if not f.endswith(".pyc"):
                    continue
                rel = os.path.relpath(os.path.join(dp, f), simenv.ROOT)[:-4].replace(os.sep, ".")
                if rel.endswith(".__init__"):
                    rel = rel[:-9]
                try:
                    importlib.import_module(rel); ok += 1
                except Exception as e:
                    bad["%s: %s" % (type(e).__name__, str(e)[:100])] += 1
    finally:
        dev_config.SERVER_MODE = False
    proxy = _ServerModeDevConfig(dev_config)
    proxied = 0
    for name, m in list(sys.modules.items()):
        if (name == "common_cs.ai" or name.startswith("common_cs.ai.")) and getattr(m, "dev_config", None) is dev_config:
            m.dev_config = proxy; proxied += 1
    info = {"imported": ok, "failed": dict(bad), "proxied": proxied, "stale": stale}
    log("[core] 服务端 AI 孤岛：导入 %d 个模块，失败 %d（%s），装代理 %d 个%s" % (
        ok, sum(bad.values()), "; ".join("%s ×%d" % kv for kv in bad.most_common(3)) or "无", proxied,
        "；⚠ 已提前加载 %s，其中引用的仍是旧 AI 类" % stale if stale else ""))
    return info


def _make_world_mgr():
    from worlds.WorldManager import WorldManager

    class SimWorldMgr(WorldManager):
        """用游戏真正的 WorldManager 方法（is_world_battle 等按当前世界算），只跳过它繁重的 __init__。"""
        def __init__(self):
            self.cur_world = None
            self.battle_world = None

        def __getattr__(self, n):
            if n.startswith("__"): raise AttributeError(n)
            simenv.ACCESS["GK.g_world_mgr." + n] += 1
            return simenv.Stub("GK.g_world_mgr." + n)
    return SimWorldMgr()
