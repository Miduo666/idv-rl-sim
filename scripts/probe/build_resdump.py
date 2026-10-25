# -*- coding: utf-8 -*-
"""把离线收集的路径清单填进 cmd_resdump.py 模板，生成 cmd_resdump_built.py。
用法: python build_resdump.py <explicit_paths.json>"""
import sys, os, json
here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "cmd_resdump.py"), encoding="utf-8").read()
paths = json.load(open(sys.argv[1], encoding="utf-8"))
blob = json.dumps(paths, ensure_ascii=False)
assert "'''" not in blob
out = tpl.replace("__EXPLICIT_JSON__", blob)
compile(out, "cmd_resdump_built.py", "exec")
with open(os.path.join(here, "cmd_resdump_built.py"), "w", encoding="utf-8", newline="") as f:
    f.write(out)
print("built: %d explicit paths, %d bytes" % (len(paths), len(out)))
