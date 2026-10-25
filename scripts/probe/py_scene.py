# -*- coding: utf-8 -*-
r"""跨进程(无需 probe2)在 CPython 层按名字找"阶段/场景"字段,解决 大厅 vs 准备 分不开。

    python py_scene.py <场景名>        # lobby / prepare / battle

走链: *(libbase+0xA7029E8)=sys.modules -> game_kernel 模块 -> 模块dict
      -> 列阶段关键字全局 + 走 g_ui_mgr.ui_dict 列 keys(验 UIRoomWait 存在性)
前提: 游戏前台(跨进程读要页常驻)。靠 pyw/devread,不需要注入 probe2。
"""
import sys, os, json
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from idv_probe import discover
from pyw import Py

SYS_MODULES_OFF = 0xA7029E8
HINT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scene_hint.json")
KW = ("room", "match", "prepare", "ready", "lobby", "select", "battle", "stage",
      "scene", "world", "state", "phase", "mode", "game_", "ui_", "g_", "cur_")


def main():
    scene = sys.argv[1] if len(sys.argv) > 1 else "?"
    pid, libbase, bss, maps = discover()
    p = Py(pid, libbase)

    def tpname(obj):
        if not obj:
            return "?"
        tp = p.qf(obj + 8)
        if not tp:
            return "?"
        namep = p.qf(tp + 0x18)
        if not namep:
            return "?"
        b = p.get(namep, 64)
        if not b:
            return "?"
        z = b.find(b"\x00")
        try:
            return b[:z if z >= 0 else 64].decode("ascii")
        except Exception:
            return "?"

    def rv(v):
        tp = tpname(v)
        try:
            if tp == "int":
                return "int %s" % p.longval(v)
            if tp == "bool":
                return "bool %s" % (p.longval(v) != 0)
            if tp == "float":
                return "float %s" % p.floatval(v)
            if tp == "str":
                return "str '%s'" % p.pystr(v)
            if tp == "list":
                return "list len=%d" % len(p.list_items(v))
            if tp == "dict":
                r = p.dict_raw(v)
                return "dict nent=%s" % (r[2] if r else "?")
            if tp == "NoneType":
                return "None"
        except Exception as e:
            return "%s(err %s)" % (tp, e)
        return tp

    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    pr = print
    def flush_pr(*a):
        pr(*a); sys.stdout.flush()

    ck = {}
    try:
        ck = json.load(open(HINT))
    except Exception:
        pass
    ui_only = "--ui" in sys.argv

    SM = p.qf(libbase + SYS_MODULES_OFF)
    flush_pr("scene=%s pid=%d libbase=0x%X sys.modules=0x%X" % (scene, pid, libbase, SM))
    mi, mod = p.dget(SM, "game_kernel", ck.get("gk"))
    if not mod:
        sys.exit("没找到 game_kernel 模块(热更可能改了 SYS_MODULES_OFF)")
    ck["gk"] = mi
    md = p.qf(mod + 0x10)
    flush_pr("game_kernel mod=0x%X dict=0x%X" % (mod, md))

    # 1) 模块全局: 只打名字(便宜, dict_names 已批量), 阶段关键字优先。--ui 跳过。
    if not ui_only:
        names = p.dict_names(md)
        flush_pr("\n== game_kernel 全局名 (共%d) 阶段关键字命中 ==" % len(names))
        hit = sorted(nm for _, nm, v in names if any(w in nm.lower() for w in KW))
        for nm in hit:
            flush_pr("  " + nm)

    # 2) g_ui_mgr.ui_dict keys —— UIRoomWait 存在性 = 准备判据?  (只打 key 名)
    flush_pr("\n== g_ui_mgr.ui_dict keys (UIRoomWait 存在=准备?) ==")
    mgri, uimgr = p.dget(md, "g_ui_mgr", ck.get("uimgr"))
    if not uimgr:
        flush_pr("  没取到 g_ui_mgr")
    else:
        ck["uimgr"] = mgri
        ud = p.inst_dict(uimgr)
        flush_pr("  g_ui_mgr=0x%X inst_dict=0x%X cls=%s" % (uimgr, ud or 0, tpname(uimgr)))
        udi, uidict = (p.dget(ud, "ui_dict", ck.get("uidict")) if ud else (None, None))
        if uidict:
            ck["uidict"] = udi
        try:
            json.dump(ck, open(HINT, "w"))
        except Exception:
            pass
        if not uidict:
            flush_pr("  没取到 ui_dict; g_ui_mgr 属性名:")
            if ud:
                for _, nm, v in sorted(p.dict_names(ud)):
                    flush_pr("     " + nm)
        else:
            keys = sorted(nm for _, nm, v in p.dict_names(uidict))
            flush_pr("  ui_dict keys (%d):" % len(keys))
            for nm in keys:
                flush_pr("     " + nm)


if __name__ == "__main__":
    main()
