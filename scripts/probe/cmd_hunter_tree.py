# -*- coding: utf-8 -*-
# probe2 命令：dump 场上监管的【完整天赋树】
#   数据源 unit.genius_id_lv_lst（units_by_type[1]）—— 进程内读是完整的全部条目(含中间节点，不止 4 终端)。
#   每个天赋 id 用 GK.DM.butcher_genius 配表解成 名称 / 所在层.序 / 前置依赖，并与内置中文表交叉校验。
#   在局内(自己打监管最直接；打求生者也能读对面监管)时跑。不能 sleep(在游戏主线程 exec)。

NAME = {1:"恶化",2:"执念",3:"枯萎",4:"恐慌",5:"破坏欲",6:"狂暴",7:"愤怒",8:"禁闭空间",
        9:"封禁",10:"困兽之斗",11:"狩猎本能",12:"报幕",13:"好客之道",14:"崩坏",15:"通缉",16:"底牌",
        17:"惯性",18:"摧枯拉朽",19:"嘲弄",20:"临界点",21:"狂欢",22:"巨钳",23:"拘禁狂",24:"挽留",
        25:"狩鹿",26:"掌控欲",27:"耐受力",28:"表现欲",29:"后遗症",30:"清道夫",31:"追猎",32:"张狂",
        33:"嬉弄",34:"幽闭恐惧",35:"冲动",36:"成瘾症",37:"余威",38:"饥荒",39:"惊弓之鸟",40:"念旧癖"}
TERM = {8, 16, 24, 32}   # 四个终端大天赋

gk = GK
dm = S(lambda: gk.DM)
try:
    import common_tools.utils as U
except Exception as e:
    U = None
    P("[warn] import common_tools.utils 失败: %r (名称退回内置表)" % (e,))

def cfg(gid):
    # 走配表拿 (layer, node_seq, pre_genius, 活体名)。taggeddict 不是 dict 子类，用鸭子类型。
    row = S(lambda: dm.butcher_genius[gid])
    if row is None:
        return (None, None, None, None)
    try:
        d = row[min(row.keys())]
    except Exception:
        return (None, None, None, None)
    layer = S(lambda: d['layer'])
    nseq  = S(lambda: d['node_seq'])
    pre   = S(lambda: d['pre_genius'])
    live  = None
    if U is not None:
        psv = S(lambda: d['passive_skill_id_lv'][0])
        if psv:
            sid, slv = psv
            live = S(lambda: U.do_ui_tid_replace(dm.get_passive_skill_data_from_id_lv(sid, slv)['name_tid']))
    return (layer, nseq, pre, live)

def show(gid, lv, prefix="   "):
    layer, nseq, pre, live = cfg(gid)
    name = live or NAME.get(gid, "?")
    mark = ""
    if live and NAME.get(gid) and live != NAME.get(gid):
        mark = " (配表=%s/内置=%s 不一致!)" % (live, NAME.get(gid))
    term = " ★" if gid in TERM else ""
    P("%sid=%-3s lv=%s  %-7s 层%s.%s  前置=%s%s%s" % (
        prefix, gid, lv, R(name, 7), layer, nseq, R(pre, 18), term, mark))

def flatten(obj):
    # genius_data_b_active_page 可能是 {分支:{id:lv}} 或 {id:lv}；统一拍平成 [(id,lv),...]
    out = []
    try:
        items = list(obj.items())
    except Exception:
        return out
    for k, v in items:
        try:
            vit = list(v.items())           # 值还是 dict -> 分支层
            for gid, lv in vit:
                out.append((gid, lv))
        except Exception:
            out.append((k, v))              # 值不是 dict -> 本身就是 {id:lv}
    return out

ubt = S(lambda: gk.unit_mgr.units_by_type, {}) or {}
P("g_unit=%s  room=%s" % (cname(S(lambda: gk.g_unit)), cname(S(lambda: gk.g_unit.room))))
P("units_by_type 键 = %s" % sorted([k for k in S(lambda: list(ubt.keys()), [])]))

# ===== 账号级权威源：自身监管的完整天赋树(训练房/大厅也在，带等级含非终端) =====
av = S(lambda: gk.g_avatar)
page = S(lambda: av.genius_data_b_active_page)
P("\n===== g_avatar.genius_data_b_active_page （自身监管全树）=====")
P("  原始 = %s" % R(page, 160))
pairs = flatten(page) if page is not None else []
if pairs:
    pts = 0
    for gid, lv in sorted(pairs):
        try: pts += int(lv)
        except Exception: pass
        show(gid, lv)
    P("  合计加点 %d（正常监管为 7）" % pts)
else:
    P("  (拍平后为空 —— 看上面原始结构，可能字段名/层次不同)")

hunters = S(lambda: list(ubt.get(1, [])), []) or []
if not hunters:
    P("\n没有 units_by_type[1]（监管单位）—— 不在局内？")

for u in hunters:
    d  = S(lambda u=u: idict(u), {}) or {}
    nm = S(lambda: d.get("player_name"))
    uid = S(lambda: d.get("uid"))
    ss = S(lambda: d.get("support_skill_id"))
    gl = S(lambda: d.get("genius_id_lv_lst"))
    P("\n===== %s uid=%s name=%s 辅助特质=%s =====" % (cname(u), R(uid, 10), R(nm, 14), R(ss, 10)))
    if not isinstance(gl, list):
        P("  genius_id_lv_lst 取不到: %r" % (gl,))
        continue
    P("  共 %d 条（完整树，含中间节点）；★=终端大天赋" % len(gl))
    pts = 0
    for pair in gl:
        try:
            gid, lv = pair
        except Exception:
            P("   异常条目 %r" % (pair,))
            continue
        try:
            pts += int(lv)
        except Exception:
            pass
        show(gid, lv)
    P("  合计加点 %d（正常监管为 7）" % pts)
