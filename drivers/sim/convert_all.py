import sys, os, io, marshal, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, sys.argv[1])
import idvpyc
src, dst = sys.argv[2], sys.argv[3]
ok = bad = 0; errs = []
t = time.time()
for dp, _, fs in os.walk(src):
    for fn in fs:
        if not fn.endswith(".pyc"): continue
        p = os.path.join(dp, fn); rel = os.path.relpath(p, src)
        try:
            idvpyc.to_std_pyc(p, os.path.join(dst, rel))
            marshal.loads(open(os.path.join(dst, rel), "rb").read()[16:])   # 标准 marshal 复核
            ok += 1
        except Exception as e:
            bad += 1; errs.append((rel, repr(e)))
print("ok", ok, "bad", bad, "secs %.0f" % (time.time() - t))
for e in errs[:10]: print(e)
