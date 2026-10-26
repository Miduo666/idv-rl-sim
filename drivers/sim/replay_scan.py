# -*- coding: utf-8 -*-
"""录像事件流概览：各快照里的事件类型(et)、RPC 函数名计数，以及含指定关键字的 RPC 样例。
用法: replay_scan.py <录像对局目录> [关键字正则] [样例数]
解析用 逆向存档\\_scripts\\replay_genius.py 的受限 Unpickler（pickle 会执行代码，不要用裸 pickle.load）。"""
import sys, os, re, glob, collections
sys.path.insert(0, os.environ.get("IDV_SCRIPTS", r"C:\Users\31297\Desktop\逆向存档\_scripts"))
sys.stdout.reconfigure(encoding="utf-8")
import replay_genius as rg

def snaps(d):
    fs = glob.glob(os.path.join(d, "battle_frames_snapshot_*.txt"))
    return sorted(fs, key=lambda p: int(re.search(r"_(\d+)\.txt$", p).group(1)))


def events(d):
    """逐条产出 (快照号, 时间戳, et, data)。"""
    for p in snaps(d)[1:]:
        k = int(re.search(r"_(\d+)\.txt$", p).group(1))
        o = rg.读(p)
        for blk in o.get("data", []):
            for ev in (blk.get("battle_event") or []) if isinstance(blk, dict) else []:
                ts, body = ev[0], ev[1]
                yield k, ts, body.get("et"), body.get("data")


if __name__ == "__main__":
    D = sys.argv[1]
    PAT = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None
    NS = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    o0 = rg.读(snaps(D)[0])
    print("snapshot_0 data[0] 键:", list(o0["data"][0].keys())[:20])
    ets = collections.Counter(); funcs = collections.Counter(); ex = collections.defaultdict(list)
    t0 = t1 = None
    ET = set(int(x) for x in os.environ.get("SCAN_ET", "").split(",") if x)   # 另取这些非 RPC 事件类型的样例
    for k, ts, et, data in events(D):
        ets[et] += 1
        if et in ET and len(ex["et%s" % et]) < NS:
            ex["et%s" % et].append((round(ts - (t0 or ts), 2), str(data)[:400]))
        t0 = ts if t0 is None else min(t0, ts); t1 = ts if t1 is None else max(t1, ts)
        if et == 10999 and isinstance(data, dict):
            fn = data.get("func"); funcs[fn] += 1
            if PAT and PAT.search(str(fn)) and len(ex[fn]) < NS:
                ex[fn].append((round(ts - (t0 or 0), 2), data.get("id"), str(data.get("args"))[:300]))
    print("时间跨度 %.1fs" % ((t1 or 0) - (t0 or 0)))
    print("事件类型:", ets.most_common(20))
    print("RPC 函数 %d 种，前 80:" % len(funcs))
    for fn, n in funcs.most_common(80):
        print("  %6d  %s" % (n, fn))
    for fn, rows in ex.items():
        print("== 样例", fn)
        for r in rows: print("   ", r)
