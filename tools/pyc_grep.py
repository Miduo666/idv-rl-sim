"""在全量 pyc 的字符串常量/名字里搜子串。用法: pyc_grep.py [--files 路径子串] 关键字 [关键字...]
关键字全部命中(AND)的文件才打印，并列出每个关键字命中的字符串(去重，最多 8 个)。"""
import marshal, os, sys, types

ROOT = r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\all_pyc"


def strings(co, acc):
    acc.update(co.co_names)
    acc.add(co.co_qualname)
    for c in co.co_consts:
        if isinstance(c, str):
            acc.add(c)
        elif isinstance(c, tuple):
            for x in c:
                if isinstance(x, str):
                    acc.add(x)
        elif isinstance(c, types.CodeType):
            strings(c, acc)


args = sys.argv[1:]
path_filter = None
if args and args[0] == '--files':
    path_filter = args[1]
    args = args[2:]
keys = [k.lower() for k in args]
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith('.pyc'):
            continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
        if path_filter and path_filter not in rel:
            continue
        try:
            with open(p, 'rb') as fh:
                co = marshal.loads(fh.read()[16:])
        except Exception:
            continue
        acc = set()
        strings(co, acc)
        low = [(s, s.lower()) for s in acc]
        hits = []
        for k in keys:
            m = sorted({s for s, l in low if k in l})
            if not m:
                break
            hits.append((k, m[:8]))
        else:
            print(rel)
            for k, m in hits:
                print('   ', k, '->', m)
