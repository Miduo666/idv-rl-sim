# -*- coding: utf-8 -*-
# probe2 命令(2026-10-22)：约瑟夫镜世界("photo world")鬼魂来源定位。
# 目的：搞清镜世界里被"额外算一次"的密码机/求生者/骨骼鬼魂，在 Python 层到底是什么对象，
#       以及怎么把它们和真身区分开，好写进叠加层过滤(扛把它们加进废弃模型黑名单)。
#
# 静态已确认：约瑟夫不生成克隆单位，而是对已有单位调 switch_photo_state(in_photo)，
#   并把"已移除但保留模型"的东西收在 unit_mgr.units_removed_but_model_by_type。
#   本探针就是去活体验证这一点 + 拿到这些模型的 id/类名/坐标，和真身 unit.model 对照。
#
# ！！怎么跑：进一局约瑟夫局，分两次采 —— ①镜世界【没开】时跑一次 ②约瑟夫按快门/进镜世界后立刻再跑一次。
#   两次输出对比，差出来的那批对象就是鬼魂。不要 sleep(探针在游戏主线程 exec，sleep 会卡游戏)。
import re

gk = GK
P("==== TIME %.1f ====" % time.time())

# --- 0) 确认是不是约瑟夫局 / 镜世界状态 ---
wm = S(lambda: gk.g_world_mgr)
bw = S(lambda: wm.battle_world)
P("world=%s battle_world=%s" % (cname(S(lambda: wm.cur_world)), cname(bw)))

um = S(lambda: gk.unit_mgr)
keys = S(lambda: sorted([k for k in ubt().keys() if isinstance(k, int)]), []) or []
P("ubt 键+数量: " + ", ".join("%d:%d" % (k, len(S(lambda k=k: units_of(k), []) or [])) for k in keys))

# --- 1) units_removed_but_model_by_type —— 静态源码里的鬼魂来源 ---
d = S(lambda: idict(um), {}) or {}
rm = S(lambda: d.get("units_removed_but_model_by_type"))
P("\n== units_removed_but_model_by_type == type=%s" % cname(rm))
if isinstance(rm, dict):
    for t, v in S(lambda: list(rm.items()), []) or []:
        lst = v if isinstance(v, (list, tuple)) else [v]
        P("  type %s : %d 项" % (t, len(lst)))
        for m in list(lst)[:8]:
            # m 可能是 model 对象，也可能是 (uid,model) / dict
            mo = m
            if isinstance(m, (list, tuple)) and m:
                mo = m[-1]
            P("     item=%s id=0x%x  path=%s vis=%s" % (
                cname(mo), id(mo),
                R(S(lambda mo=mo: mo.model_path) or S(lambda mo=mo: mo.get_filename()) or S(lambda mo=mo: mo.filename), 60),
                R(S(lambda mo=mo: mo.visible), 8)))
else:
    # 不是 dict 就把 unit_mgr 上名字含 remove/photo/ghost/model 的属性列出来
    for k in sorted([x for x in d.keys() if isinstance(x, str)]):
        if re.search(r"remov|photo|ghost|gray|poster|snapshot", k, re.I):
            P("  um.%s = %s (%s)" % (k, R(d[k], 80), cname(d[k])))

# --- 2) 约瑟夫 PhotoUnit 状态 ---
pu = None
for k in keys:
    for u in (S(lambda k=k: units_of(k), []) or []):
        if "Photo" in cname(u):
            pu = u
            break
    if pu:
        break
P("\n== PhotoUnit == %s" % cname(pu))
if pu is not None:
    pd = S(lambda: idict(pu), {}) or {}
    P("  is_active=%s _players=%s _time=%s" % (
        R(S(lambda: pu.is_active()), 10), R(pd.get("_players"), 60), R(pd.get("_time"), 20)))

# --- 3) 每个真身单位的 model + photo 标志，用来和鬼魂对照 ---
def dump_units(t, label, limit=8):
    P("\n== %s units_by_type[%d] ==" % (label, t))
    for u in (S(lambda: units_of(t), []) or [])[:limit]:
        ud = S(lambda u=u: idict(u), {}) or {}
        mo = ud.get("model")
        line = "  uid=%s %s id=0x%x" % (R(ud.get("uid"), 10), cname(u), id(u))
        line += " model=0x%x(%s)" % (id(mo), R(S(lambda mo=mo: mo.model_path), 40)) if mo is not None else " model=None"
        # photo 相关标志(静态源码里 BaseUnit/GeneratorUnit 上的)
        for a in ("in_photo", "in_photo_world", "in_photo_uid", "out_photo_uid", "is_in_photo"):
            if a in ud:
                line += " %s=%s" % (a, R(ud[a], 12))
        # 字典里名字含 photo/gray/another/model 的额外属性(可能挂着鬼魂模型)
        extra = []
        for k in ud:
            if isinstance(k, str) and k != "model" and re.search(r"photo|gray|another_model|_model$", k):
                v = ud[k]
                if v is not None and not isinstance(v, (int, float, bool, str)):
                    extra.append("%s=0x%x(%s)" % (k, id(v), cname(v)))
                elif isinstance(v, (int, bool)):
                    extra.append("%s=%s" % (k, v))
        if extra:
            line += "  |ATTR| " + " ".join(extra[:8])
        P(line)

dump_units(3, "密码机", 10)
dump_units(2, "求生者", 8)
dump_units(1, "监管", 4)
P("\n==== END ====")
