# -*- coding: utf-8 -*-
"""编译 acl_c（官方 ACL v1.2.1 解码 + 薄 C 封装）为共享库，Windows(mingw g++) 与 Linux(g++) 通用。
用法: python build.py        产物: natives/bin/acl_c.dll | libacl_c.so
ACL 是纯头文件库；源码不在仓库里：首次运行把固定版本浅克隆到 tools/_deps/acl。
版本依据：RAWANIMA 里 ACL 块的 m_version=4，ACL get_algorithm_version(UniformlySampled) 在 v1.2.0/v1.2.1 为 4（v1.1=3，v1.3=5）。"""
import os, sys, subprocess

TAG = "v1.2.1"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
DEPS = os.path.join(REPO_ROOT, "tools", "_deps", "acl")
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "bin"))


def main():
    if not os.path.isdir(os.path.join(DEPS, "includes", "acl")):
        subprocess.check_call(["git", "clone", "-q", "--depth", "1", "--branch", TAG,
                               "https://github.com/nfrechette/acl.git", DEPS])
    os.makedirs(OUT_DIR, exist_ok=True)
    win = sys.platform == "win32"
    out = os.path.join(OUT_DIR, "acl_c.dll" if win else "libacl_c.so")
    src = os.path.join(HERE, "acl_c.cpp")
    cmd = ["g++", "-O2", "-shared", "-std=c++11", "-msse4.1", "-I", os.path.join(DEPS, "includes"), "-o", out, src]
    cmd += ["-static", "-static-libgcc", "-static-libstdc++"] if win else ["-fPIC", "-D__declspec(x)="]
    print(" ".join(cmd[:9]), "...")
    subprocess.check_call(cmd)
    print("->", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
