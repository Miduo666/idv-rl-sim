# -*- coding: utf-8 -*-
# probe2 命令(2026-09-25)：治疗/自愈连续采样。由 heal60.ps1 投递，它会在最前面加 SECONDS / INTERVAL 两行。
# 命令本身立刻返回；采样在自己的 daemon 线程里跑(跟 probe2 的 loop 同一种做法)，每 INTERVAL 秒一帧，
# 每帧一行 JSON 追加写到 idv_heal60.jsonl。每帧内容：
#   h    监管当前动画 + last_cast_skill_id
#   s    每个 units_by_type[2] 单位：固定的治疗字段 + 名字命中关键字的标量(kw) + 本帧变化的标量(chg)
# chg 不猜字段名：所有 int/bool/None/短 str 属性(float 只看命中关键字的)逐帧比，变了就记，
# 用来找"倒地/受伤"是哪个字段。同名属性全场累计变化超过 NOISY_AFTER 次后不再逐条记，只计数。
import sys, threading

try:
    SECONDS
except NameError:
    SECONDS = 60
try:
    INTERVAL
except NameError:
    INTERVAL = 0.25

OUTF = "/sdcard/Android/data/com.netease.dwrg/files/idv_heal60.jsonl"
KW = ("hp", "blood", "hurt", "injur", "fall", "down", "dying", "cure", "heal", "life", "health",
      "crawl", "stand", "rescue", "recover", "wound")
# now：验证 debug_record_cured_info[0] 的时间戳是不是跟 unit.now 同一个钟(外推要用)
FIXED = ("cured_process_client", "cured_speed_client", "cured_uid", "debug_record_cured_info", "floor_blood", "now")
NOISY_AFTER = 12


def jv(v, depth=0):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, (tuple, list)) and depth < 2:
        return [jv(x, depth + 1) for x in list(v)[:12]]
    return R(v, 60)


def anim(d):
    ap = d.get("animation_parameter")
    if isinstance(ap, (tuple, list)):
        return jv(ap[0]) if ap else None
    return jv(ap)


def tick(prev, seen, cnt):
    m = S(lambda: GK.unit_mgr)
    ub = S(lambda: m.units_by_type) or {}
    cam = S(lambda: GK.g_cam_ctrl.unit)
    out = {}
    hs = S(lambda: list(ub.get(1) or []), []) or []
    if hs:
        hd = idict(hs[0])
        out["h"] = [anim(hd), jv(S(lambda: hs[0].skill_mgr.last_cast_skill_id))]
    rows = []
    for u in S(lambda: list(ub.get(2) or []), []) or []:
        d = idict(u)
        uid = d.get("uid")
        e = {"uid": uid, "cls": cname(u), "me": u is cam, "anim": anim(d)}
        for k in FIXED:
            e[k] = jv(d.get(k))
        kw, ch = {}, []
        first = uid not in seen
        for k, v in list(d.items()):
            if not isinstance(k, str) or k in FIXED:
                continue
            lk = k.lower()
            hit = any(w in lk for w in KW)
            if isinstance(v, float):
                if not hit:
                    continue
            elif not (v is None or isinstance(v, (bool, int)) or (isinstance(v, str) and len(v) <= 40)):
                continue
            if hit and v not in (None, 0, False, ""):
                kw[k] = jv(v)
            key = (uid, k)
            if key in prev:
                if prev[key] != v:
                    c = cnt.get(k, 0) + 1
                    cnt[k] = c
                    if c <= NOISY_AFTER:
                        ch.append([k, jv(prev[key]), jv(v)])
            elif not first:
                ch.append([k, "<new>", jv(v)])
            prev[key] = v
        seen.add(uid)
        e["kw"] = kw
        if ch:
            e["chg"] = ch
        rows.append(e)
    out["s"] = rows
    return out


def run(st):
    f = None
    t0 = time.time()
    n = 0
    cnt = {}
    try:
        f = open(OUTF, "w")
        f.write(json.dumps({"start": True, "t0": t0, "seconds": SECONDS, "interval": INTERVAL,
                            "world": cname(S(lambda: GK.g_world_mgr.cur_world))}, ensure_ascii=False) + "\n")
        prev, seen = {}, set()
        while time.time() - t0 < SECONDS:
            ts = time.time()
            rec = {"i": n, "t": round(ts - t0, 3)}
            try:
                rec.update(tick(prev, seen, cnt))
            except Exception as ex:
                rec["err"] = R(ex, 200)
            rec["cost_ms"] = round((time.time() - ts) * 1000, 2)
            f.write(json.dumps(rec, ensure_ascii=False, default=repr) + "\n")
            f.flush()
            n += 1
            left = INTERVAL - (time.time() - ts)
            if left > 0:
                time.sleep(left)
        f.write(json.dumps({"end": True, "n": n, "counts": cnt, "noisy_after": NOISY_AFTER},
                           ensure_ascii=False) + "\n")
    except Exception:
        import traceback
        try:
            f.write(json.dumps({"fatal": traceback.format_exc()}) + "\n")
        except Exception:
            pass
    finally:
        try:
            f.close()
        except Exception:
            pass
        st["running"] = False


st = sys.__dict__.setdefault("_idv_heal60", {})
if st.get("running") and time.time() - st.get("t0", 0) < st.get("seconds", 0) + 30:
    P("BUSY 上一轮还在跑，开始于 %.1f 秒前" % (time.time() - st["t0"]))
else:
    st.update(running=True, t0=time.time(), seconds=SECONDS)
    try:
        th = threading.Thread(target=run, args=(st,))
        th.daemon = True
        th.start()
        P("STARTED seconds=%s interval=%s units2=%d out=%s" % (
            SECONDS, INTERVAL, len(units_of(2) or []), OUTF))
    except Exception as ex:
        st["running"] = False
        P("START_FAIL %s" % R(ex, 200))
