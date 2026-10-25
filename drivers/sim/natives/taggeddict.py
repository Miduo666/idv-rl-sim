# -*- coding: utf-8 -*-
"""原生 taggeddict 的替代：配表每行都是 TD({...})，原生版让同结构的行共享键表省内存，语义就是 dict。"""


class taggeddict(dict):
    __slots__ = ()
