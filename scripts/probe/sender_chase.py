# -*- coding: utf-8 -*-
"""密码机破译进度：沿对象内指针下钻抓快照，再按已知进度分档做差分。

    python sender_chase.py --grab 0x...=100 0x...=100 0x...=80 0x...=25   # 抓一次活体快照并落盘
    python sender_chase.py --score 0x...=100 ...                          # 用盘上快照重新打分(不碰游戏)

分档判据(强): 同一进度档内的机器取值必须**全部相同**，不同档之间必须**严格单调**。
两台100%的机器同值是正确特征，早前版本错误地把"档内同值"当成重复值滤掉了。

指针展开放宽: 只要非0%档的机器在该槽位有合法指针就展开(0%档可能是懒分配的NULL)。
"""
import sys, os, struct, pickle, collections
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向\_通用工具\procmem")
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from devread import Mem, PAGE, TMP
from idv_probe import discover, dump_bss, find_sigs, class_names, read_objects, MASK, PTR_MIN, PTR_MAX

BODY = NODE = 0x400
KW = "sender"
SNAP = os.path.join(TMP, "sender_snap.pkl")

DEPTH = int(sys.argv[sys.argv.index("--depth") + 1]) if "--depth" in sys.argv else 2
known = {}
for a in sys.argv[1:]:
    if "=" in a:
        k, _, v = a.partition("=")
        known[int(k, 16)] = float(v)


# ------------------------------------------------------------------ 抓快照
def grab():
    pid, libbase, bss, maps = discover()
    d = dump_bss(pid, bss, True)
    head = find_sigs(d, bss[0], libbase)["array"][0]
    m = Mem(pid)
    m.quiet = True
    r = read_objects(m, head)
    names = class_names(m, r["objs"])
    send = sorted({o for o in r["objs"] if KW in names.get(o, "").lower() and m.d(o + 0x240) == 2}
                  | set(known))
    nz = [o for o in send if known.get(o, 0) > 0]
    print("密码机 %d 台: %s" % (len(send), " ".join("0x%X(%.0f%%)" % (o, known.get(o, 0)) for o in send)))

    store = {}
    frontier = [("obj", {o: o for o in send})]
    seen = set()
    for depth in range(DEPTH + 1):
        m.fetch([b + k for _, nd in frontier for b in nd.values()
                 for k in list(range(0, NODE, PAGE)) + [NODE - 8]], "")
        nxt = []
        for path, nodes in frontier:
            good = {o: m.get(b, NODE) for o, b in nodes.items()}
            good = {o: b for o, b in good.items() if b}
            if len(good) < 3 or not all(o in good for o in nz):
                continue
            store[path] = (dict(nodes), good)
            if depth == DEPTH:
                continue
            for off in range(0, NODE - 8, 8):
                kids = {o: (struct.unpack_from("<Q", b, off)[0] & MASK) for o, b in good.items()}
                kids = {o: p for o, p in kids.items() if PTR_MIN < p < PTR_MAX}
                if not all(o in kids for o in nz):
                    continue
                key = tuple(sorted(kids.items()))
                if key in seen:
                    continue
                seen.add(key)
                nxt.append(("%s+0x%03X" % (path, off), kids))
        print("--- 第 %d 层: 节点组 %d, 已存 %d, 下一层 %d ---" % (depth, len(frontier), len(store), len(nxt)))
        frontier = nxt
        if not frontier:
            break
    pickle.dump({"store": store, "known": known, "names": {o: names.get(o, "") for o in send}},
                open(SNAP, "wb"))
    print("\n快照已落盘: %s (%d 个节点组)" % (SNAP, len(store)))


# ------------------------------------------------------------------ 打分
def score():
    snap = pickle.load(open(SNAP, "rb"))
    store = snap["store"]
    prog = dict(known) or snap["known"]
    objs = sorted({o for _, (nd, _) in store.items() for o in nd})
    prog = {o: prog.get(o, 0.0) for o in objs}
    levels = sorted({p for p in prog.values()})
    grp = {L: [o for o in objs if prog[o] == L] for L in levels}
    print("分档: " + "  ".join("%.0f%%×%d" % (L, len(grp[L])) for L in levels))

    hits = []
    for path, (nodes, blobs) in store.items():
        n = min(len(b) for b in blobs.values())
        for off in range(0, n - 4, 4):
            # f64 不能漏: Python 层的 fix_process 是 float，落到内存里是 double
            for tag, fmt in (("f32", "<f"), ("f64", "<d"), ("u32", "<I"), ("u16", "<H"), ("u8", "<B")):
                sz = struct.calcsize(fmt)
                if off + sz > n:
                    continue
                v = {o: struct.unpack_from(fmt, b, off)[0] for o, b in blobs.items()}
                if any(x != x or abs(x) > 1e12 for x in v.values()):
                    continue
                # 每一档内部必须同值
                rep = []
                ok = True
                for L in levels:
                    s = {v[o] for o in grp[L] if o in v}
                    if len(s) != 1:
                        ok = False
                        break
                    rep.append(s.pop())
                if not ok or len(set(rep)) != len(rep):
                    continue
                # 档间必须严格单调
                if not (all(a < b for a, b in zip(rep, rep[1:])) or
                        all(a > b for a, b in zip(rep, rep[1:]))):
                    continue
                hits.append((path, off, tag, rep, nodes))

    print("\n=== 强命中 %d 处 ===" % len(hits))
    for path, off, tag, rep, nodes in hits:
        print("   %-28s +0x%03X %-3s  %s" % (
            path, off, tag, "  ".join("%.0f%%=%-12.6g" % (L, r) for L, r in zip(levels, rep))))
        print("      节点: " + " ".join("0x%X" % nodes[o] for o in sorted(nodes, key=lambda x: prog[x])))
    if not hits:
        print("   无 —— 进度不在这张对象图的两层内，多半在 Python 层或另一棵对象树上")


if "--grab" in sys.argv:
    grab()
if "--score" in sys.argv or "--grab" not in sys.argv:
    score()
