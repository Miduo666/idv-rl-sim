# -*- coding: utf-8 -*-
# probe2: 出生/选区阶段精准连续采样。进选区就发, 循环整段窗口。
# 专盯: g_avatar._order_info_lst / birthd / birth_area_recommend_info + cur_world.region_mgr 内部状态。
# 写 birth_log2.txt(flush), 每 1.5s 一帧。你切不同格子时, 哪个在变就是出生选择数据。
import time
OUT = "/sdcard/Android/data/com.netease.dwrg/files/birth_log2.txt"
f = open(OUT, "w")

AV_KEYS = ("_order_info_lst", "birthd", "birthd_tm", "birth_area_recommend_info",
           "juesai_area_dict", "task_choice_info")
CW_KEYS = ("has_select_zone_stage", "role_born_group", "now_select_accu", "last_region_sync_st",
           "cached_area_info", "_playground_river_region")

def snap(tag):
    av = S(lambda: GK.g_avatar)
    cw = S(lambda: GK.g_world_mgr.cur_world)
    rw = S(lambda: GK.g_ui_mgr.ui_dict.get("UIRoomWait"))
    blt = S(lambda: rw.birth_left_time) if rw else "no-RW"
    f.write("\n==== %s birth_left=%s me=%s world=%s ====\n" % (tag, R(blt, 10), cname(me), cname(cw)))
    for k in AV_KEYS:
        v = S(lambda k=k: idict(av)[k])
        f.write("  av.%-26s %-12s %s\n" % (k, cname(v), R(v, 240)))
    for k in CW_KEYS:
        v = S(lambda k=k: idict(cw)[k])
        f.write("  cw.%-26s %-12s %s\n" % (k, cname(v), R(v, 160)))
    # region_mgr 的非空容器(选择可能在这)
    rm = S(lambda: idict(cw).get("region_mgr"))
    if rm is not None:
        for a in sorted(S(lambda: list(idict(rm).keys()), [])):
            if not isinstance(a, str) or a.startswith("__"):
                continue
            v = S(lambda a=a: idict(rm)[a])
            cn = cname(v)
            if cn in ("dict", "list"):
                n = S(lambda v=v: len(v), 0)
                if n:
                    f.write("  rm.%-26s %s(%d) %s\n" % (a, cn, n, R(v, 180)))
            elif cn in ("int", "float", "bool") and any(w in a.lower() for w in ("select", "region", "born", "zone", "area", "pick", "idx")):
                f.write("  rm.%-26s %-8s %s\n" % (a, cn, R(v, 40)))
    f.flush()

t0 = time.time()
n = 0
while time.time() - t0 < 68:
    snap("t+%.0f" % (time.time() - t0)); n += 1
    time.sleep(1.5)
f.write("\n== done %d ==\n" % n); f.close()
P("STARTED birthloop2 -> birth_log2.txt, %d 帧" % n)
