# -*- coding: utf-8 -*-
"""引擎动画查询的替代：根骨骼位移曲线 + 动画时长，数据来自角色资源包里的 RAWANIMA（animdb_build.py 生成，SKILL §9.13）。
只覆盖服务端/本地服务端会用到的查询（AnimDataComponent READ_FROM_ROOT_MOTION + RootMotionClassicComponent NO_MODEL_MODE）：
  get_reference_to_first_frame_transform(动画, 秒).translation = 根骨骼位移 T(t) - T(0)，模型空间，+z 朝前
  get_anim_length(动画) = 毫秒
依据：录像里翻窗/翻板终点到窗板中心的距离与解码出的根骨骼终点 z 一致（span2 4.72/5.27、slide4 11.35/13.67）。
没有数据的动画按零位移、时长 0 返回并计数（STATS），不抛异常。"""
import os, json, re, collections
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.environ.get("IDV_ANIMDB", os.path.normpath(os.path.join(HERE, "..", "..", "..", "res_pull", "animdb")))

# 模型路径 → 骨骼（推断）：gim 里引用骨骼都是相对路径，按角色大目录共用一份，如
# chr/player/dm65_survivor_m/<角色>/x.gim 引用 ../h55_survivor_m_zbs/h55_survivor_m_zbs.skeleton（gim_scan.py 统计 64 处），
# chr/player/dm65_survivor_w/<角色>/x.gim 引用 ../dm65_survivor_w.skeleton（46 处），厂长一族引用 ../dm65_butcher_ll/dm65_butcher_ll.skeleton。
# gim 里不带自身路径，"哪个 gim 是哪个模型"无法按内容确认，所以这张表是按目录结构推断的。
SKELETON_RULES = (
    (r"^chr/player/dm65_survivor_w/", "dm65_survivor_w"),
    (r"^chr/player/dm65_survivor_m/", "h55_survivor_m_zbs"),
    (r"^chr/player/dm65_survivor_boy/", "dm65_survivor_boy"),
    (r"^chr/player/dm65_survivor_girl/", "dm65_survivor_girl"),
    (r"^chr/boss/butcher/", "dm65_butcher_ll"),
    (r"^chr/boss/ripper/", "ripper"),       # 杰克 h55_ripper_lv1.gim；boss gim 里 ../../ripper.skeleton 30 处（按目录名推断）
)

STATS = collections.Counter()
MISSING = collections.Counter()     # (骨骼, 动画名) 未找到
_TABLES = {}


def skeleton_of(path):
    p = (path or "").replace("\\", "/").lower()
    for pat, sk in SKELETON_RULES:
        if re.match(pat, p):
            return sk
    return None


class AnimTable(object):
    def __init__(self, stem):
        self.stem = stem
        p = os.path.join(DB_DIR, stem + ".json")
        d = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"anims": {}, "alias": {}}
        self.alias = d.get("alias", {})
        self.anims = {}
        for k, v in d["anims"].items():
            fr = np.asarray(v["frames"], dtype=np.float64)
            xyz = np.asarray(v["xyz"], dtype=np.float64).reshape(-1, 3)
            self.anims[k] = (float(v["fps"]), float(v["dur"]), fr, xyz)
        self.names = sorted(set(self.anims) | set(self.alias))
        self.index = {n: i for i, n in enumerate(self.names)}

    def get(self, name):
        e = self.anims.get(name)
        if e is None and name in self.alias:
            e = self.anims.get(self.alias[name])
        if e is None:
            STATS["未找到"] += 1
            MISSING[(self.stem, name)] += 1
        return e

    def offset(self, name, sec):
        """根骨骼相对第 0 帧的位移 (x, y, z)；时间按关键帧线性插值，超出两端取端点。"""
        e = self.get(name)
        if e is None or len(e[2]) == 0:
            return (0.0, 0.0, 0.0)
        STATS["位移查询"] += 1
        fps, dur, fr, xyz = e
        f = float(sec) * fps
        x0 = xyz[0] if fr[0] <= 0 else np.array([np.interp(0.0, fr, xyz[:, k]) for k in range(3)])
        cur = np.array([np.interp(f, fr, xyz[:, k]) for k in range(3)])
        return tuple(float(c) for c in (cur - x0))

    def length_ms(self, name):
        e = self.get(name)
        return 0.0 if e is None else e[1] * 1000.0


def table_for(path):
    sk = skeleton_of(path)
    if sk is None:
        STATS["模型无骨骼映射"] += 1
        return None
    t = _TABLES.get(sk)
    if t is None:
        t = _TABLES[sk] = AnimTable(sk)
    return t


def report():
    lines = ["== 动画数据库: 已载入 %s; 统计 %s" % ({k: len(v.anims) for k, v in _TABLES.items()}, dict(STATS))]
    if MISSING:
        lines.append("   未找到的动画(前 12): %s" % MISSING.most_common(12))
    return "\n".join(lines)
