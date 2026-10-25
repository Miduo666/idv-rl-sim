# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：模仿者模式广度搜索(重，1~2 秒一次，只在开局/中途/结束各跑一次)。
# 从 玩家单位 / 世界 / 名字可疑的 UI 面板 / game_kernel 顶层 出发广度遍历，报告三类命中：
#   KW   属性名/字典键命中关键字
#   VAL  整数值落在身份号段 101~118 / 201~209 / 301~308
#   VKEY 字典的整数键落在身份号段(身份->xxx 的映射表)
# 另外单列 GK.DM 里名字可疑的配表(身份名/阵营配置可能在这里)。
# 不 sleep；有时间和节点上限，超了会打 TRUNC。
import re, types
gk = GK
t0 = time.time()
BUDGET = 1.5
MAXN = 6000
RX = re.compile(r"ident|camp|role|copycat|detect|mimic|imitat|faction|team|reveal|secret|hidden|disguise"
                r"|career|job|neutral|spy|vote|meet|dead|die|alive|elim|kill|suspect|clue|component")
UIRX = re.compile(r"copy|ident|role|camp|detect|vote|meet|mimic|spy|clue|job|career", re.I)
FOLLOW = {"components", "_components", "ability", "params", "combat_unit"}
IDR = set(range(101, 119)) | set(range(201, 210)) | set(range(301, 309))
PLAYERISH = re.compile(r"civilian|butcher|player|copycat|detect|mimic|survivor|hunter", re.I)
# 模仿者局里 Copycat*Unit 还包括场景物件(CopycatSceneUnit/ElectricUnit/GeneratorUnit/RavenGateUnit)，排除掉
NOTPLAYER = re.compile(r"scene|electric|generator|gate", re.I)
CONT = (dict, list, tuple, set, frozenset)
LEAF = (bool, int, float, str, bytes, type(None))
FUNCS = (types.ModuleType, types.FunctionType, types.BuiltinFunctionType, types.MethodType, type)
UI_CLS = ("Node", "Button", "Layout", "Sprite", "Label", "ScrollView", "Widget", "ImageView", "RichText",
          "CheckBox", "Slider", "EditBox", "ListView", "PageView", "RichTextEx55", "TextField", "Text",
          "LoadingBar")
LIM = {"KW": 2500, "VAL": 1200, "VKEY": 400}
cnt = {"KW": 0, "VAL": 0, "VKEY": 0, "node": 0}
seen = set()
trunc = [False]


def one(v, n=120):
    return R(v, n).replace("\t", " ").replace("\n", " ")


def brief(v, n=120):
    ln = S(lambda: len(v), 0) if isinstance(v, CONT) else 0
    if ln > 30:
        head = list(v.items())[:5] if isinstance(v, dict) else list(v)[:5]
        return "<%s len=%d> %s" % (type(v).__name__, ln, one(head, n))
    return one(v, n)


def emit(kind, s):
    if cnt[kind] < LIM[kind]:
        P(kind + "\t" + s)
    cnt[kind] += 1


def children(o):
    if isinstance(o, dict):
        return [("[%s]" % one(k, 40), k, v) for k, v in list(o.items())[:400]]
    if isinstance(o, (list, tuple)):
        return [("[%d]" % i, None, v) for i, v in enumerate(list(o)[:400])]
    if isinstance(o, (set, frozenset)):
        return [("{}", None, v) for v in list(o)[:400]]
    d = idict(o)
    return [("." + k, k, v) for k, v in list(d.items()) if isinstance(k, str)] if isinstance(d, dict) else []


def bfs(roots, maxd, follow_all):
    """roots: [(path, obj)]；follow_all=False 时第一层只进入名字命中关键字/FOLLOW 的属性"""
    q = [(p, o, 0, follow_all) for p, o in roots]
    i = 0
    while i < len(q):
        if time.time() - t0 > BUDGET or cnt["node"] >= MAXN:
            trunc[0] = True
            return
        path, o, dep, fa = q[i]
        i += 1
        if id(o) in seen:
            continue
        seen.add(id(o))
        cnt["node"] += 1
        isdict = isinstance(o, dict)
        for seg, k, v in children(o):
            name = k if isinstance(k, str) else None
            hit = name is not None and RX.search(name.lower()) is not None
            if hit and not isinstance(v, FUNCS):
                emit("KW", "%s%s\t%s\t%s" % (path, seg, cname(v), brief(v)))
            if type(v) is int and v in IDR:
                emit("VAL", "%s%s\t%d" % (path, seg, v))
            if isdict and type(k) is int and k in IDR:
                emit("VKEY", "%s%s\t%s\t%s" % (path, seg, cname(v), brief(v, 80)))
            if dep + 1 > maxd or isinstance(v, LEAF) or isinstance(v, FUNCS) or id(v) in seen:
                continue
            if cname(v) in UI_CLS:
                continue
            if fa or hit or (name in FOLLOW):
                q.append((path + seg, v, dep + 1, True))


P("TIME\t%.3f" % t0)

# 1) 玩家单位：第一层全扫，只顺着可疑属性往下走
roots = []
seen_u = set()
for k in sorted([x for x in (S(lambda: list(ubt().keys()), []) or []) if isinstance(x, int)]):
    for u in units_of(k):
        if id(u) in seen_u:
            continue
        if k in (1, 2) or (PLAYERISH.search(cname(u)) and not NOTPLAYER.search(cname(u))):
            seen_u.add(id(u))
            roots.append(("U%s<%s>" % (S(lambda u=u: idict(u).get("uid")), cname(u)), u))
P("ROOTS_UNITS\t%d" % len(roots))
bfs(roots[:24], 3, False)

# 2) 世界对象
wm = S(lambda: gk.g_world_mgr)
wr = [("W.g_world_mgr", wm)] if wm is not None else []
for a in ("cur_world", "battle_world"):
    w = S(lambda a=a: getattr(wm, a))
    if w is not None:
        wr.append(("W." + a + "<" + cname(w) + ">", w))
bfs(wr, 2, True)

# 3) 名字可疑的 UI 面板
ui = S(lambda: gk.g_ui_mgr.ui_dict, {}) or {}
ur = [("UI[%s]" % k, v) for k, v in S(lambda: list(ui.items()), []) if isinstance(k, str) and UIRX.search(k)]
P("UI_PANELS\t%s" % one([p for p, _ in ur], 600))
bfs(ur, 2, True)

# 4) game_kernel 顶层(跳过 DM 配表和已经走过的管理器)
gr = []
for name, v in S(lambda: list(vars(gk).items()), []):
    if not isinstance(name, str) or name.startswith("__") or name in ("DM", "unit_mgr", "g_ui_mgr", "g_world_mgr"):
        continue
    if isinstance(v, LEAF + FUNCS):
        if RX.search(name.lower()) and isinstance(v, LEAF):
            emit("KW", "GK.%s\t%s\t%s" % (name, cname(v), brief(v)))
        continue
    gr.append(("GK." + name, v))
bfs(gr, 2, True)

# 5) DM 配表：名字可疑的列出来(不遍历，太大)
dm = S(lambda: gk.DM)
dd = S(lambda: idict(dm), {}) or {}
for a in sorted([x for x in dd.keys() if isinstance(x, str)]):
    if RX.search(a.lower()) or "copy" in a.lower():
        v = dd[a]
        P("DM\t%s\t%s\t%s" % (a, cname(v), brief(v, 300)))
# DM 也可能是按需加载的属性(不在 __dict__)，按 dir 再补一遍名字
dnames = [x for x in S(lambda: dir(dm), []) if isinstance(x, str) and x not in dd and (RX.search(x.lower()) or "copy" in x.lower())]
P("DM_DIR\t%s" % one(dnames, 1500))

P("TRUNC\t%s\tnodes=%d\tKW=%d VAL=%d VKEY=%d(超过上限的只计数不输出)" % (
    trunc[0], cnt["node"], cnt["KW"], cnt["VAL"], cnt["VKEY"]))
P("END\t%.1fms" % ((time.time() - t0) * 1000))
