# -*- coding: utf-8 -*-
r"""列出某类单位 skill_mgr.skill_dict 里每个技能对象的冷却相关字段。

链路: units_by_type[type][0] -> skill_mgr -> skill_dict -> {技能id: Skill实例}
每个 Skill 实例再取 managed dict，按名字筛。

    python py_skills.py --type 1 [--grep cd,cool,time] [--all] [--id 1603]

冷却是活跃数据，PC 侧一次往返 ~30ms，读到的值只在采样那一刻成立；
要连续观察用 --loop。
"""
import json
import os
import struct
import sys
import time

sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from pyw import Py
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
SYS_MODULES_OFF = 0xA7029E8
PYLONG_T_OFF = 0xA026498
PYFLOAT_T_OFF = 0xA0336F0
PYSTR_T_OFF = 0xA038140
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_cache.json")


def arg(n, d):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


UTYPE = int(arg("--type", 1))
GREP = [x.lower() for x in arg("--grep", "cd,cool,time,energy").split(",") if x]
ALL = "--all" in sys.argv
ONLY = arg("--id", None)
LOOP = int(arg("--loop", 1))
GAP = float(arg("--gap", 3))
TICK = "--tick" in sys.argv     # 找"正在被每帧重新赋值"的字段(冷却倒计时会自己暴露)

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
pid, libbase, bss, maps = discover()
LONG_T = libbase + PYLONG_T_OFF
FLOAT_T = libbase + PYFLOAT_T_OFF
STR_T = libbase + PYSTR_T_OFF


def 一轮():
    p = Py(pid, libbase)

    def 解值(vp, 深=0):
        b = p.get(vp, 0x28)
        if not b:
            return "读不到", None
        if struct.unpack_from("<q", b, 0)[0] <= 0:
            return "refcount异常", None
        tp = struct.unpack_from("<Q", b, 8)[0] & MASK
        if tp == FLOAT_T:
            return "float", struct.unpack_from("<d", b, 16)[0]
        if tp == LONG_T:
            sz = struct.unpack_from("<q", b, 16)[0]
            if sz == 0:
                return "int", 0
            d = struct.unpack_from("<I", b, 24)[0]
            return "int", (d if sz > 0 else -d)
        if tp == STR_T:
            return "str", p.pystr(vp)
        n = p.qf(tp + 0x18)
        p.fetch([n], 0x40)
        s = p.get(n, 48)
        名 = s.split(b"\0")[0].decode("utf-8", "replace") if s else "?"
        if 名 == "list" and 深 < 2:
            its = p.list_items(vp)
            p.fetch(its, 0x20)
            return "list", [解值(x, 深 + 1)[1] for x in its]
        return 名, None

    def 键值表(d):
        """entries 整块一次读完，返回 (序号->名字, 序号->值指针, 条数)。"""
        ent0, step, nent = p.dict_raw(d)      # 逐实例算，不能套用
        if not ent0:
            return {}, {}, 0
        键off = 0 if step == 16 else 8
        值off = 8 if step == 16 else 16
        p.fetch([ent0], nent * step)
        blk = p.get(ent0, nent * step)
        if not blk:
            return {}, {}, 0
        kp, vp = {}, {}
        for i in range(nent):
            k = struct.unpack_from("<Q", blk, i * step + 键off)[0] & MASK
            v = struct.unpack_from("<Q", blk, i * step + 值off)[0] & MASK
            if 0x7000000000 < k < 0x8000000000:
                kp[i] = k
            if 0x7000000000 < v < 0x8000000000:
                vp[i] = v
        p.fetch(list(kp.values()), 0x60)
        名 = {}
        for i, a in kp.items():
            s = p.pystr(a)
            if s:
                名[i] = s
        return 名, vp, nent

    SM = p.qf(libbase + SYS_MODULES_OFF)
    _, mod = p.dget(SM, "game_kernel", cache.get("mod"))
    _, UM = p.dget(p.qf(mod + 0x10), "unit_mgr", cache.get("unit_mgr"))
    _, UBT = p.dget(p.inst_dict(UM), "units_by_type", cache.get("units_by_type"))
    if not UBT:
        sys.exit("拿不到 units_by_type，多半不在对局中")
    lst = None
    for _, nm, v in p.dict_pairs(UBT):
        if p.longval(nm) == UTYPE:
            lst = v
            break
    if not lst:
        sys.exit("units_by_type 里没有键 %d" % UTYPE)

    print("本机时间 %.3f" % time.time())
    for o in p.list_items(lst):
        d = p.inst_dict(o)
        if not d:
            continue
        名0, vp0, _ = 键值表(d)
        找 = [i for i, s in 名0.items() if s == "skill_mgr"]
        if not 找:
            print("单位 0x%X 没有 skill_mgr" % o)
            continue
        MGR = vp0[找[0]]
        md = p.inst_dict(MGR)
        名1, vp1, _ = 键值表(md)
        找 = [i for i, s in 名1.items() if s == "skill_dict"]
        if not 找:
            print("skill_mgr 里没有 skill_dict")
            continue
        SD = vp1[找[0]]
        对 = p.dict_pairs(SD)
        print("\n单位 0x%X  skill_mgr=0x%X  skill_dict=0x%X  %d 个技能"
              % (o, MGR, SD, len(对)))
        for _, kk, vv in 对:
            sid = p.longval(kk)
            if ONLY and str(sid) != ONLY:
                continue
            sd = p.inst_dict(vv)
            if not sd:
                print("  技能 %s: 取不到 dict" % sid)
                continue
            if TICK:
                # 属性每被重新赋值一次就换一个新的值对象，所以先只比值指针，
                # 圈出正在动的少数几条，再解它们的值 —— 比全解快两个数量级。
                名2, vp2, n2 = 键值表(sd)
                时1 = time.time()
                V1 = {}
                p.fetch([v for v in vp2.values()], 0x28)
                for i, a in vp2.items():
                    V1[i] = 解值(a)
                time.sleep(GAP)
                p2 = Py(pid, libbase)                 # 新建以绕开读缓存
                旧p, globals()["p"] = p, p2
                名3, vp3, _ = 键值表(sd)
                时2 = time.time()
                p2.fetch([v for v in vp3.values()], 0x28)
                V2 = {i: 解值(a) for i, a in vp3.items()}
                globals()["p"] = 旧p
                隔 = 时2 - 时1
                print("  技能 %-8s obj=0x%X  %d 条  两次相距 %.2f 秒" % (sid, vv, n2, 隔))
                动 = []
                for i in V1:
                    if i not in V2 or i not in 名3:
                        continue
                    a, b = V1[i][1], V2[i][1]
                    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a != b:
                        动.append((i, 名3[i], a, b, b - a))
                if not 动:
                    print("     没有数值在变 —— 冷却可能没在走，或不在这个对象上")
                for i, nm, a, b, dd in sorted(动, key=lambda x: -abs(x[4])):
                    判 = ""
                    if abs(dd + 隔) < max(0.6, 隔 * 0.2):
                        判 = "<<< 按秒递减，像剩余冷却"
                    elif abs(dd - 隔) < max(0.6, 隔 * 0.2):
                        判 = "<<< 按秒递增，像已过时间"
                    print("     %-30s %14.4f -> %14.4f  %+9.4f %s" % (nm, a, b, dd, 判))
                continue
            名2, vp2, n2 = 键值表(sd)
            选 = [i for i, s in 名2.items()
                 if ALL or any(g in s.lower() for g in GREP)]
            选.sort()
            p.fetch([vp2[i] for i in 选 if i in vp2], 0x40)
            print("  技能 %-8s obj=0x%X  %d 条属性, 命中 %d 条" % (sid, vv, n2, len(选)))
            for i in 选:
                if i not in vp2:
                    print("     %-30s <空>" % 名2[i])
                    continue
                类, 值 = 解值(vp2[i])
                print("     %-30s %-8s %s"
                      % (名2[i], 类, "?" if 值 is None else repr(值)))


for 轮 in range(LOOP):
    一轮()
    if 轮 + 1 < LOOP:
        time.sleep(GAP)
