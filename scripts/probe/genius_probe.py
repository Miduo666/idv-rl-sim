# -*- coding: utf-8 -*-
r"""专查 genius_id_lv_lst 到底是"真的空"还是"读不到"。

起因：pyw.list_items() 在读失败和真空列表两种情况下都返回 []，
拿它下结论会把"读不到"误判成"这人没天赋/列表被清空"。
这里每一步都单独报告成败，不做任何吞掉错误的简化。

    python genius_probe.py [--type 2] [--loop 3] [--gap 2]
"""
import json
import os
import struct
import sys
import subprocess
import time

sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from pyw import Py
from idv_probe import discover

MASK = 0x00FFFFFFFFFFFFFF
SYS_MODULES_OFF = 0xA7029E8
PYLONG_T_OFF = 0xA026498
ADB = r"C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_cache.json")


def arg(n, d):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


UTYPE = int(arg("--type", 2))
LOOP = int(arg("--loop", 3))
GAP = float(arg("--gap", 2))

cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
pid, libbase, bss, maps = discover()
LONG_T = libbase + PYLONG_T_OFF


def 内存压力():
    try:
        s = subprocess.run([ADB, "shell", "su -c 'cat /proc/%d/status'" % pid],
                           capture_output=True, text=True, timeout=20).stdout
        rss = swap = "?"
        for ln in s.splitlines():
            if ln.startswith("VmRSS"):
                rss = ln.split()[1]
            elif ln.startswith("VmSwap"):
                swap = ln.split()[1]
        return "VmRSS=%s kB  VmSwap=%s kB" % (rss, swap)
    except Exception as e:
        return "取不到(%s)" % e


def 一轮(p):
    SM = p.qf(libbase + SYS_MODULES_OFF)
    _, mod = p.dget(SM, "game_kernel", cache.get("mod"))
    _, UM = p.dget(p.qf(mod + 0x10), "unit_mgr", cache.get("unit_mgr"))
    _, UBT = p.dget(p.inst_dict(UM), "units_by_type", cache.get("units_by_type"))
    if not UBT:
        print("  拿不到 units_by_type，多半不在对局中")
        return
    lst = None
    for _, nm, v in p.dict_pairs(UBT):
        if p.longval(nm) == UTYPE:
            lst = v
            break
    if not lst:
        print("  units_by_type 里没有键 %d" % UTYPE)
        return

    for o in p.list_items(lst):
        d = p.inst_dict(o)
        if not d:
            continue
        ent0, step, nent = p.dict_raw(d)
        if not ent0:
            continue
        键off = 0 if step == 16 else 8
        值off = 8 if step == 16 else 16
        p.fetch([ent0], nent * step)
        blk = p.get(ent0, nent * step)
        if not blk:
            print("  单位 0x%X: entries 读不到" % o)
            continue
        目标 = None
        kps = {}
        for i in range(nent):
            k = struct.unpack_from("<Q", blk, i * step + 键off)[0] & MASK
            if 0x7000000000 < k < 0x8000000000:
                kps[i] = k
        p.fetch(list(kps.values()), 0x60)
        for i, k in kps.items():
            if p.pystr(k) == "genius_id_lv_lst":
                目标 = i
                break
        if 目标 is None:
            print("  单位 0x%X: 没有 genius_id_lv_lst 这个属性" % o)
            continue

        vp = struct.unpack_from("<Q", blk, 目标 * step + 值off)[0] & MASK
        报 = "  单位 0x%-13X #%-5d 值指针=0x%X" % (o, 目标, vp)
        if not (0x7000000000 < vp < 0x8000000000):
            print(报 + "   << 值指针本身无效")
            continue
        # 关键：分开报告"对象头读不到" 和 "ob_size 真的是 0"
        p.fetch([vp], 0x20)
        h = p.get(vp, 0x20)
        if not h:
            print(报 + "   << **对象头读不到(页换出?)** —— 不是空列表")
            continue
        rc = struct.unpack_from("<q", h, 0)[0]
        n = struct.unpack_from("<q", h, 0x10)[0]
        it = struct.unpack_from("<Q", h, 0x18)[0] & MASK
        报 += "  refcount=%d ob_size=%d ob_item=0x%X" % (rc, n, it)
        if rc <= 0:
            print(报 + "   << refcount 异常，对象已废")
            continue
        if n == 0:
            print(报 + "   << **ob_size 真的是 0，列表确实为空**")
            continue
        if not (0x7000000000 < it < 0x8000000000):
            print(报 + "   << ob_item 指针无效")
            continue
        p.fetch([it], n * 8)
        ib = p.get(it, n * 8)
        if not ib:
            print(报 + "   << **元素数组读不到(页换出?)**")
            continue
        内层好 = 内层坏 = 0
        ids = []
        项 = [struct.unpack_from("<Q", ib, j * 8)[0] & MASK for j in range(n)]
        p.fetch([x for x in 项 if 0x7000000000 < x < 0x8000000000], 0x20)
        for x in 项:
            if not (0x7000000000 < x < 0x8000000000):
                内层坏 += 1
                continue
            hb = p.get(x, 0x20)
            if not hb:
                内层坏 += 1
                continue
            m = struct.unpack_from("<q", hb, 0x10)[0]
            mi = struct.unpack_from("<Q", hb, 0x18)[0] & MASK
            if m < 1 or not (0x7000000000 < mi < 0x8000000000):
                内层坏 += 1
                continue
            p.fetch([mi], 8)
            eb = p.get(mi, 8)
            if not eb:
                内层坏 += 1
                continue
            kp = struct.unpack_from("<Q", eb, 0)[0] & MASK
            v = p.longval(kp)
            if v is None:
                内层坏 += 1
            else:
                内层好 += 1
                ids.append(v)
        print(报 + "   内层 %d 好 / %d 坏   ids=%s" % (内层好, 内层坏, sorted(ids)))


for 轮 in range(LOOP):
    print("\n===== 第 %d 轮  %s =====" % (轮 + 1, 内存压力()))
    一轮(Py(pid, libbase))          # 每轮新建，绕开读缓存
    if 轮 + 1 < LOOP:
        time.sleep(GAP)
