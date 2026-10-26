# -*- coding: utf-8 -*-
"""从设备场景包里按内容找回某张图的普通导航（导出包只有 AI 导航，SKILL §9.10）。
用法: nav_match.py <res.zip> <AI导航 .nav 路径> <scene.idx> <nav_entries.json> <nav_hunt 目录> <输出目录>
做法：
1. AI 导航分块的可走多边形中心当采样点（按块坐标 x_y_layer 分组）。
2. 场景包里同块坐标的所有 VAND 分块逐个算"覆盖率"：采样点落在其某个多边形(xz)内、且高度差 < 爬升高度的比例。
   普通导航只比 AI 导航少收缩，属于同一张图的分块覆盖率应接近 1；别的图的同坐标分块对不上。
3. 每个块坐标取覆盖率最高的分块；再在 MSET 总表里找块名集合与之吻合的。
输出：<输出目录>/<x_y_layer>.tile（原样字节）+ match.json（每块的候选与覆盖率、walkable 参数、选中的 MSET）。"""
import sys, os, json, struct, zipfile, collections, types, logging
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "tools", "NeoXtractor-IDXWPK")))
logging.disable(logging.WARNING)
_stub = types.ModuleType("core.logger"); _stub.get_logger = lambda *a, **k: logging.getLogger("wpk")
sys.modules["core.logger"] = _stub
from core.wpk.wpk_file import IDXWPKFile
import navmesh


def walkable_samples(t, include=65531):
    out = []
    for p in t["polys"]:
        if p["type"] != 0 or not (p["flags"] & include) or len(p["verts"]) < 3:
            continue
        vs = [t["verts"][i] for i in p["verts"]]
        out.append(tuple(sum(v[k] for v in vs) / len(vs) for k in range(3)))
    return out


def poly_xz(t, p):
    return [(t["verts"][i][0], t["verts"][i][2], t["verts"][i][1]) for i in p["verts"]]


def inside(pt, poly):
    x, z = pt
    c = False
    n = len(poly)
    for i in range(n):
        x1, z1, _ = poly[i]; x2, z2, _ = poly[i - 1]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            c = not c
    return c


def coverage(cand, samples, climb):
    polys = [(poly_xz(cand, p), p) for p in cand["polys"] if p["type"] == 0 and len(p["verts"]) >= 3]
    boxes = [(min(v[0] for v in pl), max(v[0] for v in pl), min(v[1] for v in pl), max(v[1] for v in pl), pl) for pl, _ in polys]
    hit = 0
    for s in samples:
        for x0, x1, z0, z1, pl in boxes:
            if x0 <= s[0] <= x1 and z0 <= s[2] <= z1 and inside((s[0], s[2]), pl):
                if abs(sum(v[2] for v in pl) / len(pl) - s[1]) < max(climb, 3.0) * 2:
                    hit += 1
                    break
    return hit / len(samples) if samples else 0.0


def main():
    zpath, ai_nav, idx, entries, hunt, outdir = sys.argv[1:7]
    os.makedirs(outdir, exist_ok=True)
    z = zipfile.ZipFile(zpath)
    ai = navmesh.load_nav(z, ai_nav)
    ai_tiles = {(t["x"], t["y"], t["layer"]): t for t in ai["tiles"]}
    samples = {k: walkable_samples(t) for k, t in ai_tiles.items()}
    print("AI 导航块 %d，采样点 %d，AI walkable(高,半径,爬升)=%s" % (len(ai_tiles), sum(map(len, samples.values())),
                                                         ai["tiles"][0]["walkable"]))
    E = json.load(open(entries))
    f = IDXWPKFile(idx)
    by_key = collections.defaultdict(list)
    for n, (i, md5, size, known) in enumerate(E["VAND分块"]):
        b = f.read_entry(i).data
        try:
            t = navmesh.parse_tile(b)
        except Exception:
            continue
        k = (t["x"], t["y"], t["layer"])
        if k in ai_tiles:
            by_key[k].append((i, md5, b, t))
        if n % 3000 == 0:
            print("  读分块 %d/%d" % (n, len(E["VAND分块"])), flush=True)
    res, chosen = {}, {}
    for k, cands in by_key.items():
        climb = ai_tiles[k]["walkable"][2]
        scored = sorted(((coverage(t, samples[k], climb), i, md5, t["walkable"], len(t["polys"])) for i, md5, b, t in cands), reverse=True)
        res["%d_%d_%d" % k] = [dict(cov=round(s[0], 3), idx=s[1], md5=s[2], walkable=s[3], npoly=s[4]) for s in scored[:4]]
        best = scored[0]
        if best[0] >= 0.9:
            b = next(bb for i, md5, bb, t in cands if i == best[1])
            chosen["%d_%d_%d" % k] = (best[1], best[3])
            open(os.path.join(outdir, "%d_%d_%d.tile" % k), "wb").write(b)
    # 选中分块的 walkable 参数分布（区分普通导航 / AI 导航 / 其它）
    wk = collections.Counter(tuple(round(x, 2) for x in v[1]) for v in chosen.values())
    # MSET：块名集合 ⊇ 选中块名、块数相近的
    names_ai = {"%d_%d_%d.tile" % k for k in ai_tiles}
    msets = []
    for fn in os.listdir(hunt):
        if fn.endswith(".nav"):
            nb = open(os.path.join(hunt, fn), "rb").read()
            ns = set(navmesh.tile_names(nb))
            j = len(ns & names_ai) / len(ns | names_ai) if ns else 0
            msets.append((round(j, 3), fn, len(ns)))
    msets.sort(reverse=True)
    out = {"chosen": {k: {"idx": v[0], "walkable": v[1]} for k, v in chosen.items()}, "walkable_dist": [list(k) + [n] for k, n in wk.items()],
           "per_key": res, "mset_by_name_jaccard": msets[:8], "missing_keys": sorted(set(res) - set(chosen))}
    json.dump(out, open(os.path.join(outdir, "match.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("块坐标 %d 个有候选；覆盖率≥0.9 选中 %d 个；选中块 walkable 分布 %s" % (len(by_key), len(chosen), dict(wk)))
    print("未选中:", out["missing_keys"][:12])
    print("MSET 按块名 Jaccard:", msets[:6])


if __name__ == "__main__":
    main()
