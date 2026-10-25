import sys, traceback
sys.path.insert(0, sys.argv[1])
import simboot
try:
    simboot.boot()
except BaseException:
    traceback.print_exc(limit=-8, file=sys.stdout)
