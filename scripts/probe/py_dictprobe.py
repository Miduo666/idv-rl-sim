# -*- coding: utf-8 -*-
r"""在堆快照里，从一个 interned 属性名字符串出发，找出所有持有它的 dict 槽位并读出取值。

    python py_dictprobe.py fix_process

依据 CPython 3 的布局:
  PyASCIIObject: refcnt/ob_type/length/hash/state/wstr, 紧凑 ASCII 数据在 +0x30
  PyDictKeyEntry: {me_hash, *me_key, *me_value} 共 24 字节
  PyFloatObject : refcnt/ob_type/double

判定一处 "指向该字符串的指针" 是不是真 dict 槽位: 它前 8 字节必须等于该字符串的 hash。
Android 堆指针带固定 0xB4 高位标记(TBI)，比较和解引用前都要掩掉。
"""
import sys, struct
sys.path.insert(0, r"C:\Users\31297\Desktop\逆向存档\_scripts")
from heap_find import Heap

MASK = 0x00FFFFFFFFFFFFFF
NAME = sys.argv[1] if len(sys.argv) > 1 else "fix_process"

h = Heap()

# ---- 1. 找 interned 字符串对象: 数据前 0x30 字节要是合法 PyASCIIObject 头 ----
objs = []
for va in h.findall(NAME.encode() + b"\0"):
    b = h.read(va - 0x30, 0x30)
    if b is None:
        continue
    rc, tp, ln, hsh = struct.unpack_from("<QQqQ", b, 0)
    state = struct.unpack_from("<I", b, 0x20)[0]
    if ln == len(NAME) and 0 < rc < 10 ** 9 and (state & 0x3F) == 0x25:   # compact+ascii+ready+1BYTE
        objs.append((va - 0x30, rc, tp, hsh, state))
print("'%s' 的 interned 字符串对象 %d 个:" % (NAME, len(objs)))
for o, rc, tp, hsh, st in objs:
    print("   0x%X  refcnt=%d  ob_type=0x%X  hash=0x%016X  state=0x%X" % (o, rc, tp, hsh, st))
if not objs:
    sys.exit("没找到合法的字符串对象")

for strobj, _, _, HASH, _ in objs:
    print("\n" + "=" * 76)
    print("以 0x%X (hash=0x%016X) 为键反查" % (strobj, HASH))
    refs = h.findall(struct.pack("<Q", strobj | 0xB4 << 56), align=8) + \
           h.findall(struct.pack("<Q", strobj), align=8)
    print("指向它的指针 %d 处" % len(refs))

    slots = []
    for r in refs:
        pre = h.read(r - 8, 8)
        if pre and struct.unpack("<Q", pre)[0] == HASH:
            slots.append(r)
    print("其中 前8字节==hash 的真 dict 槽位: %d 处" % len(slots))

    for r in slots:
        vb = h.read(r + 8, 8)
        if vb is None:
            print("   槽位 0x%X  value 读不到" % r)
            continue
        val = struct.unpack("<Q", vb)[0]
        va = val & MASK
        if val == 0:
            print("   槽位 0x%X  value=NULL  (split-table, 值在实例的 values 数组里)" % r)
            continue
        ob = h.read(va, 24)
        if ob is None:
            print("   槽位 0x%X  value=0x%X  (读不到对象)" % (r, va))
            continue
        rc, tp = struct.unpack_from("<QQ", ob, 0)
        d = struct.unpack_from("<d", ob, 16)[0]
        i = struct.unpack_from("<q", ob, 16)[0]
        print("   槽位 0x%X  value=0x%X  type=0x%X  作double=%-12.6g 作int=%d"
              % (r, va, tp & MASK, d, i))
