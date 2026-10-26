# -*- coding: utf-8 -*-
"""扫 std_pyc 某目录下模块级 `from <模块> import a, b`：统计每个顶层模块被导入了哪些名字、哪些文件在用。
看服务端专用导入（AI 孤岛里会被打桩的 utils / Timer / mobilelog …）实际要哪些名字。
用法: python scan_server_imports.py <std_pyc 下的相对目录> <模块名正则>
  例: python scan_server_imports.py common_cs/ai "^(utils|Timer|mobilelog|battle|entity|config)(\\.|$)" """
import sys, os, re, dis, marshal, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simenv

SUB, PAT = sys.argv[1], re.compile(sys.argv[2])
root = os.path.join(simenv.ROOT, SUB)
names = collections.defaultdict(collections.Counter)


def walk(code, path):
    ins = list(dis.get_instructions(code))
    for i, x in enumerate(ins):
        if x.opname != "IMPORT_NAME" or not PAT.search(x.argval):
            continue
        frm = ins[i - 1].argval if i >= 1 and ins[i - 1].opname == "LOAD_CONST" else None
        if frm:
            for n in frm:
                names[x.argval][n] += 1
        else:
            names[x.argval]["<import 整个模块>"] += 1
        names[x.argval]["@" + path] += 1
    for c in code.co_consts:
        if hasattr(c, "co_code"):
            walk(c, path)


for dp, dn, fn in os.walk(root):
    for f in fn:
        if f.endswith(".pyc"):
            p = os.path.join(dp, f)
            walk(marshal.loads(open(p, "rb").read()[16:]), os.path.relpath(p, simenv.ROOT).replace(os.sep, "/"))
for mod, cnt in sorted(names.items()):
    files = sorted(k[1:] for k in cnt if k.startswith("@"))
    print("== %s  名字: %s" % (mod, dict((k, v) for k, v in cnt.items() if not k.startswith("@"))))
    print("     %d 个文件: %s" % (len(files), " ".join(files[:12]) + (" …" if len(files) > 12 else "")))
