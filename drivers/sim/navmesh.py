# -*- coding: utf-8 -*-
"""NeoX 导航：.nav = Detour MSET(v7) 总表 + 同名目录下的 .tile；
.tile = [i32 -1][i32 数据长度] + 标准 Detour tile 数据(dtMeshHeader 'DNAV' v7 + verts + polys ...)。
这里只解出 header、顶点、多边形（够做校验/可视化；寻路交给 recastnavigation 库）。"""
import struct, zipfile, re

HDR = struct.Struct("<4s i i i i I i i i i i i i i i f f f 3f 3f f")  # dtMeshHeader (v7)


def parse_tile(b):
    if b[:4] != b"VAND":
        b = b[8:]
    h = HDR.unpack_from(b, 0)
    (magic, ver, x, y, layer, user, npoly, nvert, maxlink, ndm, ndv, ndt, nbv, noff, offbase,
     wh, wr, wc, bminx, bminy, bminz, bmaxx, bmaxy, bmaxz, bvq) = h
    assert magic == b"VAND" and ver == 7, (magic, ver)
    p = HDR.size
    verts = [struct.unpack_from("<3f", b, p + 12 * i) for i in range(nvert)]
    p += 12 * nvert
    polys = []
    for i in range(npoly):                      # dtPoly: firstLink u32, verts u16[6], neis u16[6], flags u16, vertCount u8, areaAndtype u8
        fl, *rest = struct.unpack_from("<I6H6HHBB", b, p)
        pv, nei, flags, vc, at = rest[:6], rest[6:12], rest[12], rest[13], rest[14]
        polys.append({"verts": pv[:vc], "neis": nei[:vc], "flags": flags, "area": at & 0x3F, "type": at >> 6})
        p += 32
    return {"x": x, "y": y, "layer": layer, "verts": verts, "polys": polys,
            "walkable": (wh, wr, wc), "bmin": (bminx, bminy, bminz), "bmax": (bmaxx, bmaxy, bmaxz)}


def tile_names(nav_bytes):
    names = []
    for m in re.finditer(rb"\.tile", nav_bytes):
        e = m.end()
        for L in range(6, 240):
            s0 = e - L
            if s0 < 4: break
            if int.from_bytes(nav_bytes[s0 - 4:s0], "little") == L and all(32 < c < 127 for c in nav_bytes[s0:e]):
                names.append(nav_bytes[s0:e].decode()); break
    return names


def load_nav(z, nav_path):
    nb = z.read(nav_path)
    magic, ver, ntiles = struct.unpack_from("<4sii", nb, 0)
    params = struct.unpack_from("<3f2f2i", nb, 12)
    d = nav_path.rsplit("/", 1)[0] + "/" + nav_path.rsplit("/", 1)[1][:-4]
    tiles = [parse_tile(z.read(d + "/" + n)) for n in tile_names(nb)]
    return {"params": params, "ntiles": ntiles, "tiles": tiles}
