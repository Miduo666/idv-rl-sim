# -*- coding: utf-8 -*-
# probe2 命令(2026-09-25)：找"别人身上每帧自己变的治疗进度字段"。由 healscan.ps1 投递，**必须在有人正在治疗/自愈时跑**。
# 做法：数值属性全量快照 3 次(间隔 GAP 秒)，找匀速变化的量，按下面两条打分：
#   速率 ≈ 治疗速度(0~100 量纲) 或 ≈ 速度/上限(0~1 量纲)
#   数值 ≈ 用 debug_record_cured_info 外推出的当前进度
# 搜索范围：求生者(深 4，够到 combat_unit.components[k].x)、监管(深 3)、其它所有单位(深 1)、g_ui_mgr.ui_dict(深 4)、GK 顶层(深 1)。
# 命令立刻返回，扫描在自己的 daemon 线程里跑。每次快照会占 GIL 一两百毫秒，游戏可能顿一下。
import sys, threading, types

OUTF = "/sdcard/Android/data/com.netease.dwrg/files/idv_healscan.txt"
GAP = 1.0
BUDGET = 120000          # 每次快照最多访问的节点数
SKIPT = (types.ModuleType, types.FunctionType, types.MethodType, types.BuiltinFunctionType, type)


def walk(root, name, maxd, out, seen, budget):
    stack = [(root, name, 0)]
    while stack:
        if budget[0] <= 0:
            out["__truncated__"] = 1
            return
        o, p, d = stack.pop()
        budget[0] -= 1
        if isinstance(o, bool) or o is None or isinstance(o, (str, bytes)):
            continue
        if isinstance(o, (int, float)):
            out[p] = o
            continue
        if d >= maxd or isinstance(o, SKIPT):
            continue
        oid = id(o)
        if oid in seen:
            continue
        seen.add(oid)
        try:
            if isinstance(o, dict):
                for k, v in list(o.items())[:400]:
                    stack.append((v, "%s[%s]" % (p, R(k, 30)), d + 1))
            elif isinstance(o, (list, tuple)):
                for i, v in enumerate(list(o)[:80]):
                    stack.append((v, "%s[%d]" % (p, i), d + 1))
            else:
                dd = idict(o)
                if dd:
                    for k, v in list(dd.items())[:2000]:
                        stack.append((v, "%s.%s" % (p, k), d + 1))
        except Exception:
            pass


def heals():
    """当前正在进行的治疗：[(uid, 速度, 上限, 外推进度)]"""
    hs = []
    ub = S(lambda: GK.unit_mgr.units_by_type) or {}
    for u in S(lambda: list(ub.get(2) or []), []) or []:
        d = idict(u)
        r = d.get("debug_record_cured_info")
        now = d.get("now")
        try:
            ts, lst, prog, spd, lim = r[0], list(r[1]), float(r[2]), float(r[3]), float(r[4])
        except Exception:
            continue
        if lst and spd and isinstance(now, (int, float)):
            hs.append((d.get("uid"), spd, lim, min(prog + spd * (now - ts), lim), lst))
    return hs


def snap():
    # 每组单独预算，免得求生者那组(深 3，会顺着 room/world 扩出去)把后面几组饿死
    out, seen, used = {}, set(), 0
    ub = S(lambda: GK.unit_mgr.units_by_type) or {}
    b = [BUDGET // 2]
    for u in S(lambda: list(ub.get(2) or []), []) or []:
        walk(u, "U2:%s" % idict(u).get("uid"), 4, out, seen, b)
    used += BUDGET // 2 - b[0]
    b = [BUDGET // 8]
    for u in S(lambda: list(ub.get(1) or []), []) or []:
        walk(u, "U1:%s" % idict(u).get("uid"), 3, out, seen, b)
    used += BUDGET // 8 - b[0]
    b = [BUDGET // 8]
    for t in S(lambda: sorted(k for k in ub.keys() if isinstance(k, int) and k not in (1, 2)), []) or []:
        for i, u in enumerate(S(lambda: list(ub.get(t) or []), []) or []):
            walk(u, "U%d#%d(%s)" % (t, i, cname(u)), 1, out, seen, b)
    used += BUDGET // 8 - b[0]
    b = [BUDGET // 8]
    walk(S(lambda: GK.g_ui_mgr.ui_dict) or {}, "UI", 4, out, seen, b)
    used += BUDGET // 8 - b[0]
    b = [BUDGET // 8]
    for k, v in list(vars(GK).items()):
        if k.startswith("g_") and k != "g_ui_mgr":
            walk(v, "GK." + k, 1, out, seen, b)
    used += BUDGET // 8 - b[0]
    return out, used


def run(st):
    lines = []
    L = lines.append
    try:
        shots = []
        for i in range(3):
            t0 = time.time()
            s, nodes = snap()
            cost = time.time() - t0
            shots.append((time.time(), s, heals()))
            L("快照%d 节点 %d 数值 %d 耗时 %.0fms%s" % (i, nodes, len(s), cost * 1000, " (被预算截断)" if "__truncated__" in s else ""))
            if i < 2:
                time.sleep(GAP)
        (ta, a, _), (tb, b, _), (tc, c, hc) = shots
        L("正在进行的治疗(第3次快照): %s" % ([(u, round(sp, 3), lim, round(p, 2), ls) for u, sp, lim, p, ls in hc] or "无 —— 没人在治疗，结果没意义"))
        steady, hits = [], []
        for p, vc in c.items():
            if p not in a or p not in b:
                continue
            va, vb = a[p], b[p]
            r1, r2 = (vb - va) / (tb - ta), (vc - vb) / (tc - tb)
            if r1 == 0 or r2 == 0 or abs(r1 - r2) > 0.2 * max(abs(r1), abs(r2)):
                continue
            r = (r1 + r2) / 2
            if abs(vc) > 5000:            # 时间戳/帧号之类
                continue
            steady.append((p, va, vc, r))
            why = []
            for uid, sp, lim, prog, _ in hc:
                if abs(r - sp) <= 0.15 * sp:
                    why.append("速率≈%s的治疗速度%.3f" % (uid, sp))
                if lim and abs(r - sp / lim) <= 0.15 * sp / lim:
                    why.append("速率≈%s的速度/上限%.4f" % (uid, sp / lim))
                if abs(vc - prog) <= 3:
                    why.append("数值≈%s的外推进度%.2f" % (uid, prog))
                if lim and abs(vc - prog / lim) <= 0.03:
                    why.append("数值≈%s的外推比例%.3f" % (uid, prog / lim))
            if why:
                hits.append((len(why), p, va, vc, r, why))
        hits.sort(key=lambda x: -x[0])
        L("\n==== 命中(速率或数值对得上正在进行的治疗) %d 条 ====" % len(hits))
        for n, p, va, vc, r, why in hits[:80]:
            L("  %s  %.4f→%.4f  速率 %.4f/s  %s" % (p, va, vc, r, " | ".join(why)))
        L("\n==== 所有匀速变化的数值(|值|≤5000) %d 条 ====" % len(steady))
        for p, va, vc, r in sorted(steady, key=lambda x: x[0])[:300]:
            L("  %s  %.4f→%.4f  速率 %.4f/s" % (p, va, vc, r))
    except Exception:
        import traceback
        L(traceback.format_exc())
    L("END")
    try:
        f = open(OUTF, "w"); f.write("\n".join(str(x) for x in lines) + "\n"); f.close()
    except Exception:
        pass
    st["running"] = False


st = sys.__dict__.setdefault("_idv_healscan", {})
if st.get("running") and time.time() - st.get("t0", 0) < 60:
    P("BUSY")
else:
    st.update(running=True, t0=time.time())
    th = threading.Thread(target=run, args=(st,))
    th.daemon = True
    th.start()
    P("STARTED heals=%s" % R(heals(), 300))
