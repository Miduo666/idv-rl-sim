# -*- coding: utf-8 -*-
"""全量枚举所有引用 ANTI_CHEAT_TYPE 的函数(触发点)，以及几条反作弊通道的调用点。
用法: python scan_triggers.py <all_pyc目录>"""
import sys, os, marshal, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 关注的信号(co_names 里出现即记)
ANTI_MEMBERS = {"COLLISION", "SPEED", "SCALE", "MOVE_SPEED", "MEM_MODIFY"}
CHANNELS = {"ANTI_CHEAT_TYPE", "send_battle_event_safe", "anti_mem_modify",
            "server_anti_cheat_func", "_log_move_speed_cheat", "anti_move_speed_cheat_idx"}

def load(path):
    b = open(path, "rb").read()
    try:
        return marshal.loads(b[16:])
    except Exception:
        try: return marshal.loads(b)
        except Exception: return None

def walk(co, rel, hits):
    nm = getattr(co, "co_qualname", co.co_name)
    names = set(co.co_names)
    chan = names & CHANNELS
    mem = names & ANTI_MEMBERS
    # 只在确实引用了反作弊通道时记录(避免 SPEED/SCALE 等常见词误报)
    if "ANTI_CHEAT_TYPE" in names or (chan and (mem or "ANTI_CHEAT_TYPE" in names)) or (chan & {"send_battle_event_safe","anti_mem_modify","server_anti_cheat_func","_log_move_speed_cheat"}):
        nums = [c for c in co.co_consts if isinstance(c, (int, float)) and not isinstance(c, bool)]
        strs = [c for c in co.co_consts if isinstance(c, str) and c.strip()]
        hits.append((rel, nm, sorted(chan | (mem)), nums, strs))
    for c in co.co_consts:
        if hasattr(c, "co_code"):
            walk(c, rel, hits)

def main():
    root = sys.argv[1]
    hits = []
    nfile = 0
    for dp, _, fs in os.walk(root):
        for f in fs:
            if not f.endswith(".pyc"): continue
            nfile += 1
            p = os.path.join(dp, f)
            co = load(p)
            if co is None: continue
            rel = os.path.relpath(p, root).replace("\\", "/")
            walk(co, rel, hits)
    print("scanned %d pyc, trigger/channel sites: %d\n" % (nfile, len(hits)))
    for rel, nm, sig, nums, strs in sorted(hits):
        print("### %s :: %s" % (rel, nm))
        print("    signals: %s" % sig)
        if nums: print("    nums: %s" % nums)
        if strs: print("    strs: %s" % [s for s in strs if len(s) < 60][:20])

if __name__ == "__main__":
    main()
