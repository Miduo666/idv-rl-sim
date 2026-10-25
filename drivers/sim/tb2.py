import sys, traceback
sys.path.insert(0, sys.argv[1])
import simboot; simboot.boot(False)
import importlib
for m in sys.argv[2:]:
    try:
        importlib.import_module(m); print("OK", m)
    except BaseException:
        print("FAIL", m); traceback.print_exc(limit=-12, file=sys.stdout)
