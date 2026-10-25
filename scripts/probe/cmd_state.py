# -*- coding: utf-8 -*-
import os
gk = GK
a  = S(lambda: gk.g_avatar)
AC = type(a) if a is not None else None
P("pid=", os.getpid())
P("hall_list=", R(S(lambda: a.article_unlock.get('hall_list')), 200))
P("hall_id(当前)=", S(lambda: a.article_setting.get('hall_id')))
if AC is not None:
    P("_halllog=", getattr(AC, "_halllog", 0),
      " _furnlocal=", getattr(AC, "_furnlocal", 0),
      " _furnlog=", getattr(AC, "_furnlog", 0))
