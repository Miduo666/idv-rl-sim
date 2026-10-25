# -*- coding: utf-8 -*-
r"""找"本机玩家/当前视角"的标识：读 game_kernel 的 g_unit，并与 units_by_type 对照。

    python py_self.py                 走一遍链路，打印 g_unit 和全部玩家单位
    python py_self.py --loop 8 --gap 4  连续采样(录像里切视角时用，看 g_unit 变不变)
    python py_self.py --names           额外列出 game_kernel 的全部属性名，找别的候选标识

链路(见 python-layer.md 第二节)：
    libbase+0xA7029E8 -> sys.modules -> "game_kernel" -> md_dict
      -> "g_unit"        本机玩家实例
      -> "unit_mgr" -> "units_by_type" -> 键1=监管 键2=求生者

玩家实例 -> "model" -> +0x20 = 场景对象指针，就是绘制数组里那个 obj。
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

# 玩家单位上想读的属性。key 是属性名，值是 chain_cache 里的 hint 键名。
关心 = ["uid", "unit_type", "model", "position", "player_name", "name",
        "is_self", "is_local", "camp", "pid", "unique_id"]

# 在 game_kernel 属性名里，长得像"自身/视角"标识的关键字
候选词 = ("self", "local", "my", "main", "cur", "view", "camera", "观", "g_unit",
        "observ", "replay", "video", "watch", "follow", "focus", "target")


def arg(n, d):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


LOOP = int(arg("--loop", 1))
GAP = float(arg("--gap", 4))
列名 = "--names" in sys.argv

cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
脏 = False
pid, libbase, bss, maps = discover()
print("pid=%d libbase=0x%X\n" % (pid, libbase))


def 存缓存():
    if 脏:
        json.dump(cache, open(CACHE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


class 会话:
    """一轮采样。每轮新建 Py 以绕开读缓存。"""

    def __init__(self):
        self.p = Py(pid, libbase)
        self.LONG_T = libbase + PYLONG_T_OFF
        self.FLOAT_T = libbase + PYFLOAT_T_OFF
        self.STR_T = libbase + PYSTR_T_OFF

    def 类型名(self, obj):
        tp = self.p.qf(obj + 8)
        if not tp:
            return "?"
        n = self.p.qf(tp + 0x18)
        if not n:
            return "?"
        self.p.fetch([n], 0x60)
        s = self.p.get(n, 64)
        return s.split(b"\0")[0].decode("utf-8", "replace") if s else "?"

    def 解值(self, vp, 深=0):
        if not vp or not (0x7000000000 < vp < 0x8000000000):
            return None
        self.p.fetch([vp], 0x40)
        b = self.p.get(vp, 0x28)
        if not b:
            return "<读不到>"
        if struct.unpack_from("<q", b, 0)[0] <= 0:
            return "<refcount异常>"
        tp = struct.unpack_from("<Q", b, 8)[0] & MASK
        if tp == self.FLOAT_T:
            return struct.unpack_from("<d", b, 16)[0]
        if tp == self.LONG_T:
            sz = struct.unpack_from("<q", b, 16)[0]
            if sz == 0:
                return 0
            d = struct.unpack_from("<I", b, 24)[0]
            return d if sz > 0 else -d
        if tp == self.STR_T:
            return self.p.pystr(vp)
        名 = self.类型名(vp)
        if 名 == "bool":
            # True/False 是单例，用 ob_size 区分(False 的 digit 为 0)
            return bool(struct.unpack_from("<I", b, 24)[0]) if \
                struct.unpack_from("<q", b, 16)[0] else False
        if 名 == "NoneType":
            return None
        if 名 in ("list", "tuple") and 深 < 1:
            return [self.解值(x, 深 + 1) for x in self.p.list_items(vp)]
        return "<%s 0x%X>" % (名, vp)

    def 属性(self, 实例, 名, 类键):
        """按名字取属性值指针，带 hint 缓存 + 名字校验。"""
        d = self.p.inst_dict(实例)
        if not d:
            return None
        键 = "%s.%s" % (类键, 名)
        i, v = self.p.dget(d, 名, cache.get(键))
        if i is not None and cache.get(键) != i:
            cache[键] = i
            globals().__setitem__("脏", True)
        return v

    def 读玩家(self, 实例, 类键=None):
        """返回一个描述 dict。"""
        类名 = self.类型名(实例)
        类键 = 类键 or 类名
        out = {"addr": 实例, "cls": 类名}
        d = self.p.inst_dict(实例)
        if not d:
            out["err"] = "取不到实例 dict"
            return out
        r = self.p.dict_raw(d)
        out["nent"] = r[2] if r else None
        for 名 in 关心:
            v = self.属性(实例, 名, 类键)
            if v is None:
                continue
            out[名] = self.解值(v)
            if 名 == "model" and isinstance(out[名], str) and out[名].startswith("<"):
                # model 是个 C++ 包装对象，+0x20 是场景对象指针
                mp = v
                self.p.fetch([mp], 0x40)
                b = self.p.get(mp + 0x20, 8)
                if b:
                    out["obj"] = struct.unpack("<Q", b)[0] & MASK
        return out

    def 场景对象(self, obj):
        """读场景侧的坐标和两个判据，用来跟叠加层交叉印证。"""
        if not obj or not (0x7000000000 < obj < 0x8000000000):
            return None
        self.p.fetch([obj], 0x300)
        r = {}
        b = self.p.get(obj + 0x240, 4)
        r["+0x240"] = struct.unpack("<I", b)[0] if b else None
        b = self.p.get(obj + 0x1a0, 4)
        r["+0x1a0"] = round(struct.unpack("<f", b)[0], 2) if b else None
        b = self.p.get(obj + 0x6d, 1)
        r["+0x6D"] = b[0] if b else None
        b = self.p.get(obj + 0x70, 4)
        r["+0x70"] = struct.unpack("<I", b)[0] if b else None
        co = self.p.qf(obj + 0x28)
        if co:
            self.p.fetch([co], 0x100)
            b = self.p.get(co + 0xa0, 12)
            if b:
                x, z, y = struct.unpack("<fff", b)
                r["坐标"] = (round(x, 1), round(y, 1), round(z, 1))
        return r

    def 走链(self):
        SM = self.p.qf(libbase + SYS_MODULES_OFF)
        if not SM:
            return None, None, "sys.modules 读不到(静态根可能因热更失效)"
        i, mod = self.p.dget(SM, "game_kernel", cache.get("mod"))
        if not mod:
            return None, None, "sys.modules 里没有 game_kernel"
        if cache.get("mod") != i:
            cache["mod"] = i
            globals().__setitem__("脏", True)
        return self.p.qf(mod + 0x10), mod, None


def 一轮(首轮):
    s = 会话()
    md, mod, err = s.走链()
    if err:
        print("!! " + err)
        return None
    if 首轮 and 列名:
        print("game_kernel md_dict 全部属性：")
        名表 = s.p.dict_names(md)
        print("  共 %d 条可读名字" % len(名表))
        for i, nm, v in 名表:
            标 = " <==" if any(w in nm.lower() for w in 候选词) else ""
            if 标 or 首轮 == 2:
                print("   #%-4d %-34s 0x%X%s" % (i, nm, v, 标))
        print()

    # --- g_unit
    i, g = s.p.dget(md, "g_unit", cache.get("g_unit"))
    if g and cache.get("g_unit") != i:
        cache["g_unit"] = i
        globals().__setitem__("脏", True)
    if not g:
        print("!! game_kernel 里没有 g_unit(不在对局/录像中？)")
        gi = None
    else:
        info = s.读玩家(g, "self")
        gi = info
        print("g_unit  #%s  实例=0x%X  类=%s  (%s 条属性)"
              % (i, g, info["cls"], info.get("nent")))
        for k in 关心:
            if k in info:
                print("    %-12s %s" % (k, info[k]))
        if info.get("obj"):
            print("    %-12s 0x%X   场景侧 %s"
                  % ("-> 场景obj", info["obj"], s.场景对象(info["obj"])))
    print()

    # --- units_by_type 对照
    _, UM = s.p.dget(md, "unit_mgr", cache.get("unit_mgr"))
    if not UM:
        print("!! 拿不到 unit_mgr")
        return gi
    _, UBT = s.p.dget(s.p.inst_dict(UM), "units_by_type", cache.get("units_by_type"))
    if not UBT:
        print("!! 拿不到 units_by_type，多半不在对局中")
        return gi
    for _, kp, lst in s.p.dict_pairs(UBT):
        t = s.p.longval(kp)
        if t not in (1, 2):          # 只看监管和求生者
            continue
        items = s.p.list_items(lst)
        print("units_by_type[%d]  %d 个:" % (t, len(items)))
        for o in items:
            d = s.读玩家(o, "player%d" % t)
            标 = "  ★g_unit" if g and o == g else ""
            行 = "   0x%X %-18s" % (o, d["cls"])
            for k in ("uid", "player_name", "name", "unique_id"):
                if k in d and d[k] is not None:
                    行 += " %s=%s" % (k, d[k])
            if d.get("obj"):
                行 += "  obj=0x%X" % d["obj"]
            print(行 + 标)
            if d.get("obj"):
                print("        场景侧 %s" % s.场景对象(d["obj"]))
        print()
    return gi


上一轮 = None
for 轮 in range(LOOP):
    if LOOP > 1:
        print("=" * 72)
        print("第 %d/%d 轮   %s" % (轮 + 1, LOOP, time.strftime("%H:%M:%S")))
        print("=" * 72)
    t = time.time()
    cur = 一轮(轮 == 0)
    print("[%.1f 秒]" % (time.time() - t))
    if 上一轮 and cur:
        变 = [k for k in set(上一轮) | set(cur)
              if 上一轮.get(k) != cur.get(k)]
        print(">>> g_unit 与上一轮相比：%s"
              % ("没有变化" if not 变 else "变了 " + ", ".join(sorted(map(str, 变)))))
    上一轮 = cur or 上一轮
    存缓存()
    if 轮 + 1 < LOOP:
        print("\n等待 %.1f 秒(现在切视角)...\n" % GAP)
        time.sleep(GAP)
