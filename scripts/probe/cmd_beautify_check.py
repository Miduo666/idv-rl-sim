# -*- coding: utf-8 -*-
# probe2 命令：本地美化「前置检查」—— 只读，不写任何游戏状态。
# 验证 kBeautifyScript 用到的对象/方法/字段在当前游戏版本是否仍存在 + 抽样几个值。
# 环境变量(GK/me/S/P/R/cname/idict...)见 probe2.run_cmd；用法 send_cmd.ps1 cmd_beautify_check.py beautify

a  = S(lambda: GK.g_avatar)
dm = S(lambda: GK.DM)
P("== 本地美化前置检查(只读) ==")
P("g_avatar = %s   DM = %s" % (cname(a) if a is not None else None,
                               cname(dm) if dm is not None else None))

P("\n-- Avatar 方法/属性是否存在(inst=实例上 cls=类上) --")
for n in ("role_cloth", "article_unlock", "article_setting",
          "set_cur_role_cloth", "update_article", "reply_update_cloth",
          "reply_update_decoration", "update_unlock_cloth_type_info"):
    P("  %-32s inst=%s cls=%s" % (n,
        S(lambda n=n: hasattr(a, n), False),
        S(lambda n=n: hasattr(type(a), n), False)))

P("\n-- role_cloth 抽样(当前皮 / 已拥有数) --")
rc = S(lambda: a.role_cloth)
if rc is not None:
    ks = S(lambda: list(rc.keys()), [])
    P("  role 数=%d" % len(ks))
    for k in ks[:5]:
        P("    role %-6s 当前皮=%s 已拥有数=%s" % (
            str(k), R(S(lambda k=k: rc[k][0]), 12), R(S(lambda k=k: len(rc[k][1])), 10)))

P("\n-- article_unlock['decoration_list'] 长度 = %s" %
  R(S(lambda: len(a.article_unlock['decoration_list'])), 20))

P("\n-- DM 配表 --")
cd = S(lambda: dm.cloth_data)
P("  cloth_data: has=%s count=%s" % (cd is not None, R(S(lambda: len(cd)), 20)))
if cd is not None:
    cid = S(lambda: next(iter(cd)))
    P("    sample cloth_id=%s keys=%s" % (R(cid, 20), R(S(lambda: list(cd[cid].keys())), 240)))
    P("    'role_id'/'model_path' 在不在: %s" %
      R(S(lambda: ('role_id' in cd[cid], 'model_path' in cd[cid])), 40))
dd = S(lambda: dm.decoration_data)
P("  decoration_data: has=%s count=%s" % (dd is not None, R(S(lambda: len(dd)), 20)))

P("\n-- 局内套皮 BaseUnit.__init__ --")
try:
    from ClientUnits.BaseUnit import BaseUnit
    ui = BaseUnit.__init__
    ud = getattr(ui, '__dict__', {})
    co = getattr(ud.get('LocalArticleUnlockOriginal', ui), '__code__', None)
    P("  import OK  原签名=%s" % (co.co_varnames[:co.co_argcount] if co else '?',))
    P("  hook 已装=%s calls=%s hits=%s errors=%s" % (
        ud.get('LocalArticleUnlockHooked') == 1, ud.get('calls', 0), ud.get('hits', 0), ud.get('errors', 0)))
except Exception as e:
    P("  BaseUnit 不可用: " + repr(e))
P("  Selected=%s" % R(S(lambda: dict(a.LocalArticleUnlockSelectedCloths)), 300))
P("  room self_uid=%s" % R(S(lambda: GK.g_room.info_dict.get('self_uid')), 40))
P("  unit_diag 尾部:")
for ln in S(lambda: open('/data/data/com.netease.dwrg/files/beautify_unit_diag.txt').read().split('\n')[-8:], []):
    P("    " + R(ln, 400))

P("\n== 判读：上面 inst/cls 全 True + cloth_data/decoration_data 有 count + role_cloth 有样本")
P("   => kBeautifyScript 的属性名在本版成立，可进下一步(enable)。任一 False/None 要先改名字。 ==")
