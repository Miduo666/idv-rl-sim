# -*- coding: utf-8 -*-
"""NeoX profiling 模块替代：返回一台固定的"高端安卓机"的设备信息，让性能分档等逻辑走确定分支。"""
import simenv


def get_device_model(*a): return "SIM-DEVICE"
def get_video_card_name(*a): return "Adreno (TM) 740"
def get_cpu_name(*a): return "Qualcomm Technologies, Inc SM8550"
def get_total_memory(*a): return 16 * 1024
def get_process_mem_used(*a): return 1024
def get_cpu_core_count(*a): return 8
def get_logic_rate(*a): return 30.0


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    simenv.ACCESS["profiling." + name] += 1
    return simenv.Stub("profiling." + name)
