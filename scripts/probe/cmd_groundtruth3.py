# -*- coding: utf-8 -*-
# probe3 地面实况: 纯读, 零上行。搞清两件事, 用来解"附送6件为何能持久 / grant的不能"的矛盾:
#   (1) 服务器到底认这账号拥有哪些家具 (pp['14'] —— 最好在【重登游戏后】跑, 此时该被服务器真值覆盖)
#   (2) 大厅里【现在实际摆着】什么 (custom_hall_info) —— 重登后还在的 = 真持久下来的
# 交叉比对: 实际摆着的家具 base 是否都在"拥有集"里。
import time
gk = GK
a  = S(lambda: gk.g_avatar)
if a is None:
    P("g_avatar 未就绪，进庄园再跑")
else:
    pp  = S(lambda: a.props_package)
    fur = S(lambda: pp.get("14")) if pp is not None else None
    owned = sorted(int(k) for k in fur.keys()) if fur else []
    owned_set = set(owned)
    P("=== 拥有集 (pp['14']) ===")
    P("数量:", len(owned))
    P("owned fids:", R(owned, 2500))
    avail = sorted(S(lambda: a.get_avaliable_furniture_ids()) or [])
    P("get_avaliable_furniture_ids 数:", len(avail))
    P("hall_list:", R(S(lambda: a.article_unlock.get("hall_list")), 160))
    for nm in ("hall_id", "used_custom_hall_id", "hall_scene_id"):
        val = S(lambda n=nm: a.article_setting.get(n))
        P("article_setting.%s =" % nm, R(val, 80))

    P("=== 大厅实际摆放 (custom_hall_info) = 真持久下来的 ===")
    chi = S(lambda: a.custom_hall_info)
    if chi and hasattr(chi, "items"):
        for hk, hv in list(chi.items()):
            fi = hv.get("furniture_info", {}) if hasattr(hv, "get") else {}
            placed = []
            for grp, sub in (fi.items() if hasattr(fi, "items") else []):
                for ik in (sub.keys() if hasattr(sub, "keys") else []):
                    try:
                        iki = int(ik)
                        placed.append(iki // 100)
                    except Exception:
                        pass
            bases = sorted(set(placed))
            not_owned = [b for b in bases if b not in owned_set]
            P("hall %r: 实际摆 %d 件, %d 种 base" % (hk, len(placed), len(bases)))
            P("  base fids:", R(bases, 800))
            P("  ‼ 摆着但不在拥有集的 base:", R(not_owned, 400))
    else:
        P("custom_hall_info 读不到或为空")

    P(">>> 判读:")
    P("  A. 若重登后 owned≈25 且 大厅实际摆放的 base 全∈拥有集 => 那6件是真server拥有(解锁连带了), 矛盾解除, 服务器拒摆=合理。")
    P("  B. 若 owned 仍=889 => pp['14'] 不被服务器覆盖(本地持久), 那'拥有'这判据要换成'大厅实际摆放'来看。")
    P("  C. 若大厅里摆着的 base 有不在拥有集的 => 说明服务器摆放校验不是看 pp['14'], 得另找判据。")
