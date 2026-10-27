# 从 pseudo.py 输出重建行为树缩进结构：python bt_tree.py <pseudo.txt>
import re, sys

txt = open(sys.argv[1], encoding="utf-8", errors="replace").read().splitlines()
children, params, entry = {}, {}, None
cur = None
for ln in txt:
    m = re.match(r"\s*\d*\s*N(\d+)_CHILD_DICT = \{(.*)\}", ln)
    if m:
        children[int(m.group(1))] = re.findall(r"\d+: (n\d+_\w+)", m.group(2))
        continue
    m = re.match(r"def (n\d+_\w+)\(", ln)
    if m:
        cur = m.group(1); params[cur] = []
        continue
    if ln.startswith("def entry"):
        cur = "entry"; continue
    if cur == "entry":
        m = re.search(r"return (n\d+_\w+)", ln)
        if m: entry = m.group(1); cur = None
        continue
    if cur and cur in params:
        m = re.match(r"\s*\d+\s+self_(\w+) = (.+)$", ln)
        if m:
            params[cur].append("%s=%s" % (m.group(1), m.group(2)[:60]))


def name(n):
    i = int(n.split("_")[0][1:])
    t = n.split("_", 1)[1]
    t = t.replace("QaaiCivilianPolicy", "").replace("QaaiCivilian", "").replace("Qaai", "")
    return i, t


def walk(n, d, seen):
    i, t = name(n)
    tag = {"CBTSeqNode": "SEQ", "CBTSelecNode": "SEL"}.get(t, t)
    p = (" (" + ", ".join(params.get(n, [])) + ")") if params.get(n) else ""
    print("  " * d + "%s#%d%s" % (tag, i, p))
    if i in seen:
        return
    seen.add(i)
    for c in children.get(i, []):
        walk(c, d + 1, seen)


walk(entry, 0, set())
