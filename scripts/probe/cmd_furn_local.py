# -*- coding: utf-8 -*-
# 本地装修模式：hook 掉家具/方案的所有上行写，摆放纯本地。
#   request_place_furniture -> 本地合成 {'info':{...}} 调 request_place_furniture_cb，不上行
#   其它写(保存方案/删除/改/批量)-> 阻断成 no-op，防假数据泄漏
# 协议来自 furnlog 实测：REQ {furniture_id(base*100+idx), furniture_type, pos, dir, hall_id}
#   新放 idx=0，服务器分配下一个空实例号(≥1) 回 {'info':{... furniture_id=base*100+idx ...}}
import time
gk = GK
a  = S(lambda: gk.g_avatar)
AC = type(a) if a is not None else None
LOG = "/sdcard/Android/data/com.netease.dwrg/files/furn_local.txt"

def _log(t, o):
    try:
        f = open(LOG, "a"); f.write("[%.3f] %s %r\n" % (time.time(), t, o)); f.close()
    except Exception:
        pass

def _next_idx(av, hall_id, base):
    used = set()
    chi = None
    for hk in (str(hall_id), hall_id):
        chi = av.custom_hall_info.get(hk) if hasattr(av.custom_hall_info, "get") else None
        if chi:
            break
    finfo = chi.get("furniture_info", {}) if hasattr(chi, "get") else {}
    for sub in (finfo.values() if hasattr(finfo, "values") else []):
        for k in (sub.keys() if hasattr(sub, "keys") else []):
            try:
                ik = int(k)
                if ik // 100 == base:
                    used.add(ik % 100)
            except Exception:
                pass
    i = 1
    while i in used:
        i += 1
    return i

if AC is None:
    P("g_avatar 未就绪，进庄园再跑")
else:
    # 先卸掉只记录的 furnlog(如果在)，拿到真原函数
    if getattr(AC, "_furnlog", 0):
        AC.request_place_furniture = AC._fl_o1
        AC.request_place_furniture_cb = AC._fl_o2
        for nm, o in (getattr(AC, "_fl_batch", {}) or {}).items():
            setattr(AC, nm, o)
        for k in ("_furnlog", "_fl_o1", "_fl_o2", "_fl_batch"):
            try: delattr(AC, k)
            except Exception: pass

    if getattr(AC, "_furnlocal", 0):
        P("已在本地装修模式")
    else:
        _o_place = AC.request_place_furniture
        def _place(self, furniture_info, *ar, **kw):
            try:
                fi = dict(furniture_info)
                fid = int(fi.get("furniture_id")); base = fid // 100; idx = fid % 100
                hall_id = fi.get("hall_id")
                if idx == 0:
                    idx = _next_idx(gk.g_avatar, hall_id, base)
                    fid = base * 100 + idx
                info = {"info": {"furniture_id": fid, "furniture_type": fi.get("furniture_type"),
                                 "pos": list(fi.get("pos")), "dir": list(fi.get("dir")),
                                 "hall_id": hall_id}}
                _log("LOCAL place", info["info"])
                return self.request_place_furniture_cb(info)
            except Exception as e:
                _log("place_err", repr(e)); return None
        AC.request_place_furniture = _place

        # 阻断其它上行写(no-op)，只记录，防泄漏
        AC._furn_blocked = {}
        for nm in ("request_save_custom_hall_scheme", "request_update_furniture_f_data",
                   "request_set_plant_furniture_info", "request_remove_furniture",
                   "request_remove_furniture_batch", "request_place_furniture_batch"):
            o = getattr(AC, nm, None)
            if o is not None:
                AC._furn_blocked[nm] = o
                def mk(nm):
                    def w(self, *ar, **kw):
                        _log("BLOCK " + nm, ar[:1]); return None
                    return w
                setattr(AC, nm, mk(nm))

        AC._furnlocal = 1; AC._fl_place_o = _o_place
        _log("=== furn_local ON ===", AC.__name__)
        P("本地装修模式已开：摆家具不再上行、纯本地。去庄园装修摆摆看。")
        P("阻断的上行写:", list(AC._furn_blocked.keys()))
