# -*- coding: utf-8 -*-
# probe2: 一次性按路径从游戏资源系统取出【模拟器要用的全部地图几何】，可选采集引擎碰撞真值。
#   阶段 A  按 scene_config / 离线清单 / 派生规则 收集路径并取文件（.scn .scn_col .col_mesh .col .nav .postprocess 及碰撞 .gim）
#   阶段 B  解析每个 .nav(Detour MSET) 里列出的 .tile，按候选目录取全部分块
#   阶段 C  解析 .scn 场景描述里引用的上述类型文件，补取
#   ---- 关闭 zip，写 files_done（之后即使崩溃，文件也已落盘）----
#   阶段 D  若当前在对局里：对静态场景碰撞/全碰撞打射线，记录 (起点,终点)->结果，作为模拟器碰撞的校验真值
#   阶段 E  记录 C_file / 场景碰撞对象 / 碰撞管理器 的接口清单
# 后台线程跑，命令本身立即返回。进度: resdump/progress.json；日志: resdump/log.txt
import os, json, time, re, threading, traceback

OUT = globals().get("RESDUMP_OUT", "/sdcard/Android/data/com.netease.dwrg/files/resdump")
RAY_BUDGET_SEC = globals().get("RESDUMP_RAY_BUDGET", 150)
KEEP_EXT = ("scn", "scn_col", "col_mesh", "col", "nav", "tile", "postprocess")
PATH_RE = re.compile(r"^[A-Za-z0-9_./\\\-]+\.([A-Za-z0-9_]{1,12})$")
EXPLICIT = json.loads(r'''__EXPLICIT_JSON__''')
COMMON = ["scene/scene_battle/common_col_mesh/nav/grocer_door.col_mesh"]

_state = {"stage": "init", "t0": time.time(), "got": 0, "miss": 0, "bytes": 0, "tiles": 0, "rays": 0, "err": 0}


def _write_progress():
    try:
        _state["elapsed"] = round(time.time() - _state["t0"], 1)
        with open(OUT + "/progress.json", "w") as f:
            json.dump(_state, f)
    except Exception:
        pass


class Dumper:
    def __init__(self):
        os.makedirs(OUT, exist_ok=True)
        self.log = open(OUT + "/log.txt", "w", encoding="utf-8")
        self.manifest = open(OUT + "/manifest.jsonl", "w", encoding="utf-8")
        self.missf = open(OUT + "/miss.jsonl", "w", encoding="utf-8")
        self.got = {}       # 规范路径 -> (md5, size)
        self.data = {}      # 规范路径 -> bytes（只留 .nav/.scn 供后续解析）
        self.missed = set()
        try:
            import hashlib
            self.md5 = lambda b: hashlib.md5(b).hexdigest()
        except Exception:
            self.md5 = lambda b: ""
        self.zf = None
        try:
            import zipfile
            self.zf = zipfile.ZipFile(OUT + "/res.zip", "w", zipfile.ZIP_STORED, allowZip64=True)
        except Exception as e:
            self.L("zipfile 不可用，改为散文件: %r" % e)
        import C_file
        self.C = C_file
        self.n_calls = 0

    def L(self, s):
        self.log.write("[%.1f] %s\n" % (time.time() - _state["t0"], s))
        self.log.flush()

    @staticmethod
    def norm(p):
        return p.strip().replace("\\", "/")

    def _read(self, p):
        for v in (p, p.replace("\\", "/"), p.replace("/", "\\")):
            try:
                b = self.C.get_res_file(v, "")
            except Exception:
                b = None
            self.n_calls += 1
            if self.n_calls % 40 == 0:
                time.sleep(0.002)          # 让出 GIL，别卡游戏主线程
            if b:
                if isinstance(b, str):
                    b = b.encode("utf-8", "surrogateescape")
                return v, b
        return None, None

    def fetch(self, p, src, keep=False):
        n = self.norm(p)
        if not n or n in self.missed:
            return None
        if n in self.got:
            return self.data.get(n, b"")   # 已取过：返回非 None，调用方据此判断"存在"
        used, b = self._read(p)
        if b is None:
            self.missed.add(n)
            _state["miss"] += 1
            self.missf.write(json.dumps({"path": n, "src": src}, ensure_ascii=False) + "\n")
            return None
        h = self.md5(b)
        self.got[n] = (h, len(b))
        _state["got"] += 1
        _state["bytes"] += len(b)
        if self.zf is not None:
            self.zf.writestr(n, b)
        else:
            fp = os.path.join(OUT, "files", n)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "wb") as f:
                f.write(b)
        self.manifest.write(json.dumps({"path": n, "used": used, "size": len(b), "md5": h, "src": src}, ensure_ascii=False) + "\n")
        if keep or n.endswith((".nav", ".scn")):
            self.data[n] = b
        if _state["got"] % 50 == 0:
            self.manifest.flush(); _write_progress()
        return b


def _paths_in(v):
    out = []
    if isinstance(v, str):
        for part in v.split(","):
            s = part.strip()
            m = PATH_RE.match(s)
            if m and ("/" in s or "\\" in s):
                out.append((s, m.group(1).lower()))
    elif isinstance(v, (list, tuple, set, frozenset)):
        for x in v:
            out += _paths_in(x)
    elif isinstance(v, dict):
        for x in v.values():
            out += _paths_in(x)
    return out


def phase_a(D):
    _state["stage"] = "A_scene_config"; _write_progress()
    targets = []
    sc = GK.DM.scene_config
    navs = set()
    for sid in sorted(sc):
        cfg = sc[sid]
        for k, v in cfg.items():
            for p, ext in _paths_in(v):
                if ext in KEEP_EXT or (ext == "gim" and ("col" in k.lower() or "_col" in p.lower()
                                                         or k.lower().endswith("model_path"))):
                    targets.append((p, "sc:%s:%s" % (sid, k)))
                    if ext == "nav":
                        navs.add(p)
                    if ext == "scn_col":
                        targets.append((p[:-8] + ".col_mesh", "derive:col_mesh"))
                        targets.append((p[:-8] + "_dev.col_mesh", "derive:dev_col_mesh"))
        try:
            from common_tools import utils
            cp = utils.get_scene_col_path(sid)
            if cp:
                targets.append((cp, "utils.get_scene_col_path:%s" % sid))
                targets.append((cp.replace(".scn_col", ".col_mesh"), "derive:col_mesh"))
                targets.append((cp.replace(".scn_col", "_dev.col_mesh"), "derive:dev_col_mesh"))
        except Exception as e:
            pass
    for p in EXPLICIT:
        targets.append((p, "explicit"))
        if p.lower().endswith(".nav"):
            navs.add(p)
    for p in COMMON:
        targets.append((p, "common"))
    # 导航派生：ai_ / moveable_ 前缀（NavManager.load_scene_nav_mesh 里的命名约定）
    for nv in list(navs):
        n = D.norm(nv)
        d, base = n.rsplit("/", 1) if "/" in n else ("", n)
        for pre in ("ai_", "moveable_"):
            targets.append(((d + "/" if d else "") + pre + base, "derive:nav_" + pre))
    D.L("阶段A 目标 %d 条" % len(targets))
    for p, src in targets:
        D.fetch(p, src)
    D.L("阶段A 完成 got=%d miss=%d" % (_state["got"], _state["miss"]))


def phase_b(D):
    _state["stage"] = "B_nav_tiles"; _write_progress()
    report = {}
    for n, b in list(D.data.items()):
        if not n.endswith(".nav") or b[:4] != b"TESM":
            continue
        names = []
        # 块名是 [u32 长度][字符串]：从每个 ".tile" 结尾往回找满足长度前缀的起点
        for m in re.finditer(rb"\.tile", b):
            e = m.end()
            for L in range(6, 240):
                s0 = e - L
                if s0 < 4:
                    break
                if int.from_bytes(b[s0 - 4:s0], "little") == L:
                    raw = b[s0:e]
                    if all(32 < c < 127 for c in raw):
                        nm = raw.decode("latin1")
                        if nm not in names:
                            names.append(nm)
                        break
        d, base = n.rsplit("/", 1) if "/" in n else ("", n)
        stem = base[:-4]
        cands = [d, d + "/" + stem, d + "/" + stem + "_tile", d + "/" + stem + "_tiles", d + "/tile", d + "/tiles",
                 d + "/" + stem + "/tile", ""]
        chosen = None
        if names:
            for c in cands:
                if D.fetch((c + "/" if c else "") + names[0], "tile_probe:" + n) is not None:
                    chosen = c
                    break
        ok = 0
        if chosen is not None:
            for nm in names:
                if D.fetch((chosen + "/" if chosen else "") + nm, "tile:" + n) is not None:
                    ok += 1
        report[n] = {"tiles_listed": len(names), "dir": chosen, "ok": ok, "first": names[:3]}
        _state["tiles"] += ok
        D.L("nav %s: 列出 %d 块, 目录=%r, 取到 %d" % (n, len(names), chosen, ok))
    with open(OUT + "/nav_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)


def phase_c(D):
    _state["stage"] = "C_scn_refs"; _write_progress()
    seen = set()
    for rnd in range(3):
        new = 0
        for n, b in list(D.data.items()):
            if not n.endswith(".scn") or n in seen:
                continue
            seen.add(n)
            t = b.decode("utf-8", "replace")
            for m in re.finditer(r'"([^"<>\s]+\.([A-Za-z0-9_]{1,12}))"', t):
                p, ext = m.group(1), m.group(2).lower()
                if ext in KEEP_EXT and D.norm(p) not in D.got:
                    if D.fetch(p, "scn_ref:" + n) is not None:
                        new += 1
        D.L("阶段C 第%d轮 新增 %d" % (rnd, new))
        if not new:
            break


def _ser(r, depth=0):
    if depth > 3:
        return repr(r)[:80]
    if r is None or isinstance(r, (bool, int, float, str)):
        return r
    if isinstance(r, (list, tuple)):
        return [_ser(x, depth + 1) for x in r]
    try:
        return {"v3": [float(r.x), float(r.y), float(r.z)]}
    except Exception:
        pass
    out = {"type": type(r).__name__}
    for a in ("hit", "is_hit", "pos", "position", "hit_pos", "point", "normal", "hit_normal", "cid", "col_id",
              "dist", "distance", "fraction", "t", "unit_type", "group", "layer", "face"):
        try:
            v = getattr(r, a)
            if callable(v):
                continue
            out[a] = _ser(v, depth + 1)
        except Exception:
            pass
    if len(out) == 1:
        out["repr"] = repr(r)[:160]
    return out


def phase_d(D):
    _state["stage"] = "D_ray_truth"; _write_progress()
    w = S(lambda: GK.g_world_mgr.cur_world)
    cm = S(lambda: w.collision_mgr)
    sc = S(lambda: cm._scene_col)
    meta = {"world": type(w).__name__ if w is not None else None, "has_cm": cm is not None, "has_scene_col": sc is not None}
    if cm is None or sc is None:
        meta["skipped"] = "不在对局里(没有场景碰撞)"
        with open(OUT + "/raytruth_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        D.L("阶段D 跳过: %s" % meta["skipped"])
        return
    import math3d, random
    V = math3d.vector
    sid = S(lambda: w.scene_id)
    cfg = S(lambda: GK.DM.scene_config[sid], {}) or {}
    me = S(lambda: GK.g_unit)
    pp = S(lambda: me.get_position3()) or S(lambda: me.position)
    px, py, pz = (float(pp.x), float(pp.y), float(pp.z)) if pp is not None else (0.0, 0.0, 0.0)
    cen = cfg.get("scene_center") or (px, py, pz)
    meta.update({"scene_id": sid, "scene_center": list(cen), "player": [px, py, pz],
                 "server_col": cfg.get("server_col"), "scene_path": cfg.get("scene_path")})
    funcs = {}
    for name in ("hit_by_ray_new_with_scn_col", "hit_by_ray_new"):
        f = getattr(cm, name, None)
        if f is None:
            continue
        code = getattr(getattr(f, "__func__", f), "__code__", None)
        funcs[name] = f
        meta["sig_" + name] = {"args": list(code.co_varnames[:code.co_argcount]) if code else None,
                               "defaults": repr(getattr(getattr(f, "__func__", f), "__defaults__", None))}
    meta["flags"] = {k: S(lambda k=k: getattr(cm, k)) for k in (
        "use_smaller_capsule_size", "static_test_add_extra_size", "capsule_triangle_two_edges",
        "mesh_penetration_recalc_pen", "capsule_sweep_mesh_same_radius", "jump_height", "use_bullet")}
    meta["flags"] = {k: (v if isinstance(v, (int, float, bool, str, type(None))) else repr(v)) for k, v in meta["flags"].items()}
    with open(OUT + "/raytruth_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1, default=repr)
    if not funcs:
        D.L("阶段D 跳过: 碰撞管理器上没有射线函数")
        return
    out = open(OUT + "/raytruth.jsonl", "w", encoding="utf-8")

    def call(f, a, b):
        for extra in ((), (None,), (None, False)):
            try:
                return True, f(a, b, *extra)
            except TypeError:
                continue
            except Exception as e:
                return False, repr(e)[:120]
        return False, "TypeError"

    rng = random.Random(20261024)
    cx, cz = float(cen[0]), float(cen[2])
    R = 1300.0
    t_end = time.time() + RAY_BUDGET_SEC
    k = 0
    # 1) 竖直射线网格：得到地面/楼层高度场
    G = 96
    for i in range(G):
        for j in range(G):
            if time.time() > t_end:
                break
            x = cx - R + 2 * R * (i + 0.5) / G
            z = cz - R + 2 * R * (j + 0.5) / G
            a, b = V(x, py + 400.0, z), V(x, py - 300.0, z)
            for name, f in funcs.items():
                ok, r = call(f, a, b)
                out.write(json.dumps({"k": "v", "f": name, "a": [x, py + 400.0, z], "b": [x, py - 300.0, z],
                                      "ok": ok, "r": _ser(r)}, default=repr) + "\n")
            k += 1
            if k % 64 == 0:
                _state["rays"] = k; _write_progress(); time.sleep(0.003)
    # 2) 随机水平/斜射线：墙体与障碍
    while time.time() < t_end:
        x, z = rng.uniform(cx - R, cx + R), rng.uniform(cz - R, cz + R)
        h = py + rng.choice((3.0, 10.0, 25.0, 60.0))
        ang = rng.uniform(0, 6.2831853)
        L = rng.uniform(30.0, 400.0)
        import math
        x2, z2 = x + L * math.cos(ang), z + L * math.sin(ang)
        h2 = h + rng.uniform(-20.0, 20.0)
        a, b = V(x, h, z), V(x2, h2, z2)
        for name, f in funcs.items():
            ok, r = call(f, a, b)
            out.write(json.dumps({"k": "h", "f": name, "a": [x, h, z], "b": [x2, h2, z2], "ok": ok, "r": _ser(r)},
                                 default=repr) + "\n")
        k += 1
        if k % 64 == 0:
            _state["rays"] = k; _write_progress(); time.sleep(0.003)
    out.close()
    _state["rays"] = k
    D.L("阶段D 完成 射线 %d 条" % k)


def phase_e(D):
    _state["stage"] = "E_api_lists"; _write_progress()
    rep = {}
    rep["C_file"] = S(lambda: [a for a in dir(D.C) if not a.startswith("__")], [])
    w = S(lambda: GK.g_world_mgr.cur_world)
    cm = S(lambda: w.collision_mgr)
    rep["collision_mgr"] = S(lambda: [a for a in dir(cm) if not a.startswith("__")], [])
    sc = S(lambda: cm._scene_col)
    rep["scene_col_type"] = type(sc).__name__ if sc is not None else None
    rep["scene_col"] = S(lambda: [a for a in dir(sc) if not a.startswith("__")], [])
    try:
        import collision
        rep["collision_module"] = [a for a in dir(collision) if not a.startswith("__")]
    except Exception as e:
        rep["collision_module"] = repr(e)
    nm = S(lambda: w.nav_mgr)
    rep["nav_mgr"] = S(lambda: [a for a in dir(nm) if not a.startswith("__")], [])
    rep["world"] = type(w).__name__ if w is not None else None
    rep["scene_id"] = S(lambda: w.scene_id)
    with open(OUT + "/api_report.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=repr)


def _run():
    D = None
    try:
        D = Dumper()
        D.L("开始；get_res_file 样本类型=%s" % type(S(lambda: D.C.get_res_file(COMMON[0], ""))).__name__)
        for ph in (phase_a, phase_b, phase_c):
            try:
                ph(D)
            except Exception:
                _state["err"] += 1
                D.L("阶段异常 %s:\n%s" % (ph.__name__, traceback.format_exc()))
        if D.zf is not None:
            D.zf.close()
        D.manifest.close(); D.missf.close()
        _state["stage"] = "files_done"; _write_progress()
        D.L("文件阶段结束 got=%d miss=%d bytes=%d tiles=%d" % (_state["got"], _state["miss"], _state["bytes"], _state["tiles"]))
        for ph in (phase_e, phase_d):
            try:
                ph(D)
            except Exception:
                _state["err"] += 1
                D.L("阶段异常 %s:\n%s" % (ph.__name__, traceback.format_exc()))
        _state["stage"] = "done"; _write_progress()
        D.L("全部完成")
    except Exception:
        _state["stage"] = "fatal"; _state["fatal"] = traceback.format_exc()[-1500:]
        _write_progress()


if globals().get("RESDUMP_SYNC"):
    _run()
else:
    threading.Thread(target=_run, name="resdump", daemon=True).start()
    P("resdump 已在后台启动 -> %s (看 progress.json)" % OUT)
