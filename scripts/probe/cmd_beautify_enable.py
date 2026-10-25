# -*- coding: utf-8 -*-
# probe2: 本地美化 ENABLE(完整版，对齐若辰 kBeautifyScript.py)—— 写游戏状态。
#   1. DM.cloth_data 全部皮肤追加进 role_cloth[role][1]；DM.decoration_data 全部挂件追加进 decoration_list
#   2. hook set_cur_role_cloth：本地回执 reply_update_cloth + 记 LocalArticleUnlockSelectedCloths + 刷新换装 UI
#   3. hook update_article(DECORATION)：本地回执 reply_update_decoration
#   4. hook ClientUnits.BaseUnit.BaseUnit.__init__：创建"自己"的单位时把 cloth_id/model/article_setting
#      换成本地选择 —— 局内套皮(只有自己看得到)
#   5. EXT=True 时再解锁扩展资源(随身物品/头像框/动作/特效...)，update_article 的 type 2/6/9/21 走本地回执
# 可重复投：已装的 hook(含旧版 enable 装的)先拆到原函数再装新版；回滚清单与本进程旧清单合并。
# ⚠ BaseUnit hook 只影响之后创建的单位：大厅投 → 下一局生效；局内投 → 要等下一局。
# ⚠ 别把伪造物品设进个人资料/名片去保存或分享(会上行 illegal_articles 校验)。
# 局内套皮诊断写 beautify_unit_diag.txt；回滚清单 beautify_rollback.txt，配 cmd_beautify_disable.py。
import traceback

# ‼ 2026-10-16 23:48 实测：EXT=True 投递后约 1s 游戏 native 崩溃(SIGSEGV, 引擎 JobSystem 线程 Thread-34, libclient.so)。
#   probe2 跑在 Python 后台线程，扩展段在非主线程连续调几百次 reply_unlock_face / 改 article_setting 默认值，
#   跟引擎主线程抢同一批 UI/资源对象。崩溃现场存档：逆向存档\_crash\20261016_2348_beautify\。没改成主线程调度前不要开。
EXT = False
FILES = '/data/data/com.netease.dwrg/files/'
RB_PATH = FILES + 'beautify_rollback.txt'
UNIT_DIAG = FILES + 'beautify_unit_diag.txt'
MODEL_OVERRIDES = {}   # {'角色id字符串': 'model_path'}，同若辰 LOCAL_BEAUTIFY_MODEL_OVERRIDES

_TAG_ORIG = (('LocalArticleUnlockHooked', 'LocalArticleUnlockOriginal'),
             ('LocalResourceUpdateHooked', 'LocalResourceUpdateOriginal'))

def _unwrap(owner, name):
    # 一层层拆掉我们装过的 hook，返回(真正的原函数, 拆掉的层数)
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

a  = S(lambda: GK.g_avatar)
dm = S(lambda: GK.DM)
if a is None or dm is None:
    P("g_avatar/DM 未就绪，稍后重试")
else:
    from common_cs import ComuKeys
    _CLOTH = ComuKeys.ARTICLE_TYPE.CLOTH
    _DECO = ComuKeys.ARTICLE_TYPE.DECORATION
    AC = type(a)

    # ---------- 1. 追加拥有 ----------
    pending_c = []
    for cid, cdv in list(dm.cloth_data.items()):
        role = str(S(lambda cdv=cdv: cdv['role_id']))
        if role in a.role_cloth and cid not in a.role_cloth[role][1]:
            pending_c.append((role, cid))
    dl = a.article_unlock['decoration_list']
    pending_d = [did for did in list(dm.decoration_data) if did not in dl]
    for role, cid in pending_c:
        a.role_cloth[role][1].append(cid)
    for role in a.role_cloth:
        try: a.role_cloth[role][1].sort()
        except Exception: pass
    for did in pending_d:
        dl.append(did)
    a.update_unlock_cloth_type_info()

    # ---------- 2. 换皮 hook ----------
    def _ApplySel(av, role_key, cloth_id):
        role_key = str(role_key)
        orig = getattr(av, 'LocalArticleUnlockOriginalCloths', None)
        if orig is None:
            orig = {}; av.LocalArticleUnlockOriginalCloths = orig
        if role_key not in orig and role_key in av.role_cloth:
            orig[role_key] = av.role_cloth[role_key][0]
        sel = getattr(av, 'LocalArticleUnlockSelectedCloths', None)
        if sel is None:
            sel = {}; av.LocalArticleUnlockSelectedCloths = sel
        sel[role_key] = cloth_id
        av.reply_update_cloth(cloth_id, {'role_id': int(role_key)})
        for ui_name in ('UIGoldRushArticle', 'UIBattleGoldRushChangeCloth'):
            try:
                ui = GK.g_ui_mgr.get_ui(ui_name)
                if ui: ui.update_item_on_setting(_CLOTH, cloth_id, int(role_key))
            except Exception:
                pass

    _orig_set, n_set = _unwrap(AC, 'set_cur_role_cloth')
    def _SetCloth(self, role_id_str, cloth_id, will_start_game, need_reply=False, match_type=None):
        _ApplySel(self, role_id_str, cloth_id)
        return None
    _SetCloth.LocalArticleUnlockHooked = 1
    _SetCloth.LocalArticleUnlockOriginal = _orig_set
    AC.set_cur_role_cloth = _SetCloth

    # 旧版 hook 换过的角色：当前皮就是本地选的，补记进 Selected
    sel = getattr(a, 'LocalArticleUnlockSelectedCloths', None)
    if sel is None:
        sel = {}; a.LocalArticleUnlockSelectedCloths = sel
    for role in list(getattr(a, 'LocalArticleUnlockOriginalCloths', {}) or {}):
        if role not in sel and role in a.role_cloth:
            sel[role] = a.role_cloth[role][0]

    # ---------- 3. 挂件 hook ----------
    _orig_ua, n_ua = _unwrap(AC, 'update_article')
    def _UA(self, article_type, article_id, info=None):
        if article_type == _DECO:
            self.reply_update_decoration(article_id, info); return None
        return _orig_ua(self, article_type, article_id, info)
    _UA.LocalArticleUnlockHooked = 1
    _UA.LocalArticleUnlockOriginal = _orig_ua
    AC.update_article = _UA

    # ---------- 4. 局内套皮 hook ----------
    def _udiag(st, msg):
        log = st.setdefault('log', [])
        log.append('%.0f %s' % (time.time(), msg))
        del log[:-40]
        try:
            with open(UNIT_DIAG, 'w') as fo:
                fo.write('\n'.join(log))
        except Exception:
            pass

    def _LocalCloth(av, role_id):
        rk = str(role_id)
        if rk not in av.role_cloth:
            return None
        return (getattr(av, 'LocalArticleUnlockSelectedCloths', None) or {}).get(rk, av.role_cloth[rk][0])

    def _BuildLocal(params, av, role_id):
        local = dict(params)
        if isinstance(getattr(av, 'article_setting', None), dict):
            local['article_setting'] = _copy(av.article_setting)
        cid = _LocalCloth(av, role_id)
        if cid is not None and cid in GK.DM.cloth_data:
            local['cloth_id'] = cid
            mp = MODEL_OVERRIDES.get(str(role_id))
            if mp is None:
                mp = S(lambda: GK.DM.cloth_data[cid]['model_path'])
            if mp:
                local['model'] = mp
        return local

    unit_hook = "未装"
    try:
        from ClientUnits.BaseUnit import BaseUnit
        _orig_init, n_init = _unwrap(BaseUnit, '__init__')
        def _UnitInit(self, params, *args, **kw):
            st = _UnitInit.__dict__
            st['calls'] = st.get('calls', 0) + 1
            try:
                if isinstance(params, dict):
                    ri = getattr(params.get('room'), 'info_dict', None)
                    su = ri.get('self_uid') if hasattr(ri, 'get') else None
                    if st['calls'] == 1:
                        _udiag(st, 'first_call keys=%s self_uid=%r uid=%r pid=%r' % (
                            sorted(str(k) for k in params.keys())[:60], su, params.get('uid'), params.get('pid')))
                    av = GK.g_avatar
                    if su is not None and av is not None and params.get('uid') == su:
                        old = (params.get('cloth_id'), params.get('model'))
                        local = _BuildLocal(params, av, params.get('pid'))
                        params.clear()
                        params.update(local)
                        st['hits'] = st.get('hits', 0) + 1
                        _udiag(st, 'HIT pid=%r cloth %r -> %r  model %r -> %r' % (
                            params.get('pid'), old[0], params.get('cloth_id'), old[1], params.get('model')))
            except Exception:
                st['errors'] = st.get('errors', 0) + 1
                _udiag(st, 'ERR ' + traceback.format_exc())
            return _orig_init(self, params, *args, **kw)
        _UnitInit.LocalArticleUnlockHooked = 1
        _UnitInit.LocalArticleUnlockOriginal = _orig_init
        BaseUnit.__init__ = _UnitInit
        co = getattr(_orig_init, '__code__', None)
        unit_hook = "已装(拆旧层=%d) 原签名=%s" % (
            n_init, co.co_varnames[:co.co_argcount] if co else '?')
    except Exception:
        unit_hook = "失败 " + traceback.format_exc()

    # ---------- 5. 扩展资源 ----------
    ext_msg = "跳过(EXT=False)"
    if EXT:
        LISTS = ('appendage_list', 'face_frame_list', 'face_vfx_list', 'tag_vfx_list',
                 'specific_action_list', 'specific_action_sfx_list',
                 'profile_tag_list', 'profile_decoration_list')
        def _tbl(stem):
            for nm in (stem + '_data', stem + 's_data', stem, stem + '_list_data'):
                t = getattr(dm, nm, None)
                if hasattr(t, 'keys'): return t
            return None
        def _reply(m, aid, info=None):
            try: return m(aid, info)
            except TypeError:
                try: return m(aid)
                except TypeError: return m(aid, info, False)
        unlock = a.article_unlock
        setting = getattr(a, 'article_setting', None)
        app_ids = getattr(a, 'appendage_id_list', None)
        if getattr(a, 'LocalResourceRollback', None) is None:   # 只在第一次快照，保留真正的原始状态
            a.LocalResourceRollback = {
                'unlock_keys': list(unlock.keys()),
                'unlock': {k: list(v) for k, v in unlock.items() if isinstance(v, list)},
                'appendage_ids': list(app_ids) if isinstance(app_ids, list) else None,
                'setting': _copy(setting) if isinstance(setting, dict) else None,
                'appendage_id': getattr(a, 'appendage_id', None),
            }
        changed = 0
        app_tbl = getattr(dm, 'appendage_data', None) or {}
        app_keys = list(app_tbl.keys()) if hasattr(app_tbl, 'keys') else []
        if isinstance(app_ids, list):
            for i in app_keys:
                if i not in app_ids: app_ids.append(i); changed += 1
            try: app_ids.sort()
            except Exception: pass
        for ln in LISTS:
            tgt = unlock.get(ln)
            if not isinstance(tgt, list): continue
            t = app_tbl if ln == 'appendage_list' else _tbl(ln[:-5])
            if t is None or not hasattr(t, 'keys'): continue
            for i in list(t.keys()):
                if i not in tgt: tgt.append(i); changed += 1
            try: tgt.sort()
            except Exception: pass
        if isinstance(setting, dict):
            for sname, ln in (('face_frame_id', 'face_frame_list'), ('face_vfx_id', 'face_vfx_list'),
                              ('tag_vfx_id', 'tag_vfx_list'), ('appendage_id', 'appendage_list')):
                vals = unlock.get(ln, [])
                if vals and setting.get(sname) is None: setting[sname] = vals[0]
        face_tbl = getattr(dm, 'face_data', None) or {}
        face_reply = getattr(a, 'reply_unlock_face', None)
        if callable(face_reply) and hasattr(face_tbl, 'keys'):
            for fid in list(face_tbl.keys()):
                try: _reply(face_reply, fid, None); changed += 1
                except Exception: pass
        # 扩展 hook 包在挂件 hook 外层(与若辰顺序一致)
        _inner_ua = AC.update_article
        _REPLIES = {2: 'reply_update_specific_action', 6: 'reply_update_appendage',
                    9: 'reply_update_face', 21: 'reply_update_specific_action_sfx'}
        def _ExtUA(self, article_type, article_id, info=None):
            try: tid = int(article_type)
            except Exception: tid = article_type
            rep = getattr(self, _REPLIES.get(tid, ''), None)
            if callable(rep):
                if tid == 6:
                    rid = info.get('role_id', info.get('pid', info.get('role_id_str'))) if isinstance(info, dict) else None
                    st_ = getattr(self, 'article_setting', None)
                    if isinstance(st_, dict):
                        rm = st_.get('role_appendage')
                        if not isinstance(rm, dict): rm = {}; st_['role_appendage'] = rm
                        if rid is not None: rm[str(rid)] = article_id
                    try: self.appendage_id = article_id
                    except Exception: pass
                try: _reply(rep, article_id, info)
                except Exception: pass
                return None
            return _inner_ua(self, article_type, article_id, info)
        _ExtUA.LocalResourceUpdateHooked = 1
        _ExtUA.LocalResourceUpdateOriginal = _inner_ua
        AC.update_article = _ExtUA
        ext_msg = "extended=%d" % changed

    # ---------- 回滚清单(本进程已装过 → 与旧清单合并；新进程 → 覆盖掉上次游戏留下的) ----------
    rb = ['C\t%s\t%s' % (r, c) for r, c in pending_c] + ['D\t%s' % d for d in pending_d]
    if n_set or n_ua:
        try:
            with open(RB_PATH) as fi:
                old = [x for x in fi.read().split('\n') if x]
            seen = set(old)
            rb = old + [x for x in rb if x not in seen]
        except Exception:
            pass
    try:
        with open(RB_PATH, 'w') as fo:
            fo.write('\n'.join(rb))
        rb_ok = True
    except Exception as e:
        rb_ok = False; P("回滚落盘失败 " + repr(e))

    P("ENABLE 完成：追加皮肤=%d 挂件=%d  回滚落盘=%s(%d 行)" % (len(pending_c), len(pending_d), rb_ok, len(rb)))
    P("  set_cur_role_cloth 已装(拆旧层=%d)  update_article 已装(拆旧层=%d)" % (n_set, n_ua))
    P("  BaseUnit.__init__ " + unit_hook)
    P("  扩展资源 " + ext_msg)
    P("  已记本地选择 Selected=%s" % R(dict(a.LocalArticleUnlockSelectedCloths), 300))
    P("  → 局内套皮下一局生效；进局后投 cmd_beautify_check.py 看 HIT")
