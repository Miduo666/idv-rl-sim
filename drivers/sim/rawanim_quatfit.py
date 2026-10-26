# -*- coding: utf-8 -*-
"""定 RAWANIMA 格式 2 的 32 位四元数编码：smallest-three(2 位最大分量下标 + 3×10 位)。
真值 = 同一骨骼文件、同一骨骼在 ACL(格式 1) 动画里的旋转，只用两边都是常量的骨骼。
枚举: 下标→分量映射(4! 种) × 位序(高位在前/低位在前)，统计 |dot| 接近 1 的比例。用法: rawanim_quatfit.py <idx>"""
import sys, itertools, collections
import numpy as np
sys.argv, _a = sys.argv[:1], sys.argv[1:]
import rawanim_layout as L, rawanim as R

S = 1 / np.sqrt(2)


def decode(v, perm, hi_first):
    idx = (v >> 30) & 3
    a = [(v >> 20) & 1023, (v >> 10) & 1023, v & 1023]
    if not hi_first:
        a = a[::-1]
    a = [x / 1023.0 * 2 * S - S for x in a]
    w = np.sqrt(max(0.0, 1 - sum(x * x for x in a)))
    slot = perm[idx]                     # 最大分量放到哪个分量位置
    q = [0.0] * 4
    rest = [(slot + 1) % 4, (slot + 2) % 4, (slot + 3) % 4]   # 其余三个按最大分量之后的循环顺序
    q[slot] = w
    for k, x in zip(rest, a):
        q[k] = x
    return np.array(q)                   # xyzw


def main():
    f = L.IDXWPKFile(_a[0])
    acl_vals = collections.defaultdict(list)   # (skeleton, bone) -> [常量四元数]，每个 ACL 动画一份
    kf_vals = collections.defaultdict(list)    # (skeleton, bone) -> [单关键帧 u32]
    seqs = []                                   # 动画轨道的相邻关键帧 u32 对
    for i in range(len(f.indices)):
        d = f.read_entry(i).data or b""
        if d[:8] != b"RAWANIMA":
            continue
        a = R.RawAnim(d)
        if a.fmt == 1:
            buf = a._acl_buf()
            p0 = R.acl_sample(buf, 0.0); p1 = R.acl_sample(buf, a.duration)
            for b, n in enumerate(a.bones):
                if np.abs(p0[b, :4] - p1[b, :4]).max() < 1e-4:
                    acl_vals[(a.skeleton, n)].append(p0[b, :4].astype(np.float64))
        elif a.fmt == 2:
            for b, n in enumerate(a.bones):
                fr, v = a.tracks[b][2]
                if len(v) == 1:
                    kf_vals[(a.skeleton, n)].append(int(v[0]))
                elif len(seqs) < 20000:
                    seqs += [(int(v[j]), int(v[j + 1])) for j in range(len(v) - 1)]
    # 全局常量：ACL 至少 3 份且彼此一致；关键帧侧取众数
    pairs = []
    for k, qs in acl_vals.items():
        if len(qs) >= 3 and k in kf_vals and all(abs(np.dot(qs[0], q)) > 0.99999 for q in qs):
            v = collections.Counter(kf_vals[k]).most_common(1)[0][0]
            pairs.append((qs[0], v))
    print("全局常量骨骼配对", len(pairs), " 相邻关键帧对", len(seqs))
    res = []
    for perm in itertools.permutations(range(4)):
        for hi in (True, False):
            ok = sum(1 for q, v in pairs if abs(np.dot(q, decode(v, perm, hi))) > 0.999)
            cont = np.mean([abs(np.dot(decode(u, perm, hi), decode(w, perm, hi))) > 0.98 for u, w in seqs[:5000]])
            res.append((ok, cont, perm, hi))
    res.sort(key=lambda r: (r[0], r[1]), reverse=True)
    for r in res[:6]:
        print("常量命中 %d/%d  连续性 %.4f  下标→分量 %s  高位在前 %s" % (r[0], len(pairs), r[1], r[2], r[3]))


if __name__ == "__main__":
    main()
