# -*- coding: utf-8 -*-
# probe2: 出生点选择 60s 连续采样。进出生点阶段时发一次, 它循环整段窗口。
# 每 2s 把 UIRoomWait 所有非空 dict/list 快照(名/长度/内容前220字), 写文件并 flush。
# 哪个容器在求生者选格子时发生变化 = 出生格选择数据。
import time
OUT = "/sdcard/Android/data/com.netease.dwrg/files/birth_log.txt"
f = open(OUT, "w")

def snap(tag):
    ud = S(lambda: GK.g_ui_mgr.ui_dict)
    rw = S(lambda: ud["UIRoomWait"])
    if rw is None:
        f.write("%s UIRoomWait=None me=%s keys=%s\n" % (tag, cname(me), R(S(lambda: list(ud.keys())), 80)))
        f.flush(); return
    blt = S(lambda: rw.birth_left_time)
    hs = S(lambda: rw.has_select)
    f.write("\n==== %s birth_left=%s has_select=%s ====\n" % (tag, R(blt, 10), R(hs, 8)))
    for a in sorted(S(lambda: list(idict(rw).keys()), [])):
        if not isinstance(a, str) or a.startswith("__"):
            continue
        v = S(lambda a=a: idict(rw)[a])
        cn = cname(v)
        if cn in ("dict", "list"):
            n = S(lambda v=v: len(v), 0)
            if n:
                f.write("  %-32s %s(%d) %s\n" % (a, cn, n, R(v, 220)))
    f.flush()

t0 = time.time()
n = 0
while time.time() - t0 < 68:
    snap("t+%.0f" % (time.time() - t0))
    n += 1
    time.sleep(2)
f.write("\n== done, %d snapshots ==\n" % n)
f.close()
P("STARTED birth loop -> birth_log.txt, %d 轮已写完" % n)
