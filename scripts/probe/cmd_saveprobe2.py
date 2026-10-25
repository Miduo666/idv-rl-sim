# -*- coding: utf-8 -*-
# probe2: 抓"装修摆新家具 -> 点[确定]/保存无反应"的失败点。不改任何行为，只记录。
#
# 分两段:
#  (1) 一次性诊断上次 grant 写进 pp['14'] 的记录是否畸形
#      (内层 props_id 没按家具改、实例 id 全复用模板那条) —— 验证"保存失败=数据脏"的猜想。
#  (2) 装 hook: 包住 保存/摆放/上行 相关 Avatar 方法 + call_server_method(按名过滤),
#      记录 每次调用/参数/返回/异常+traceback 到 save_probe.txt。
#      hook 装一次就常驻, 你之后连点[确定], 每点一次都会往 save_probe.txt 追加。
#
# 判读:
#  - 点确定后 save_probe.txt 里 **什么都没有** -> 拦截在 UI 层, 根本没进 Avatar 上行 (客户端预校验静默 return)。
#  - 出现 CALL request_save_custom_hall_scheme 然后 EXC...traceback -> 客户端序列化/断言炸了 (多半就是脏数据)。
#  - 出现 UPLINK call_server_method ... 之后又来个 *_cb 带错误码 -> 服务器拒收。
import time, traceback
gk = GK
a  = S(lambda: gk.g_avatar)
AC = type(a) if a is not None else None
LOG = "/sdcard/Android/data/com.netease.dwrg/files/save_probe.txt"

def _log(tag, obj="__none__"):
    try:
        f = open(LOG, "a")
        if obj == "__none__":
            f.write("[%.3f] %s\n" % (time.time(), tag))
        else:
            f.write("[%.3f] %s %s\n" % (time.time(), tag, R(obj, 500)))
        f.close()
    except Exception:
        pass

if AC is None:
    P("g_avatar 未就绪，进庄园再跑")
else:
    # ---------- (1) 诊断 grant 数据 ----------
    pp  = S(lambda: a.props_package)
    fur = S(lambda: pp.get("14")) if pp is not None else None
    if fur:
        dup_inst = 0          # 实例 id 复用模板那条的数量
        mismatch = 0          # 内层 props_id != 外层 key 的数量
        inst_set = {}         # 实例 id -> 出现次数 (看撞车)
        sample_bad = None; sample_ok = None
        for ok, ov in list(fur.items()):
            if not isinstance(ov, dict):
                continue
            try:
                out_i = int(ok)
            except Exception:
                out_i = None
            for ik, iv in ov.items():          # 只看第一条内层记录
                inst_set[ik] = inst_set.get(ik, 0) + 1
                pid = iv.get("props_id") if isinstance(iv, dict) else None
                if pid is not None and out_i is not None and pid != out_i:
                    mismatch += 1
                    if sample_bad is None:
                        sample_bad = (ok, ov)
                elif sample_ok is None:
                    sample_ok = (ok, ov)
                break
        dup_inst = sum(1 for v in inst_set.values() if v > 1)
        dup_total = sum(v for v in inst_set.values() if v > 1)
        P("诊断 pp['14']: 共 %d 条" % len(fur))
        P("  内层 props_id ≠ 外层key (畸形授予): %d 条" % mismatch)
        P("  实例id 撞车: %d 个id 被 %d 条记录共用" % (dup_inst, dup_total))
        P("  正常样本:", R(sample_ok, 240))
        P("  畸形样本:", R(sample_bad, 240))
        if mismatch > 100:
            P("  >>> 证实: 上次 grant 的内层记录是脏的(没改 props_id/实例id)。这极可能就是保存失败的根因。")
    else:
        P("pp['14'] 读不到，跳过诊断")

    # ---------- (2) 装 hook ----------
    if getattr(AC, "_saveprobe", 0):
        P("save hook 已在，直接去点[确定]，然后 cat save_probe.txt")
    else:
        names = [
            "request_save_custom_hall_scheme", "request_save_custom_hall_scheme_cb",
            "request_place_furniture", "request_place_furniture_cb",
            "request_update_furniture_f_data", "request_update_furniture_f_data_cb",
            "request_set_plant_furniture_info", "request_set_plant_furniture_info_cb",
            "request_remove_furniture", "request_remove_furniture_cb",
            "request_update_custom_hall", "reply_update_custom_hall",
            "request_batch_place_furniture", "request_batch_place_furniture_cb",
        ]
        # 动态补: 方法名含 scheme, 或同时含 save+hall (可能把确定按钮的真实 handler 也抓到)
        for nm in dir(AC):
            try:
                if nm in names:
                    continue
                if not callable(getattr(AC, nm, None)):
                    continue
                low = nm.lower()
                if "scheme" in low or ("save" in low and "hall" in low):
                    names.append(nm)
            except Exception:
                pass

        def mk(orig, nm):
            def w(self, *ar, **kw):
                _log("CALL " + nm, (ar, kw))
                try:
                    r = orig(self, *ar, **kw)
                    _log("RET  " + nm, r)
                    return r
                except Exception:
                    _log("EXC  " + nm + "\n" + traceback.format_exc())
                    raise
            return w

        wrapped = []
        for nm in names:
            try:
                o = getattr(AC, nm, None)
                if o is None or not callable(o):
                    continue
                setattr(AC, nm, mk(o, nm))
                wrapped.append(nm)
            except Exception:
                pass

        # call_server_method: 全量上行原语, 只记录名字相关的, 避免刷屏
        csm = getattr(AC, "call_server_method", None)
        if csm is not None and callable(csm):
            def wcsm(self, *ar, **kw):
                try:
                    mname = ar[0] if ar else kw.get("method", "")
                    s = str(mname).lower()
                    if any(x in s for x in ("hall", "furnit", "custom", "scheme", "place", "decorat")):
                        _log("UPLINK call_server_method", (ar, kw))
                except Exception:
                    pass
                return csm(self, *ar, **kw)
            try:
                setattr(AC, "call_server_method", wcsm)
                wrapped.append("call_server_method(filtered)")
            except Exception:
                pass

        AC._saveprobe = 1
        _log("=== save_probe installed on %s; hooks=%d ===" % (AC.__name__, len(wrapped)))
        P("save hook 装好 %d 个: %s" % (len(wrapped), ", ".join(wrapped)))
        P(">>> 去装修, 摆一件【新解锁】的家具, 连点几次[确定]。完了告诉我, 我让你 cat save_probe.txt")
