import sys, io, importlib, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, sys.argv[1])
sys.dont_write_bytecode = True
for m in sys.argv[2:]:
    try:
        importlib.import_module(m)
        print("OK  ", m)
    except BaseException as e:
        tb = traceback.extract_tb(e.__traceback__)
        where = tb[-1].filename if tb else "?"
        print("FAIL", m, "->", type(e).__name__, str(e)[:120], "| at", where)
