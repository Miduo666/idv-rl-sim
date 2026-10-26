# -*- coding: utf-8 -*-
"""找"游戏自带 ImportError 兜底、但模拟器把被导入模块打成桩"的地方（桩导入成功会挡掉兜底，§9.16 CommonUtils 那类 bug）。
扫 std_pyc 全部模块：位于 try 块（异常表覆盖）内、且异常处理里出现 ImportError/ModuleNotFoundError/Exception 名字的 IMPORT_NAME。
再与一次模拟运行实际打桩的模块名单（从 run_full 的 "stub modules (N): ..." 行读）取交集。
用法: python scan_try_imports.py <run_full 输出文件>"""
import sys, os, re, dis, marshal, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simenv

log = open(sys.argv[1], encoding="utf-8", errors="replace").read()
m = re.search(r"stub modules \(\d+\): (.*)", log)
stubbed = set(m.group(1).split()) if m else set()
print("== 运行期打桩模块 %d 个" % len(stubbed))

hits = collections.defaultdict(set)


def walk(code, path):
    try:
        table = list(dis._parse_exception_table(code))
    except Exception:
        table = []
    ins = list(dis.get_instructions(code))
    byoff = {x.offset: i for i, x in enumerate(ins)}
    for e in table:
        # 处理器开头若干条里有没有 ImportError 类名字
        hi = byoff.get(e.target)
        if hi is None:
            continue
        names = {x.argval for x in ins[hi:hi + 12] if x.opname in ("LOAD_GLOBAL", "LOAD_NAME")}
        if not names & {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}:
            continue
        for x in ins:
            if e.start <= x.offset < e.end and x.opname == "IMPORT_NAME":
                hits[x.argval].add(path)
    for c in code.co_consts:
        if hasattr(c, "co_code"):
            walk(c, path)


for dp, dn, fn in os.walk(simenv.ROOT):
    for f in fn:
        if f.endswith(".pyc"):
            p = os.path.join(dp, f)
            try:
                walk(marshal.loads(open(p, "rb").read()[16:]), os.path.relpath(p, simenv.ROOT).replace(os.sep, "/"))
            except Exception:
                pass
both = sorted(n for n in hits if n in stubbed or any(s == n or s.startswith(n + ".") for s in stubbed))
print("== try 块里导入、且运行期被打桩的模块 %d 个：" % len(both))
for n in both:
    fs = sorted(hits[n])
    print("  %-50s %d 处: %s" % (n, len(fs), " ".join(fs[:6]) + (" …" if len(fs) > 6 else "")))
