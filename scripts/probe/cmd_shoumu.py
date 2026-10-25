# -*- coding: utf-8 -*-
# probe2 命令：守墓人(m_shoumu)遁地状态采样。单次快照，不 sleep(会卡主线程)，由 PC 侧连续投递成序列。
# 关心的是：遁地时 unit.model 会不会换对象/换路径、visible 怎么变、高度掉多少
# —— 这决定叠加层的"废弃模型黑名单(another_model)"和"D.Z <= -300 跳过地下"两条会不会把他滤掉。
import time

gk = GK
P("== T=%.3f ==" % time.time())

ubt = S(lambda: gk.unit_mgr.units_by_type, {}) or {}
targets = []
for t in (1, 2):
    for u in S(lambda t=t: list(ubt.get(t, [])), []) or []:
        mp = S(lambda u=u: u.model_path, "") or ""
        cn = cname(u)
        if "shoumu" in str(mp).lower() or S(lambda u=u: u.is_self, False) is True:
            targets.append((t, u, mp, cn))

P("units_by_type 键 = %s" % sorted([k for k in S(lambda: list(ubt.keys()), [])]))
P("命中单位 %d 个" % len(targets))

for t, u, mp, cn in targets:
    P("\n[键%d] %s uid=%s is_self=%s camp=%s" % (
        t, cn, R(S(lambda: u.uid), 20), R(S(lambda: u.is_self), 8), R(S(lambda: u.dk_camp_type), 8)))
    P("   model_path = %s" % mp)
    for attr in ("model", "another_model"):
        mo = S(lambda attr=attr: getattr(u, attr))
        if mo is None:
            P("   %-14s = None" % attr); continue
        P("   %-14s id=0x%X vis=%s file=%s" % (
            attr, id(mo), R(S(lambda mo=mo: mo.visible), 8),
            R(S(lambda mo=mo: getattr(mo, "filename", getattr(mo, "model_path", "?"))), 70)))
    pos = S(lambda: u.position)
    P("   position   = %s" % R(pos, 70))
    # 场景对象 = model + 0x20。叠加层的 D.Z<=-300(跳过地下) 判的是场景侧的高度(objcoor+0xa4)，
    # 不是 unit.position，所以必须直接读内存。ctypes 不可用时这段整体跳过
    ct = S(lambda: __import__("ctypes"))
    if ct is not None:
        def rd(addr, typ):
            return S(lambda: ct.cast(addr, ct.POINTER(typ))[0])
        for attr in ("model", "another_model"):
            mo = S(lambda attr=attr: getattr(u, attr))
            if mo is None: continue
            sp = rd(id(mo) + 0x20, ct.c_uint64)
            if not sp: continue
            sp &= 0x00FFFFFFFFFFFFFF
            coor = rd(sp + 0x28, ct.c_uint64)
            xyz = "?"
            if coor:
                coor &= 0x00FFFFFFFFFFFFFF
                xyz = "%.1f / %.1f / %.1f" % (rd(coor + 0xa0, ct.c_float), rd(coor + 0xa4, ct.c_float),
                                              rd(coor + 0xa8, ct.c_float))
            P("   %s 场景对象=0x%X  X/高/Y=%s  +0x240=%s +0x6D=0x%02X +0x73=%s" % (
                attr, sp, xyz, rd(sp + 0x240, ct.c_uint32), rd(sp + 0x6D, ct.c_ubyte) or 0,
                rd(sp + 0x73, ct.c_ubyte)))
    # 遁地相关：名字里带这些词的属性，值不是 None/0/False 的都打出来
    KW = ("dig", "hole", "under", "burrow", "grave", "tudi", "dun", "invisible", "hide",
          "stealth", "state", "skill_state", "in_", "is_")
    names = S(lambda: sorted(attr_names(u)), []) or []
    hits = []
    for k in names:
        if not any(w in k.lower() for w in KW):
            continue
        v = S(lambda k=k: idict(u).get(k))
        if v in (None, 0, False, "", [], {}):
            continue
        hits.append("%s=%s" % (k, R(v, 40)))
    P("   非空状态属性(%d): %s" % (len(hits), " | ".join(hits[:40])))
