# -*- coding: utf-8 -*-
"""NeoX render 模块替代（无渲染）：只提供被 isinstance 用到的类型，其余回退记录型桩。"""
import simenv


class material(object):
    def __getattr__(self, n):
        if n.startswith("__"): raise AttributeError(n)
        return simenv.Stub("render.material." + n)


class material_group(material):
    pass


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    simenv.ACCESS["render." + name] += 1
    return simenv.Stub("render." + name)
