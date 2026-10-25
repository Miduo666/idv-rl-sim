# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：C++ 读 final_genius_dict 失败时，把它在进程内的真实样子打出来，
# 并用 Python 复刻 C++ 的配对逻辑(uid2pos 键 -> 键字符串 -> 查 final_genius_dict)。
# 以 FGD / SEAT 开头的行给 fgd_mem.py 用(PC 侧按 C++ 的读法再读一遍内存)。
ui = S(lambda: GK.g_ui_mgr.ui_dict, {}) or {}
panel = S(lambda: ui.get("UIRoomWait"))
pd = S(lambda: idict(panel), {}) or {}
av = S(lambda: GK.g_avatar)
ad = S(lambda: idict(av), {}) or {}
fgd = ad.get("final_genius_dict")
P("panel=%s role=%r" % (panel is not None, pd.get("role")))
P("final_genius_dict: type=%s id=0x%x len=%s" % (type(fgd).__name__, id(fgd), S(lambda: len(fgd))))
P("FGD\t0x%x" % id(fgd))
for k, v in (fgd or {}).items():
    P("  key=%r type=%s len=%s id=0x%x  ->  value=%r type=%s id=0x%x" % (
        k, type(k).__name__, S(lambda k=k: len(k)), id(k), v, type(v).__name__, id(v)))
    if isinstance(v, (list, tuple)):
        P("      元素类型: %s" % [type(x).__name__ for x in v])
P("\n== 复刻 C++ 配对(Python 侧) ==")
pos = pd.get("uid2pos") or {}
for k, seat in pos.items():
    key = "%d" % k if isinstance(k, int) else str(k)
    hit = (fgd or {}).get(key, "<没有这个键>")
    P("  座位%s eid=%r(%s) 拼出的键=%r -> %r" % (seat, k, type(k).__name__, key, hit))
    P("SEAT\t%s\t0x%x\t%s" % (seat, id(k), key))
