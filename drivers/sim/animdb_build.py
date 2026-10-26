# -*- coding: utf-8 -*-
"""从角色资源包构建模拟器用的"根运动数据库"：每个骨骼一份 json，动画名 → 根骨骼位移轨道。
用法: animdb_build.py <idx> <census.json> <thy> <输出目录> <骨骼文件名>...
  例: animdb_build.py ../../res_pull/chr_pkg/chr_player.idx ../../res_pull/chr_pkg/player_census.json
        ../../res_pull/chr_pkg/thd_chr_player.thy ../../res_pull/animdb dm65_survivor_w.skeleton h55_survivor_m_zbs.skeleton
来源与规则：
- 动画 ↔ 骨骼：RAWANIMA 头里的骨骼相对路径取文件名（rawanim_census.py 普查）。
- 动画名：RAWANIMA 的 NAME 源名 = 配置里文件名去扩展名（管家包 1534/1534）；配置 Name≠文件名的（约 1%）记为别名。
  别名只收 FileName 目录名含 "animations_<骨骼名>" 的配置条目。
- 同名多份内容：先只留 MD5 在 thd 清单(.thy，当前版本)里的；实测两份都在清单里（是不同目录的同名文件，
  如 animations_dm65_survivor_w/yywf/），约 1%，记冲突、取最后一份。
- 根骨骼 = 名为 "biped" 的骨骼（无则第 0 根）；格式 2 存关键帧原样，格式 1(ACL) 按采样率逐帧解。
  只存位移（get_reference_to_first_frame_transform 用的是 .translation；录像终点对照见 SKILL §9.13）。"""
import sys, os, json, struct, collections
sys.argv, ARGS = sys.argv[:1], sys.argv[1:]
import rawanim_layout as L, rawanim as R


def thy_md5s(path):
    d = open(path, "rb").read()
    out = set()
    for i in range(8, len(d) - 32, 4):
        f2, = struct.unpack_from("<I", d, i + 8)
        if (f2 >> 24) == 0xFC:
            out.add(d[i + 16:i + 32].hex())
    return out


def root_track(a):
    if not a.bones:
        return None
    b = a.bones.index("biped") if "biped" in a.bones else 0
    if a.fmt == 2:
        fr, v = a.tracks[b][0]
        return [int(x) for x in fr], [[round(float(c), 4) for c in row] for row in v]
    if a.fmt == 1:
        buf = a._acl_buf()
        try:
            info = R.acl_info(buf)
        except ValueError:          # ACL 头校验不过（多半是别的 ACL 版本），计数跳过
            return None
        n = info["num_samples"]
        rows = [R.acl_sample(buf, k / info["sample_rate"], 1)[b, 4:7] for k in range(n)]
        return list(range(n)), [[round(float(c), 4) for c in r] for r in rows]
    return None


def main():
    idx, census, thy, outdir = ARGS[:4]
    skels = ARGS[4:]
    J = json.load(open(census, encoding="utf-8"))
    cur = thy_md5s(thy)
    f = L.IDXWPKFile(idx)
    os.makedirs(outdir, exist_ok=True)
    for sk in skels:
        stem = sk[:-len(".skeleton")]
        cand = collections.defaultdict(list)
        for a in J["anims"]:
            if os.path.basename(a["skeleton"]) == sk:
                cand[a["src"]].append(a)
        alias, alias_conf = {}, collections.Counter()
        for c in J["cfgs"]:
            for e in c["anims"]:
                if "animations_" + stem not in e["file"]:
                    continue
                src = os.path.splitext(os.path.basename(e["file"]))[0]
                if e["name"] != src:
                    if alias.get(e["name"], src) != src:
                        alias_conf[e["name"]] += 1
                    alias[e["name"]] = src
        anims, stat = {}, collections.Counter()
        for src, lst in cand.items():
            if len(lst) > 1:
                lst = [a for a in lst if a["md5"] in cur] or lst
                stat["同名多份"] += 1
                if len({a["md5"] for a in lst}) > 1:
                    stat["清单筛后仍冲突"] += 1
            a = R.RawAnim(f.read_entry(lst[-1]["i"]).data)
            tr = root_track(a)
            if tr is None:
                stat["格式%d跳过" % a.fmt if a.bones else "无骨骼跳过"] += 1
                continue
            stat["格式%d" % a.fmt] += 1
            anims[src] = {"fps": a.fps, "dur": round(a.duration, 5), "frames": tr[0], "xyz": tr[1]}
        alias = {k: v for k, v in alias.items() if v in anims and k not in anims}
        out = {"skeleton": sk, "root_bone": "biped", "anims": anims, "alias": alias,
               "stat": dict(stat), "alias_conflict": dict(alias_conf)}
        p = os.path.join(outdir, stem + ".json")
        json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        print("%-32s 动画 %d 别名 %d %s 别名冲突 %d -> %s (%.1f MB)" % (sk, len(anims), len(alias), dict(stat),
              len(alias_conf), p, os.path.getsize(p) / 1e6))


if __name__ == "__main__":
    main()
