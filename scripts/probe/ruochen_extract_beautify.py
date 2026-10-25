"""从若辰主程序里提取内嵌的"本地美化"注入 so 和它携带的 Python 脚本。

用法: python ruochen_extract_beautify.py <若辰主程序> <输出目录>

不写死偏移: 在主程序里找第二个 ELF 头(第一个是主程序自己), 按节头表算出 so 的长度;
再在 so 里按 "\nimport json\n" 开头、NUL 结尾截出 kBeautifyScript。
10.1.74 版实测: so 在文件偏移 0x2d6730, 长 0x7530; 脚本在 so 内 +0x7f0, 19959 字节。
"""
import hashlib
import os
import struct
import sys


def find_embedded_elf(data):
    pos = data.find(b"\x7fELF", 4)
    while pos >= 0:
        if data[pos + 4] == 2:  # ELFCLASS64
            e_type, = struct.unpack_from("<H", data, pos + 16)
            shoff, = struct.unpack_from("<Q", data, pos + 0x28)
            shentsize, shnum = struct.unpack_from("<HH", data, pos + 0x3A)
            end = pos + shoff + shentsize * shnum
            if e_type == 3 and shentsize == 64 and end <= len(data):
                return pos, end
        pos = data.find(b"\x7fELF", pos + 4)
    return None


def main():
    src, out_dir = sys.argv[1], sys.argv[2]
    data = open(src, "rb").read()
    hit = find_embedded_elf(data)
    if hit is None:
        sys.exit("没找到内嵌 ELF")
    start, end = hit
    so = data[start:end]
    if b"ruochen_beautify_start_v1" not in so:
        sys.exit("内嵌 ELF 不是美化 so (没有 ruochen_beautify_start_v1)")

    s = so.find(b"\nimport json\n")
    e = so.index(b"\x00", s)
    script = so[s:e]

    os.makedirs(out_dir, exist_ok=True)
    so_path = os.path.join(out_dir, "rc_beautify.so")
    py_path = os.path.join(out_dir, "kBeautifyScript.py")
    open(so_path, "wb").write(so)
    open(py_path, "wb").write(script)
    print("so     file+0x%x..0x%x  %d B  md5 %s" % (start, end, len(so), hashlib.md5(so).hexdigest()))
    print("script so+0x%x  %d B  %d 行" % (s, len(script), script.count(b"\n")))


if __name__ == "__main__":
    main()
