# -*- coding: utf-8 -*-
"""physx_collision 适配层自测：用假 CollisionConst（常量取自本机 t_colconst.py 的真实输出）+ 合成 .scn_col，
测射线/扫掠/静态测试/路径相交的过滤语义、返回结构、动态体同步与形状约定。不需要游戏脚本和资源。用法: python t_physx.py"""
import sys, os, types, zipfile, tempfile, struct, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "natives"), HERE]
import numpy as np
import colworld

cc = types.ModuleType("common_cs.CollisionConst")
cc.Group = types.SimpleNamespace(STATIC_BODY=1, DYNAMIC_BODY=2, VIRTUAL_BODY=4, ROLE=8)
cc.Layer = types.SimpleNamespace(NORMAL=1, ALL=65535)
cc.EXCLUDE_FILTER, cc.INCLUDE_FILTER = 1, 0
pkg = types.ModuleType("common_cs"); pkg.CollisionConst = cc
sys.modules["common_cs"] = pkg; sys.modules["common_cs.CollisionConst"] = cc

# ---- 合成地图（同 t_colworld.py）：地板 100×100 + x∈[19,21] 的墙 + 旋转 45° 的箱子 ----
def pack_obj(verts, idx, mat=None, pos=None):
    b = struct.pack("<4I", 1, 0, 1, len(verts)) + b"".join(struct.pack("<3f", *v) for v in verts)
    nt = len(idx) // 3
    b += struct.pack("<I", nt) + struct.pack("<%dI" % nt, *([0] * nt))
    b += struct.pack("<I", len(idx)) + struct.pack("<%dI" % len(idx), *idx)
    if mat is not None:
        b += struct.pack("<I16f", 4, *mat)
    if pos is not None:
        b += struct.pack("<I3f", 3, *pos)
    return b


def box_mesh(hx, hy, hz):
    T = colworld.box_tris((0, 0, 0), (hx, hy, hz))
    V = [tuple(v) for v in T.reshape(-1, 3)]
    return V, list(range(len(V)))


def roty(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    # 行向量约定：v' = v·M；绕 Y 轴
    return (c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1)


# ---- 合成地图：地板 100×100（细分成 20×20 网格，跨很多格子）+ x=20 处的墙 + 旋转 45° 的箱子 ----
fv, fi = [], []
N = 20
for i in range(N + 1):
    for j in range(N + 1):
        fv.append((-50 + 100.0 * i / N, 0.0, -50 + 100.0 * j / N))
for i in range(N):
    for j in range(N):
        a = i * (N + 1) + j
        fi += [a, a + 1, a + N + 2, a, a + N + 2, a + N + 1]
data = pack_obj(fv, fi)
wv, wi = box_mesh(1, 15, 50)
data += pack_obj(wv, wi, mat=(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1), pos=(20, 15, 0))   # 墙面 x∈[19,21]
bv, bi = box_mesh(4, 4, 4)
data += pack_obj(bv, bi, mat=roty(45), pos=(-20, 4, -20))

zp = os.path.join(tempfile.mkdtemp(), "fake_res.zip")
with zipfile.ZipFile(zp, "w") as z:
    z.writestr("m/f.scn_col", data)
os.environ["IDV_RES_ZIP"] = zp
import physx_collision as pc
V = pc.vector
ok = []


def chk(name, cond, extra=""):
    ok.append(bool(cond)); print(("ok  " if cond else "FAIL"), name, extra)


def chk_ray(name, r, hit):
    """射线/扫掠返回必须是 6 元组，[0] 与期望的命中与否一致。"""
    chk(name, len(r) == 6 and bool(r[0]) == hit, r[:3])


print("== 射线与过滤（静态地图属性用推断默认值）")
sc = pc.scene_col(); sc.load("m/f.scn_col")
s, e, short = V(0, 10, 0), V(40, 10, 0), V(10, 10, 0)
r = sc.hit_by_ray_new(s, e, 0, 332, set(), {1, 2}, 1, 1); chk_ray("RoleFilter 形(EXCLUDE 332,{1,2}) 打墙", r, True)
if r[0]: print("     命中点 x=%.3f 法线=%r cid=%s group=%s" % (r[1].x, r[2], r[5].cid, r[5].group))
chk_ray("INCLUDE group0 extra{146} → 地图不在内", sc.hit_by_ray_new(s, e, 0, 0, set(), {146}, 1, 0), False)
chk_ray("INCLUDE group=STATIC → 打到", sc.hit_by_ray(s, e, 0, 1, 1, 0), True)
chk_ray("EXCLUDE group=STATIC → 穿过", sc.hit_by_ray(s, e, 0, 1, 1, 1), False)
chk_ray("层不匹配 → 穿过", sc.hit_by_ray(s, e, 0, 0, 2, 1), False)
chk_ray("5 参数无过滤 → 打到", sc.hit_by_ray(s, e, 0, 0, 1), True)
chk_ray("够不到 → 未命中", sc.hit_by_ray(s, short, 0, 0, 1), False)
pc.set_default_filter_info(1, 1, 146, 0)
chk_ray("set_default_filter_info 给 utype=146 后 INCLUDE{146} → 打到", sc.hit_by_ray_new(s, e, 0, 0, set(), {146}, 1, 0), True)
chk_ray("同上 ignore{146}+EXCLUDE group=STATIC → ignore 优先，打到", sc.hit_by_ray_new(s, e, 0, 1, {146}, set(), 1, 1), True)

print("== 动态体 / 扫掠 / 静态测试（静态地图属性同游戏 preset_collision_module）")
pc.set_default_filter_info(65535, 1, 65535)
sc = pc.scene_col(); sc.load("m/f.scn_col")
# 动态球（如子弹）：ROLE 组，层 NORMAL
ball = pc.col_object(0, V(2, 2, 2), 1, 8, 0, False, 1); ball.position = V(10, 10, 0); sc.add_object(ball)
r = sc.hit_by_ray(V(0, 10, 0), V(40, 10, 0), 0, 0, 1, 1)
chk("射线先打到动态球（球面 x≈8）", r[0] and r[5] is ball and 7.7 < r[1].x <= 8.0, r[:2])
r = sc.hit_by_ray(V(0, 10, 0), V(40, 10, 0), 0, 8, 1, 1)
chk("EXCLUDE ROLE → 穿过球打到墙", r[0] and r[5] is not ball and abs(r[1].x - 19) < 1e-6, r[:2])
r = sc.hit_by_ray_new(V(0, 10, 0), V(40, 10, 0), 0, 0, set(), {1}, 1, 1)
chk("EXCLUDE extra{类型1} → 穿过球", r[0] and r[5] is not ball, r[:2])
ball.position = V(10, 30, 0)
r = sc.hit_by_ray(V(0, 10, 0), V(40, 10, 0), 0, 0, 1, 1)
chk("球移走后（改 position，下一次查询自动同步）→ 打到墙", r[0] and abs(r[1].x - 19) < 1e-6)

# 球作查询体：扫掠 / 零长度 / 静态测试 / 路径相交
probe = pc.col_object(0, V(3, 3, 3), 2, 8, 0, False, 1)
r = sc.sweep_test_new(probe, V(0, 10, 0), V(40, 10, 0), 8, set(), set(), 1, 0, 1)
chk("球扫向墙 → 命中点 x=19、法线 -x", r[0] and abs(r[1].x - 19) < 1e-3 and abs(r[2].x + 1) < 1e-6, r[:3])
r = sc.sweep_test(probe, V(0, 2, 0), V(0, 2, 0), 0, 1, 0, 1)
chk("零长度扫掠压地板 → [-1] 是碰撞体列表", r[0] and isinstance(r[-1], list) and len(r[-1]) == 1, r)
r = sc.sweep_test(probe, V(0, 10, 0), V(0, 10, 0), 0, 1, 0, 1)
chk("零长度扫掠悬空 → [-1] 为 None", (not r[0]) and r[-1] is None)
probe.position = V(17, 10, 0)
chk("static_test 贴墙 → [静态碰撞体]", [o.unit_type for o in sc.static_test(probe, 0, 1, 1)] == [65535])
probe.position = V(0, 10, 0)
chk("static_test 悬空 → []", sc.static_test_new(probe, 0, set(), set(), 1, 1) == [])
res = sc.sweep_intersect(probe, V(0, 10, 0), V(40, 10, 0), 0, 1, 1)
chk("sweep_intersect 穿墙 → 含静态碰撞体", len(res) == 1 and res[0].unit_type == 65535, res)

# 盒子（已登记：半长 + rotation_matrix）
box = pc.col_object(1, V(1, 5, 3), 3, 2, 0, False, 1); box.position = V(5, 10, 0); sc.add_object(box)
r = sc.hit_by_ray(V(0, 10, 0), V(40, 10, 0), 0, 0, 1, 1)
chk("动态盒子挡射线（半长 1 → x=4）", r[0] and r[5] is box and abs(r[1].x - 4) < 1e-6, r[:2])
box.rotation_matrix = pc.matrix(0, 0, -1, 0,  0, 1, 0, 0,  1, 0, 0, 0,  0, 0, 0, 1)   # 绕 Y 90°：x 半长变 3
r = sc.hit_by_ray(V(0, 10, 0), V(40, 10, 0), 0, 0, 1, 1)
chk("旋转后（x 方向半长 3 → x=2）", r[0] and abs(r[1].x - 2) < 1e-6, r[:2])
sc.remove_object(box)
qbox = pc.col_object(1, V(2, 1.5, 2), 3, 2, 0, False, 1); qbox.position = V(0, 1, 0)
chk("盒子 static_test 压地板 → [静态]", [o.unit_type for o in sc.static_test(qbox, 0, 1, 1)] == [65535])
qbox.position = V(0, 5, 0)
chk("盒子 static_test 悬空 → []", sc.static_test(qbox, 0, 1, 1) == [])
r = sc.sweep_test(qbox, V(0, 1, 0), V(0, 1, 0), 0, 1, 0, 1)
chk("盒子零长度扫掠压地板 → 列表", r[0] and len(r[-1]) == 1)
r = sc.sweep_test(qbox, V(0, 5, 0), V(40, 5, 0), 0, 1, 0, 1)
chk("盒子连续扫掠 → 未实现，未命中 + 计数", (not r[0]) and pc.UNSUPPORTED.get("sweep_test 盒子扫掠"))
chk("盒子 sweep_intersect 穿墙 → 含静态", [o.unit_type for o in sc.sweep_intersect(qbox, V(0, 10, 0), V(40, 10, 0), 0, 1, 1)] == [65535])
chk("col_size 属性存在", qbox.col_size.y == 1.5)

# 胶囊（角色）：col_conf = (4.5, 15) → size (4.5, 7.5, 4.5)，线段 y∈[中心-7.5, 中心+7.5]
cap = pc.col_object(2, V(4.5, 7.5, 4.5), 2, 8, 0, False, 1); cap.position = V(10, 15, 0); sc.add_object(cap)
r = sc.hit_by_ray(V(0, 15, 0), V(40, 15, 0), 0, 0, 1, 1)
chk("胶囊挡射线（表面 x≈5.5，多面体外接最多大 7%）", r[0] and r[5] is cap and 5.1 <= r[1].x <= 5.5 + 1e-6, r[:2])
r = sc.hit_by_ray(V(0, 15 + 7.5 + 4.5 * 1.072, 0), V(40, 15 + 7.5 + 4.5 * 1.072, 0), 0, 0, 1, 1)
chk("高过胶囊顶（中心+半长+半径×1.072 外接上限）→ 打墙", r[0] and r[5] is not cap)
sc.remove_object(cap)
qcap = pc.col_object(2, V(3, 5, 3), 2, 8, 0, False, 1)
r = sc.sweep_test_new(qcap, V(0, 10, 0), V(40, 10, 0), 0, set(), set(), 1, 0, 1)
chk("胶囊扫向墙 → 命中 x=19、可走到 x=16", r[0] and abs(r[1].x - 19) < 1e-3, r[:3])
r = sc.sweep_test(qcap, V(0, 7, 0), V(0, 7, 0), 0, 1, 0, 1)
chk("胶囊零长度：中心 7、半长 5、半径 3 → 底 -1 压地板", r[0] and len(r[-1]) == 1)
r = sc.sweep_test(qcap, V(0, 9, 0), V(0, 9, 0), 0, 1, 0, 1)
chk("胶囊零长度：中心 9 → 底 1，不碰", not r[0])
qcap.rotation_matrix = pc.matrix(0, -1, 0, 0,  1, 0, 0, 0,  0, 0, 1, 0,  0, 0, 0, 1)   # 局部 Y 转到世界 X
qcap.position = V(10, 4, 0)
chk("胶囊横放（线段沿 x）中心高 4、半径 3 → 不碰地板", sc.static_test(qcap, 0, 1, 1) == [])
qcap.position = V(10, 2, 0)
chk("横放中心高 2 → 压地板", len(sc.static_test(qcap, 0, 1, 1)) == 1)

# 未登记形状：ORG_CAPSULE(7)
oc = pc.col_object(7, V(3, 5, 3), 2, 8, 0, False, 1)
r = sc.sweep_test(oc, V(0, 10, 0), V(40, 10, 0), 0, 1, 0, 1)
chk("ORG_CAPSULE 未登记 → 未命中 + 计数", (not r[0]) and pc.UNSUPPORTED.get("sweep_test 查询体 type=7"), dict(pc.UNSUPPORTED))

# 副本语义 / enable / remove
b2 = pc.col_object(1, V(1, 5, 3), 3, 2, 0, False, 1); b2.position = V(5, 10, 0); sc.add_object(b2)
p_ = b2.position; p_.x = 30                       # 原地改取出来的副本：不应移动碰撞体
r = sc.hit_by_ray(V(0, 10, 0), V(40, 10, 0), 0, 0, 1, 1)
chk("改 position 副本不移动碰撞体", r[5] is b2 and abs(r[1].x - 4) < 1e-6)
b2.enable = False
r = sc.hit_by_ray(V(0, 10, 0), V(40, 10, 0), 0, 0, 1, 1)
chk("enable=False → 不参与", r[5] is not b2)
b2.enable = True
chk("enable=True → 恢复", sc.hit_by_ray(V(0, 10, 0), V(40, 10, 0), 0, 0, 1, 1)[5] is b2)
sc.remove_object(b2)
chk("remove_object → 移出世界", sc.hit_by_ray(V(0, 10, 0), V(40, 10, 0), 0, 0, 1, 1)[5] is not b2)

import time
for i in range(138):
    o = pc.col_object(1, V(1, 5, 2), 3, 2, 0, False, 1); o.position = V(-45 + (i % 12) * 7, 10, -45 + (i // 12) * 7); sc.add_object(o)
for i in range(5):
    o = pc.col_object(2, V(3, 10, 3), 2, 8, 0, False, 1); o.position = V(i, 10, 30); sc.add_object(o)
sc.hit_by_ray(V(0, 10, 0), V(1, 10, 0), 0, 0, 1, 1)
t0 = time.perf_counter()
for k in range(2880):
    sc.hit_by_ray_new(V(-40, 7, -40 + k % 80), V(40, 5, 40 - k % 80), 0, 332, set(), {1, 2}, 1, 1)
dt = time.perf_counter() - t0
print("     143 个碰撞体在场，2880 次射线 %.2fs（%.2f ms/次）" % (dt, dt / 2880 * 1000))

print("\n%s" % ("全部通过" if all(ok) else "失败 %d 项" % ok.count(False)))
sys.exit(0 if all(ok) else 1)
