# -*- coding: utf-8 -*-
"""bullet_collision 与 physx_collision 接口同形（CollisionManager.init_collision_module 二选一），共用同一实现。"""
from physx_collision import *          # noqa
from physx_collision import __getattr__  # noqa
