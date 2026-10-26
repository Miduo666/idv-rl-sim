# -*- coding: utf-8 -*-
"""NeoX3 RAWANIMA(.animation) 解析。

文件:  "RAWANIMA" [u32 总长][u32 0][u32 0][u32 HEAD 偏移][8B 哈希?][u32 ?][u32 ?][u32 n][n B 骨骼文件相对路径]
       然后是块 [4B 标签][u32 长度][内容]：HEAD / DATA / NAME
HEAD:  [f32 帧率][f32 时长秒][u8×8 未知][u8 格式][u8 ?]...   格式 2=关键帧 1=ACL v1.2 CompressedClip 0=未知(极少)
NAME:  [u32 串数][u32 len+源动画名(=配置里的文件名/动画名)][(u32 len+骨骼名)×(串数-1)][补零]
DATA 格式 2（全部样本恰好解析到块尾，补零对齐）:
       [u8 =4] + 每根骨骼(按 NAME 顺序) { T: u16 n, n×(u16 帧, half3)
                                         S: u16 n, n×(u16 帧, half3)
                                         R: u16 n, n×(u16 帧, u32 压缩四元数) }
       R 的 u32 = smallest-three：最高 2 位 = 最大分量下标(xyzw)，其余三个分量按"最大分量之后的循环顺序"
       高位在前各 10 位、线性映射到 [-1/√2, 1/√2]，最大分量 = √(1-其余平方和)。
       依据(rawanim_quatfit.py，管家包)：同骨骼文件的 ACL 动画里全局常量骨骼 48/49 一致；相邻关键帧连续性 0.9992（次优映射 0.9976）。
DATA 格式 1: ACL v1.2.1 CompressedClip，用 natives/acl_c 解。
"""
import struct, os, ctypes
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_S = 1 / np.sqrt(2)


def decode_quat32(v):
    """u32 数组 → (n,4) xyzw 四元数。"""
    v = np.asarray(v, dtype=np.uint32)
    idx = (v >> 30) & 3
    a = np.stack([(v >> 20) & 1023, (v >> 10) & 1023, v & 1023], axis=-1).astype(np.float64) / 1023.0 * 2 * _S - _S
    big = np.sqrt(np.clip(1 - (a * a).sum(-1), 0, None))
    q = np.zeros(v.shape + (4,))
    n = np.arange(v.size).reshape(v.shape)
    q[n, idx] = big
    for k in range(3):
        q[n, (idx + 1 + k) % 4] = a[..., k]
    return q


class RawAnim:
    def __init__(self, data):
        d = data
        assert d[:8] == b"RAWANIMA", d[:8]
        n, = struct.unpack_from("<I", d, 0x28)
        self.skeleton = d[0x2c:0x2c + n].decode("utf-8", "replace")
        self.chunks = {}
        o = 0x2c + n
        while o + 8 <= len(d):
            tag = d[o:o + 4]; sz, = struct.unpack_from("<I", d, o + 4)
            self.chunks[tag] = (o + 8, sz)
            o += 8 + sz
        ho, hs = self.chunks[b"HEAD"]
        self.head = d[ho:ho + hs]
        self.fps, self.duration = struct.unpack_from("<2f", d, ho)
        self.fmt = d[ho + 16]
        no, ns = self.chunks[b"NAME"]
        cnt, = struct.unpack_from("<I", d, no)
        strs, p = [], no + 4
        for _ in range(cnt):
            l, = struct.unpack_from("<I", d, p)
            strs.append(d[p + 4:p + 4 + l].decode("utf-8", "replace")); p += 4 + l
        self.name, self.bones = strs[0], strs[1:]
        self._d = d
        self.tracks = None
        if self.fmt == 2:
            self.tracks = self._parse_keyframes()

    def _parse_keyframes(self):
        d = self._d
        o, sz = self.chunks[b"DATA"]
        end = o + sz
        assert d[o] == 4, d[o]
        o += 1
        out = []
        for _ in self.bones:
            bone = []
            for w in (6, 6, 4):
                n, = struct.unpack_from("<H", d, o); o += 2
                rec = np.frombuffer(d, dtype=np.uint8, count=n * (2 + w), offset=o).reshape(n, 2 + w)
                o += n * (2 + w)
                frames = rec[:, :2].copy().view("<u2").ravel()
                if w == 6:
                    vals = rec[:, 2:].copy().view("<f2").astype(np.float32)
                else:
                    vals = rec[:, 2:].copy().view("<u4").ravel()
                bone.append((frames, vals))
            out.append(bone)
        assert o <= end and not d[o:end].strip(b"\0"), "DATA 尾部非零"
        return out

    # —— 采样 ——
    def translation(self, bone, t):
        """骨骼 bone(下标或名字) 在 t 秒的局部位移（关键帧线性插值，端点外取端点值）。"""
        if isinstance(bone, str):
            bone = self.bones.index(bone)
        if self.fmt == 1:
            return acl_sample(self._acl_buf(), t)[bone, 4:7]
        frames, vals = self.tracks[bone][0]
        if len(frames) == 0:
            return None
        f = t * self.fps
        return np.array([np.interp(f, frames, vals[:, k]) for k in range(3)], dtype=np.float64)

    def _acl_buf(self):
        if getattr(self, "_aclbuf", None) is None:
            o, sz = self.chunks[b"DATA"]
            self._aclbuf = aligned_copy(self._d[o:o + sz])
        return self._aclbuf


# —— ACL（格式 1）——
_acl = None


def _lib():
    global _acl
    if _acl is None:
        name = "acl_c.dll" if os.name == "nt" else "libacl_c.so"
        _acl = ctypes.CDLL(os.path.join(HERE, "natives", "bin", name))
        _acl.acl_info.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_int)] * 2 + [ctypes.POINTER(ctypes.c_float)] + [ctypes.POINTER(ctypes.c_int)] * 2
        _acl.acl_sample.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_int, ctypes.c_void_p]
    return _acl


def aligned_copy(b):
    """ACL 要求 16 字节对齐。返回 (numpy 缓冲区, 对齐后的指针) 并保持引用。"""
    raw = np.zeros(len(b) + 32, dtype=np.uint8)
    off = (-raw.ctypes.data) % 16
    raw[off:off + len(b)] = np.frombuffer(b, dtype=np.uint8)
    return raw, raw.ctypes.data + off


def acl_info(buf):
    nb, ns, hs, ok = (ctypes.c_int() for _ in range(4)); sr = ctypes.c_float()
    r = _lib().acl_info(buf[1], ctypes.byref(nb), ctypes.byref(ns), ctypes.byref(sr), ctypes.byref(hs), ctypes.byref(ok))
    if r:
        raise ValueError("ACL 数据无效")
    return dict(num_bones=nb.value, num_samples=ns.value, sample_rate=sr.value, has_scale=hs.value, hash_ok=ok.value)


def acl_sample(buf, t, rounding=0):
    nb = acl_info(buf)["num_bones"]
    out = np.zeros((nb, 10), dtype=np.float32)
    if _lib().acl_sample(buf[1], ctypes.c_float(t), rounding, out.ctypes.data):
        raise ValueError("ACL 解码失败")
    return out
