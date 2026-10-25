# -*- coding: utf-8 -*-
"""
第五人格 (com.netease.dwrg) PC 侧活体探针 —— 不改代码、不重编译，纯只读验证偏移。

它自己发现 pid / libbase / bss 段 / 两个签名位置，然后把整条链走一遍并打分，
一次运行就能回答"游戏更新后到底是哪一层坏了"。

用法:
    python idv_probe.py            # 全量：链路 + 对象表 + 相机偏移
    python idv_probe.py quick      # 只验链路，不读对象（最快，几秒）
    python idv_probe.py --redump   # 强制重新 dump bss（默认复用本地缓存）

前提: 设备已 root(Magisk `su -c` 可用)、游戏在**前台**运行。
      后台时页面会被换到 zram，本工具会拒读以免制造缺页，见 README。
"""
import os, sys, re, struct, subprocess, collections

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
from devread import Mem, sh, ADB, PAGE, TMP   # TMP: 纯ASCII临时目录，adb 拉不动中文路径

PKG = "com.netease.dwrg"
MASK = 0x00FFFFFFFFFFFFFF
MAT_SIG = 0x656A624F72655028          # "(PerObje"，属于字符串 "(PerObjectParamBuffer"
PTR_MIN = 0x5000000000
# 上界不可省：只判下界的话，浮点垃圾(如 0x400674954293DF)也会被当成合法指针，
# 导致矩阵链"多出"一堆假槽位。本机用户态指针都落在 0x77xx/0x79xx 段。
PTR_MAX = 0x8000000000


# ---------------------------------------------------------------- 环境发现
def discover():
    pid = sh("pidof %s" % PKG).decode(errors="replace").split()
    if not pid:
        sys.exit("游戏没在运行")
    pid = int(pid[0])
    maps = sh("cat /proc/%d/maps" % pid).decode(errors="replace").splitlines()

    libbase = None
    bss = None
    seen_module = False
    for ln in maps:
        p = ln.split()
        if not p or "-" not in p[0]:
            continue
        a, b = (int(x, 16) for x in p[0].split("-"))
        if "libclient.so" in ln:
            if libbase is None and "r-xp" in ln:
                libbase = a
            seen_module = True
            continue
        # 复刻 get_module_bss: 模块行之后第一个 rw 且 >=2800 页的段（实际是 [anon:.bss]）
        if seen_module and bss is None and "rw" in p[1] and (b - a) // PAGE >= 2800:
            bss = (a, b, ln.strip())
    if libbase is None or bss is None:
        sys.exit("没找到 libclient.so 基址或 bss 段")
    return pid, libbase, bss, maps


def dump_bss(pid, bss, redump):
    path = os.path.join(TMP, "bss_%d.bin" % pid)
    npg = (bss[1] - bss[0]) // PAGE
    if redump or not os.path.exists(path) or os.path.getsize(path) != npg * PAGE:
        sh("dd if=/proc/%d/mem of=/data/local/tmp/bss.bin bs=4096 skip=%d count=%d 2>/dev/null; "
           "chmod 666 /data/local/tmp/bss.bin" % (pid, bss[0] // PAGE, npg))
        subprocess.run([ADB, "pull", "/data/local/tmp/bss.bin", path], capture_output=True)
    return open(path, "rb").read()


# ---------------------------------------------------------------- 签名定位
def find_sigs(d, base, libbase):
    out = {}
    o = d.find(struct.pack("<Q", MAT_SIG))
    while o != -1:
        if (base + o) % 8 == 0:                    # 原代码只扫8字节对齐
            out.setdefault("matrix", []).append(base + o)
        o = d.find(struct.pack("<Q", MAT_SIG), o + 1)

    arr = []
    for p in range(16, len(d) - 64, 8):
        if struct.unpack_from("<Q", d, p)[0] != 16384:
            continue
        if struct.unpack_from("<I", d, p - 8)[0] != 257:
            continue
        if abs(struct.unpack_from("<f", d, p - 16)[0] - 1.0) > 1e-9:
            continue
        arr.append(base + p + 56)                  # 原代码: 命中处 +56 = 数组头
    out["array"] = arr
    return out


# ---------------------------------------------------------------- 矩阵链
def resolve_matrix(m, sigaddr):
    """在窗口内找能走通整条链的槽位，返回 [(槽位偏移, 根, Matrix)]"""
    m.fetch([sigaddr + o for o in range(0x200, 0x600, 8)], "")
    hits = []
    for off in range(0x200, 0x600, 8):
        p1 = m.q(sigaddr + off)
        if not p1 or not (PTR_MIN < (p1 & MASK) < PTR_MAX):
            continue
        m.fetch([(p1 & MASK) + 0xa58], "")
        p2 = m.q((p1 & MASK) + 0xa58)
        if not p2 or not (PTR_MIN < (p2 & MASK) < PTR_MAX):
            continue
        hits.append((off, p1 & MASK, (p2 & MASK) + 0x2c0))
    return hits


def cam_from_matrix(m, MAT):
    r = [m.f(MAT + i * 4) for i in range(16)]
    if any(x is None for x in r):
        return None, None
    A = [r[0:3], r[4:7], r[8:11]]
    t = r[12:15]
    a, b, c = A[0]; d, e, f = A[1]; g, h, k = A[2]
    det = a * (e * k - f * h) - b * (d * k - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-9:
        return None, r
    adj = [[(e * k - f * h), (c * h - b * k), (b * f - c * e)],
           [(f * g - d * k), (a * k - c * g), (c * d - a * f)],
           [(d * h - e * g), (b * g - a * h), (a * e - b * d)]]
    cam = [-sum(t[i] * adj[i][j] / det for i in range(3)) for j in range(3)]
    return cam, r


def find_cam_offset(m, MAT, cam):
    m.fetch([MAT + o for o in range(-0x400, 0x40, PAGE)] + [MAT - 0x400, MAT], "")
    best, besterr = None, 1e9
    allhits = []
    for off in range(-0x400, -0x40, 4):
        v = [m.f(MAT + off + i * 4) for i in range(3)]
        if any(x is None or not (-1e5 < x < 1e5) for x in v):
            continue
        err = sum(abs(v[i] - cam[i]) for i in range(3))
        if err < 60:
            allhits.append((err, off, v))
        if err < besterr:
            best, besterr = off, err
    allhits.sort()
    return best, besterr, allhits


# ---------------------------------------------------------------- 对象表
def read_objects(m, head):
    m.fetch([head, head + 8], "")
    a, e = m.q(head), m.q(head + 8)
    if a is None or e is None:
        return None
    a &= MASK; e &= MASK
    n = (e - a) // 8 if e > a else -1
    if not (0 < n < 20000):
        return dict(count=n, objs=[])
    m.fetch([a + i * 8 for i in range(n)], "")
    objs = []
    for i in range(n):
        v = m.q(a + i * 8)
        if v and (v & MASK) > PTR_MIN:
            objs.append(v & MASK)
    m.fetch([o + k for o in objs for k in (0, 0x100, 0x200)], "")
    return dict(count=n, arr=a, objs=objs)


def class_names(m, objs):
    lvl = [(o, m.q(o + 0xf8)) for o in objs]
    for add in (0x0, 0x8, 0x20, 0x20):
        m.fetch([(v & MASK) + add for _, v in lvl if v], "")
        lvl = [(o, (m.q((v & MASK) + add) if v else None)) for o, v in lvl]
    m.fetch([(v & MASK) for _, v in lvl if v], "")
    strs = []
    for o, v in lvl:
        if not v:
            continue
        p = v & MASK
        s, L = m.q(p + 0x8), m.q(p + 0x10)
        if s and L and 0 < (L & 0xFFFFFFFF) < 512:
            strs.append((o, s & MASK, L & 0xFFFFFFFF))
    m.fetch([a + k for _, a, L in strs for k in (0, L)], "")
    out = {}
    for o, a, L in strs:
        b = m.get(a, L)
        if b:
            out[o] = b.decode("utf-8", "replace")
    return out


# ---------------------------------------------------------------- 主流程
def main():
    quick = "quick" in sys.argv
    redump = "--redump" in sys.argv

    pid, libbase, bss, maps = discover()
    print("pid=%d  libbase=0x%X  bss=0x%X-0x%X (%d页)  maps=%d行"
          % (pid, libbase, bss[0], bss[1], (bss[1] - bss[0]) // PAGE, len(maps)))

    d = dump_bss(pid, bss, redump)
    sigs = find_sigs(d, bss[0], libbase)
    print("\n[签名] 矩阵签名命中 %d 处, 数组签名命中 %d 处"
          % (len(sigs.get("matrix", [])), len(sigs["array"])))
    for a in sigs.get("matrix", []):
        print("   矩阵签名 0x%X  (模块相对 +0x%X)" % (a, a - libbase))
    for a in sigs["array"]:
        print("   数组头   0x%X  (模块相对 +0x%X)" % (a, a - libbase))
    if not sigs.get("matrix"):
        print("   !! 矩阵签名消失 —— 这才是真正的引擎大改，需要活体数值扫描重找")

    m = Mem(pid)

    # ---- 矩阵链 ----
    MAT = None
    for sa in sigs.get("matrix", []):
        hits = resolve_matrix(m, sa)
        print("\n[矩阵链] 签名 0x%X 窗口内可用槽位 %d 个" % (sa, len(hits)))
        for off, root, mat in hits:
            print("   +0x%03X -> 根=0x%X -> Matrix=0x%X%s"
                  % (off, root, mat, "   (旧版写死的是 +0x430)" if off == 0x430 else ""))
        if hits:
            MAT = hits[-1][2]

    cam = None
    if MAT:
        m.fetch([MAT, MAT + 0x40], "")
        cam, row = cam_from_matrix(m, MAT)
        if row:
            print("\n[VP矩阵] 0x%X" % MAT)
            for r in range(4):
                print("   " + " ".join("%11.4f" % row[r * 4 + c] for c in range(4)))
        if cam:
            print("   矩阵反解相机 = (%.2f, %.2f, %.2f)" % tuple(cam))
            best, err, allh = find_cam_offset(m, MAT, cam)
            print("   相机字段候选(误差<60):")
            for e2, off, v in allh[:8]:
                print("      Matrix%+#07x = (%9.2f,%7.2f,%9.2f) 误差%.2f%s"
                      % (off, v[0], v[1], v[2], e2,
                         "   <<< 旧版写死的位置" if off == -0x290 else ""))
            if not allh:
                print("      无候选 —— 相机字段可能已挪出窗口")

    if quick:
        return

    # ---- 对象表 ----
    for head in sigs["array"]:
        r = read_objects(m, head)
        if r is None or not r["objs"]:
            print("\n[数组 0x%X] 不可用 (count=%s)" % (head, r["count"] if r else "?"))
            continue
        objs = r["objs"]
        names = class_names(m, objs)
        m.fetch([(m.q(o + 0x28) & MASK) + k for o in objs if m.q(o + 0x28) for k in (0, 0xa0)], "")
        print("\n[数组 0x%X] count=%d 有效指针=%d 类名读出=%d"
              % (head, r["count"], len(objs), len(names)))

        dist = collections.Counter()
        players = []
        for o in objs:
            f = m.f(o + 0x1a0)
            if f is None:
                continue
            dist[round(f, 1)] += 1
            if f == 450.0:
                c = m.q(o + 0x28)
                cc = (c & MASK) if c else 0
                xyz = [m.f(cc + 0xa0 + i * 4) for i in range(3)] if cc else [None] * 3
                players.append((o, xyz, names.get(o, "")))
        print("   +0x1a0 值分布:", dict(dist.most_common(6)),
              "   (450=玩家角色, 500=场景可交互物, 0=普通场景模型)")
        print("   +0x1a0==450 的对象 %d 个 —— 应等于本局真人+人机总数:" % len(players))
        for o, xyz, nm in players:
            print("      0x%X %s %s" % (
                o, ("(%8.1f,%6.2f,%8.1f)" % tuple(xyz))
                if all(v is not None for v in xyz) else "坐标N/A".ljust(26),
                nm[:66]))


if __name__ == "__main__":
    main()
