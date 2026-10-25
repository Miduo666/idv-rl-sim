import json, marshal, types, collections, sys
from loadpd import load
HIT = 18
def rows(d): return d.args[1] if hasattr(d, 'args') and len(d.args) > 1 else d
def expand(tbl):
    out = {}
    def get(k):
        if k in out: return out[k]
        v = tbl[k]
        if isinstance(v, dict): r = dict(v)
        else:
            base = v[0]; r = dict(get(base)) if base in tbl else {}
            if len(v) > 1:
                n = v[1]; pairs = v[2:2 + 2 * n]
                for i in range(0, len(pairs), 2): r[pairs[i]] = pairs[i+1]
                for dk in v[2 + 2 * n:]: r.pop(dk, None)   # 尾部 = 从基准行删掉的键
        out[k] = r; return r
    for k in tbl: get(k)
    return out
sst = expand(rows(load('skill_state_table')['data']))
bst = expand(rows(load('butcher_state')['data']))
sk = expand(rows(load('skill')['data']))
fx = load('skill_state_fix')['data']
tid = json.load(open(r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\intl_tid\tid_chs_en.json", encoding='utf-8'))['chs']
# 枚举名
co = marshal.loads(open(r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\std_pyc\common_cs\ComuKeys.pyc", 'rb').read()[16:])
import dis
def enum(name):
    for c in co.co_consts:
        if isinstance(c, types.CodeType) and c.co_name == name:
            m = {}; last = None
            for ins in dis.get_instructions(c):
                if ins.opname == 'LOAD_CONST': last = ins.argval
                elif ins.opname == 'STORE_NAME' and isinstance(last, int): m.setdefault(last, ins.argval)
            return m
stype = enum('SKILL_TYPE')
bco = marshal.loads(open(r"C:\Users\31297\Desktop\逆向\第五人格_脚本解包_反作弊\std_pyc\common_cs\states\StatesConst.pyc", 'rb').read()[16:])
bstate = {}
for c in bco.co_consts:
    if isinstance(c, types.CodeType) and c.co_name == 'BUTCHER_STATE':
        last = None
        for ins in dis.get_instructions(c):
            if ins.opname == 'LOAD_CONST': last = ins.argval
            elif ins.opname == 'STORE_NAME' and isinstance(last, int): bstate.setdefault(last, ins.argval)
res = []
for sid, phases in sorted(fx.items()):
    for ph, p in sorted(phases.items()):
        if p.get('unit_type') != 1: continue
        f = p.get('skill_state_fix'); st = p.get('state_id')
        if f in sst: row = sst[f]; src = 'sst'
        elif st in bst: row = bst[st]; src = 'bs'
        else: row = None; src = '-'
        r = row.get(HIT, 0) if row is not None else None
        s = sk.get(sid, {})
        name = tid.get(s.get('name_tid', ''), s.get('name_tid', ''))
        res.append((sid, ph, r, src, f, st, bstate.get(st, st), s.get('skill_type'), stype.get(s.get('skill_type'), '?'), name, (p.get('skill_state_anim') or ('',))[0]))
blocked = [x for x in res if x[2] == 0]
print('butcher skill phases', len(res), 'blocked', len(blocked), 'unknown', sum(1 for x in res if x[2] is None))
for x in blocked:
    print('\t'.join(str(v) for v in x))
if len(sys.argv) > 1:
    keys = sys.argv[1:]
    for x in res:
        if any(k in str(x[8]) or k in str(x[9]) or k in str(x[10]) for k in keys):
            print('ALL\t' + '\t'.join(str(v) for v in x))
