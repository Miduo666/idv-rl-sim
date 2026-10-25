# -*- coding: utf-8 -*-
# probe2: 本地美化 DISABLE —— 配 cmd_beautify_enable.py(完整版)。
#   卸全部 hook(set_cur_role_cloth / update_article 含扩展层 / BaseUnit.__init__)，
#   还原扩展资源快照，按 beautify_rollback.txt 撤销追加，恢复原穿戴皮，删临时属性。
# (内存写，重启游戏也会自动还原；这个命令用于不重启的干净回滚)
# ⚠ 卸 BaseUnit hook 只影响之后创建的单位，当前这局里已经套上的皮不会变回去。
FILES = '/data/data/com.netease.dwrg/files/'
RB_PATH = FILES + 'beautify_rollback.txt'
EXT_LISTS = ('appendage_list', 'face_frame_list', 'face_vfx_list', 'tag_vfx_list',
             'specific_action_list', 'specific_action_sfx_list',
             'profile_tag_list', 'profile_decoration_list')
_TAG_ORIG = (('LocalArticleUnlockHooked', 'LocalArticleUnlockOriginal'),
             ('LocalResourceUpdateHooked', 'LocalResourceUpdateOriginal'))

def _unwrap(owner, name):
    fn = getattr(owner, name)
    n = 0
    while True:
        d = getattr(fn, '__dict__', {})
        for tag, okey in _TAG_ORIG:
            if d.get(tag) == 1:
                fn = d[okey]; n += 1
                break
        else:
            return fn, n

def _copy(v):
    if isinstance(v, dict): return {k: _copy(x) for k, x in v.items()}
    if isinstance(v, list): return [_copy(x) for x in v]
    if isinstance(v, tuple): return tuple(_copy(x) for x in v)
    return v

a = S(lambda: GK.g_avatar)
if a is None:
    P("g_avatar 未就绪")
else:
    # 卸 hook
    AC = type(a)
    unhooked = {}
    for mname in ("set_cur_role_cloth", "update_article"):
        fn, n = _unwrap(AC, mname)
        if n:
            setattr(AC, mname, fn)
        unhooked[mname] = n
    try:
        from ClientUnits.BaseUnit import BaseUnit
        fn, n = _unwrap(BaseUnit, '__init__')
        if n:
            BaseUnit.__init__ = fn
        unhooked['BaseUnit.__init__'] = n
    except Exception as e:
        unhooked['BaseUnit.__init__'] = 'ERR ' + repr(e)

    # 扩展资源快照还原(先于皮肤回滚，与若辰顺序一致)
    ext_msg = "无快照"
    snap = getattr(a, 'LocalResourceRollback', None)
    if isinstance(snap, dict):
        unlock = getattr(a, 'article_unlock', {})
        if isinstance(unlock, dict):
            o_list = snap.get('unlock', {}); o_keys = set(snap.get('unlock_keys', []))
            for k in list(unlock.keys()):
                if k not in o_keys and k in EXT_LISTS:
                    del unlock[k]
                elif isinstance(unlock.get(k), list) and k in o_list:
                    unlock[k][:] = o_list[k]
        oid = snap.get('appendage_ids')
        if oid is not None and isinstance(getattr(a, 'appendage_id_list', None), list):
            a.appendage_id_list[:] = oid
        ost = snap.get('setting')
        if isinstance(ost, dict) and isinstance(getattr(a, 'article_setting', None), dict):
            a.article_setting.clear(); a.article_setting.update(_copy(ost))
        try: a.appendage_id = snap.get('appendage_id')
        except Exception: pass
        try: del a.LocalResourceRollback
        except Exception: pass
        ext_msg = "已还原"

    # 读回滚清单
    lines = []
    try:
        with open(RB_PATH) as fi:
            lines = fi.read().split('\n')
    except Exception as e:
        P("读回滚文件失败 " + repr(e))
    rc = rd = 0
    dl = a.article_unlock['decoration_list']
    for ln in lines:
        if not ln:
            continue
        f = ln.split('\t')
        if f[0] == 'C' and len(f) == 3:
            role = f[1]
            try: cid = int(f[2])
            except Exception: cid = f[2]
            if role in a.role_cloth and cid in a.role_cloth[role][1]:
                a.role_cloth[role][1].remove(cid); rc += 1
        elif f[0] == 'D' and len(f) == 2:
            try: did = int(f[1])
            except Exception: did = f[1]
            if did in dl:
                dl.remove(did); rd += 1
    # 恢复原穿戴皮
    orig = getattr(a, 'LocalArticleUnlockOriginalCloths', None)
    restored = 0
    if isinstance(orig, dict):
        for role, cloth in list(orig.items()):
            try: a.reply_update_cloth(cloth, {'role_id': int(role)}); restored += 1
            except Exception: pass
    for attr in ('LocalArticleUnlockOriginalCloths', 'LocalArticleUnlockSelectedCloths'):
        try: delattr(a, attr)
        except Exception: pass
    a.update_unlock_cloth_type_info()
    try:
        with open(RB_PATH, 'w') as fo:
            fo.write('')
    except Exception:
        pass
    P("DISABLE 完成：移除皮肤=%d 挂件=%d 恢复穿戴=%d  扩展资源=%s" % (rc, rd, restored, ext_msg))
    P("  卸 hook 层数=%s" % unhooked)
