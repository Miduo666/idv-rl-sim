# -*- coding: utf-8 -*-
# probe2 命令(2026-09-24)：bson ObjectId 的内存布局 —— C++ 侧要从 ObjectId 对象拿到 12 字节、拼成 24 位 hex。
oid = S(lambda: GK.g_avatar.id)
T = type(oid)
P("类型 %s.%s  basicsize=%s  dictoffset=%s  itemsize=%s" % (T.__module__, T.__name__, T.__basicsize__,
                                                          T.__dictoffset__, T.__itemsize__))
P("__slots__ = %r" % (S(lambda: T.__slots__, "<无>"),))
P("mro = %s" % [c.__name__ for c in T.__mro__])
P("str(oid) = %s   id(oid)=0x%x" % (str(oid), id(oid)))
for nm in ("_ObjectId__id", "__id", "_id", "binary"):
    v = S(lambda nm=nm: object.__getattribute__(oid, nm), "<取不到>")
    if v == "<取不到>": P("  .%s 取不到" % nm); continue
    P("  .%s = %r  type=%s id=0x%x len=%s" % (nm, v, type(v).__name__, id(v), S(lambda v=v: len(v))))
# 槽描述符的 offset
for c in T.__mro__:
    for k, d in c.__dict__.items():
        if type(d).__name__ == "member_descriptor":
            P("  member_descriptor %s.%s  offset=?  (repr=%r)" % (c.__name__, k, d))
d = S(lambda: object.__getattribute__(oid, "__dict__"), None)
P("实例 __dict__ = %r" % (d,))
