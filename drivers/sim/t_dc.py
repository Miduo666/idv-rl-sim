import sys
sys.path.insert(0, sys.argv[1])
import simenv; simenv.setup()
from etc import dev_config as dc
for k in sorted(dir(dc)):
    if k.isupper():
        v = getattr(dc, k)
        if isinstance(v, (bool, int, str, type(None))) and ("MODE" in k or "SERVER" in k or "CLIENT" in k or "AI" in k or "COMMON" in k):
            print(k, "=", repr(v))
import game_kernel
print("game_kernel:", [a for a in dir(game_kernel) if not a.startswith("__")][:80])
