# -*- coding: utf-8 -*-
"""监管普攻链路打点：LSkillNormal.cast / resolve_tick / get_resolve_targets(结果数) / process_enemy_attacked，
看攻击断在哪一环。用法: python atk_probe.py [帧=1800]"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simcore
simcore.ensure_hashseed()
from simcore import SimCore

FR = int(sys.argv[1]) if len(sys.argv) > 1 else 1800
core = SimCore(verbose=False, server_ai=True, seed=0)
import sim1v4
from common_cs.skills.LSkillNormal import LSkillNormal
from common_cs.skills.LSkillBase import LSkillBase
C = collections.Counter()
SAMPLE = []


def wrap(cls, name, tag, post=None):
    f = getattr(cls, name)

    def g(self, *a, **k):
        C[tag] += 1
        r = f(self, *a, **k)
        if post:
            post(self, a, r)
        return r
    setattr(cls, name, g)


def after_targets(self, a, r):
    n = len(r) if r else 0
    C["get_resolve_targets 非空"] += bool(n)
    if len(SAMPLE) < 6:
        o = getattr(self, "owner", None)
        SAMPLE.append(("目标数", n, "技能", getattr(self, "skill_id", None), "释放者", getattr(o, "uid", None)))


wrap(LSkillNormal, "cast", "LSkillNormal.cast")
wrap(LSkillNormal, "resolve_tick", "LSkillNormal.resolve_tick")
wrap(LSkillBase, "get_resolve_targets", "get_resolve_targets", after_targets)
wrap(LSkillNormal, "process_enemy_attacked", "process_enemy_attacked")
w = sim1v4.make_1v4(core, 1)
core.run(FR)
print("== 普攻链路计数:", dict(C))
for s in SAMPLE: print("  ", s)
