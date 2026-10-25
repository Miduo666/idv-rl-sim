# -*- coding: utf-8 -*-
"""照游戏跑新手局/剧情局的原路启动：客户端模式 + MODE_CS(本地服务端)，Netease = game_kernel。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simenv


def boot(verbose=True):
    simenv.setup()
    from etc import dev_config
    dev_config.set_cs_mode(dev_config.MODE_CS)
    import game_kernel as GK
    from core.DataManager import DataManager
    GK.DM = DataManager()
    if verbose:
        print("[boot] cs_mode=%s DM=%s global_data=%d keys" % (
            dev_config.COMMON_CS_MODE, type(GK.DM).__name__, len(GK.DM.global_data)))
    return GK
