# -*- coding: utf-8 -*-
"""
字段指纹分析器：不靠 IDA，从 dump_frame_objs.bin 里按"值分布特征"反推结构体偏移。
先在旧版本数据上验证能否复现 known_offsets.md 里已知的 +0x70 / +0x1a0 / +0xa8 / +0x148 / +0xaa。
用法: python field_finger.py <dump_frame_objs.bin> <dump_frame_meta.txt>
"""
import sys, struct, re, collections

REC = 8 + 0x300

def load(binp, metap):
    raw = open(binp, 'rb').read()
    n = len(raw) // REC
    objs = []
    for i in range(n):
        base = i * REC
        addr = struct.unpack_from('<Q', raw, base)[0]
        objs.append((addr, raw[base + 8: base + 8 + 0x300]))
    meta = []
    for line in open(metap, encoding='utf-8', errors='replace'):
        m = re.match(r'idx=(\d+) obj=0x([0-9A-Fa-f]+) 阵营=(-?\d+) 类名=(\S*) str=(.*?) coord=\((.*?)\)', line)
        if m:
            meta.append(dict(idx=int(m.group(1)), obj=int(m.group(2), 16),
                             camp=int(m.group(3)), cls=m.group(4), name=m.group(5)))
    return objs, meta


def fingerprint(objs, meta):
    by_addr = {a: b for a, b in objs}
    rows = [(m, by_addr[m['obj']]) for m in meta if m['obj'] in by_addr]
    print('records=%d  matched=%d' % (len(objs), len(rows)))
    camps = collections.Counter(m['camp'] for m, _ in rows)
    print('阵营分布:', dict(camps))

    # 角色 = 阵营1(监管)/2(求生)；场景物 = 阵营3
    chars = [r for r in rows if r[0]['camp'] in (1, 2)]
    scene = [r for r in rows if r[0]['camp'] == 3]
    print('角色=%d 场景物=%d' % (len(chars), len(scene)))

    def col(rs, off, fmt, size):
        return [struct.unpack_from(fmt, b, off)[0] for _, b in rs]

    print('\n--- A. 全局常量型 dword 列（角色间完全一致，且非0）---')
    for off in range(0, 0x300 - 4):
        v = col(chars, off, '<I', 4)
        if len(set(v)) == 1 and v[0] not in (0,) and len(chars) >= 4:
            sv = col(scene, off, '<I', 4) if scene else []
            same_scene = (len(set(sv)) == 1 and sv and sv[0] == v[0])
            f = struct.unpack_from('<f', chars[0][1], off)[0]
            tag = '(场景物同值)' if same_scene else '(场景物不同 <- 有区分力)'
            print('  +0x%03x u32=0x%08X f32=%-14.4g %s' % (off, v[0], f, tag))

    print('\n--- B. 双值/少值型 dword 列（像状态位/枚举）---')
    for off in range(0, 0x300 - 4):
        v = col(rows, off, '<I', 4)
        c = collections.Counter(v)
        if 2 <= len(c) <= 4 and c.most_common(1)[0][1] >= len(v) * 0.4:
            print('  +0x%03x  %s' % (off, ['0x%X x%d' % (k, n) for k, n in c.most_common()]))

    print('\n--- C. 指针型 qword 列（高位 0xB4 规律）---')
    for off in range(0, 0x300 - 8, 8):
        v = col(rows, off, '<Q', 8)
        nz = [x for x in v if x]
        if len(nz) >= len(v) * 0.8 and all((x >> 56) in (0xB4, 0x00) and (x & 0xFFFFFFFFFFFFFF) > 0x5000000000 for x in nz):
            print('  +0x%03x  样例=0x%016X ... 非空%d/%d' % (off, nz[0], len(nz), len(v)))

    print('\n--- D. 已知偏移回读校验 ---')
    for off, desc in [(0x28, 'objcoor 指针'), (0x70, 'jxpd 状态'), (0xa8, '已使用标志'),
                      (0x148, '箱子用完标志'), (0x1a0, '阵营判定 450.0f'), (0x298, 'pd2')]:
        vs = []
        for m, b in rows[:12]:
            u = struct.unpack_from('<I', b, off)[0]
            f = struct.unpack_from('<f', b, off)[0]
            vs.append('%s:0x%X/%.3g' % (m['name'][:6], u, f))
        print('  +0x%03x %-16s %s' % (off, desc, ' '.join(vs)))
    print('  +0x0aa 1字节标志:', [(m['name'][:6], hex(b[0xaa])) for m, b in rows[:12]])


if __name__ == '__main__':
    o, mt = load(sys.argv[1], sys.argv[2])
    fingerprint(o, mt)
