# -*- coding: utf-8 -*-
"""可复现性检查：同一种子跑两次（两个独立进程），逐帧比较 5 个角色的位置，报告第一次分叉的帧。
用法: python t_determinism.py [帧数=300] [种子=0]"""
import sys, os, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))

if len(sys.argv) > 1 and sys.argv[1] == "--child":
    sys.path.insert(0, HERE)
    frames, seed = int(sys.argv[2]), int(sys.argv[3])
    from simcore import SimCore
    core = SimCore(verbose=False, server_ai=True, seed=seed)
    import sim1v4
    w = sim1v4.make_1v4(core)
    traj = []

    def cb(i):
        traj.append([[u.uid] + [round(c, 4) for c in (u.get_position3().x, u.get_position3().y, u.get_position3().z)]
                     for u in sorted(core.characters(), key=lambda u: u.uid)])
    core.run(frames, every=1, cb=cb)
    sys.stdout.write("\n@@TRAJ@@" + json.dumps(traj))
    sys.exit(0)

frames = int(sys.argv[1]) if len(sys.argv) > 1 else 300
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
env = dict(os.environ, PYTHONHASHSEED="0")
runs = []
for k in range(2):
    out = subprocess.run([sys.executable, __file__, "--child", str(frames), str(seed)], env=env, capture_output=True, text=True, encoding="utf-8").stdout
    runs.append(json.loads(out.split("@@TRAJ@@")[-1]))
a, b = runs
for i, (x, y) in enumerate(zip(a, b)):
    if x != y:
        print("第 %d 帧分叉:" % i)
        for r1, r2 in zip(x, y):
            if r1 != r2: print("   ", r1, "vs", r2)
        break
else:
    print("两次运行 %d 帧逐帧一致（%d 个记录帧）" % (frames, len(a)))
