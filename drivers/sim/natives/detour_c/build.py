# -*- coding: utf-8 -*-
"""编译 detour_c（官方 Detour v1.6.0 + 薄 C 封装）为共享库，Windows(mingw g++) 与 Linux(g++) 通用。
用法: python build.py        产物: natives/bin/detour_c.dll | libdetour_c.so
源码不在仓库里：首次运行把 recastnavigation 固定版本浅克隆到 tools/_deps/。"""
import os, sys, subprocess, glob

TAG = "v1.6.0"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DEPS = os.path.join(REPO_ROOT, "tools", "_deps", "recastnavigation")
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "bin"))


def main():
    if not os.path.isdir(os.path.join(DEPS, "Detour")):
        subprocess.check_call(["git", "clone", "-q", "--depth", "1", "--branch", TAG,
                               "https://github.com/recastnavigation/recastnavigation.git", DEPS])
    os.makedirs(OUT_DIR, exist_ok=True)
    win = sys.platform == "win32"
    out = os.path.join(OUT_DIR, "detour_c.dll" if win else "libdetour_c.so")
    srcs = [os.path.join(HERE, "detour_c.cpp")] + sorted(glob.glob(os.path.join(DEPS, "Detour", "Source", "*.cpp")))
    cmd = ["g++", "-O2", "-shared", "-std=c++11", "-I", os.path.join(DEPS, "Detour", "Include"), "-o", out] + srcs
    # Windows 下静态链接运行库，DLL 不依赖 mingw 的 libstdc++/libgcc
    cmd += ["-static", "-static-libgcc", "-static-libstdc++"] if win else ["-fPIC"]
    print(" ".join(cmd[:8]), "...")
    subprocess.check_call(cmd)
    print("->", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
