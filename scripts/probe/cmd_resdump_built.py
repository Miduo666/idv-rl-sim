# -*- coding: utf-8 -*-
# probe2: 一次性按路径从游戏资源系统取出【模拟器要用的全部地图几何】，可选采集引擎碰撞真值。
#   阶段 A  按 scene_config / 离线清单 / 派生规则 收集路径并取文件（.scn .scn_col .col_mesh .col .nav .postprocess 及碰撞 .gim）
#   阶段 B  解析每个 .nav(Detour MSET) 里列出的 .tile，按候选目录取全部分块
#   阶段 C  解析 .scn 场景描述里引用的上述类型文件，补取
#   ---- 关闭 zip，写 files_done（之后即使崩溃，文件也已落盘）----
#   阶段 D  若当前在对局里：对静态场景碰撞/全碰撞打射线，记录 (起点,终点)->结果，作为模拟器碰撞的校验真值
#   阶段 E  记录 C_file / 场景碰撞对象 / 碰撞管理器 的接口清单
# 后台线程跑，命令本身立即返回。进度: resdump/progress.json；日志: resdump/log.txt
import os, json, time, re, threading, traceback

OUT = globals().get("RESDUMP_OUT", "/sdcard/Android/data/com.netease.dwrg/files/resdump")
RAY_BUDGET_SEC = globals().get("RESDUMP_RAY_BUDGET", 150)
KEEP_EXT = ("scn", "scn_col", "col_mesh", "col", "nav", "tile", "postprocess")
PATH_RE = re.compile(r"^[A-Za-z0-9_./\\\-]+\.([A-Za-z0-9_]{1,12})$")
EXPLICIT = json.loads(r'''["chr/boss/burke/burke_console.gim", "chr/boss/burke/burke_wall.gim", "chr/boss/burke/burke_wall_static.gim", "chr/boss/joseph/h55_joseph_camera.gim", "chr/boss/spider/h55_butcher_spider_cocoon.gim", "chr/creature/crow/crow.gim", "chr/dual_prop/h55_dual_chest01.gim", "chr/dual_prop/h55_dual_hangnail01.gim", "chr/dual_prop/h55_dual_telephonebox01.gim", "chr/guajian/h55_guajian_bingdong/h55_guajian_bingdong_ice.gim", "chr/prop/h55_pendant_cam_burke/h55_pendant_cam_burke.gim", "scene/model/battle_activity_prop/battle_activity_foolday26/activity_foolday26_box01.gim", "scene/model/battle_activity_prop/battle_activity_foolday26/dm65_scene_sender_01.gim", "scene/model/battle_activity_prop/battle_activity_foolday26/dm65_scene_sender_01_low.gim", "scene/model/battle_activity_prop/battle_activity_foolday26/dm65_scene_sender_03.gim", "scene/model/battle_activity_prop/battle_activity_foolday26/dm65_scene_sender_03_low.gim", "scene/model/battle_activity_prop/battle_activity_spring24/battle_activity_spring2023_doorpaint01.gim", "scene/model/battle_activity_prop/battle_activity_spring24/battle_activity_spring2023_doorpaint02.gim", "scene/model/battle_activity_prop/battle_activity_spring26/activity_spring26_boxpaint01.gim", "scene/model/battle_activity_prop/battle_activity_spring26/activity_spring26_boxpaint02a.gim", "scene/model/battle_activity_prop/battle_activity_spring26/activity_spring26_boxpaint02b.gim", "scene/model/battle_activity_prop/battle_activity_spring26/activity_spring26_boxpaint03a.gim", "scene/model/battle_activity_prop/battle_activity_spring26/activity_spring26_boxpaint03b.gim", "scene/model/battle_activity_prop/battle_activity_spring26/activity_spring26_chair.gim", "scene/model/battle_activity_prop/battle_activity_spring26/activity_spring26_chair_dis.gim", "scene/model/battle_activity_prop/battle_activity_spring26/activity_spring26_chair_low.gim", "scene/model/battle_activity_prop/battle_activity_spring26/activity_spring26_denglong01.gim", "scene/model/dm65_main/h55_main_anniversary01.gim", "scene/model/dm65_main/h55_main_anniversary01_distantview.gim", "scene/model/dm65_main/h55_main_anniversary01_low.gim", "scene/model/h55_activity_summer2025/activity_summer2025_table01.col", "scene/model/h55_asylum/dm65_scene_cabinet_03_lod_close.gim", "scene/model/h55_chinatown/h55_chinatown_wall02a.gim", "scene/model/h55_chinatown/h55_chinatown_wall02b.gim", "scene/model/h55_chinatown/h55_chinatown_wall02c.gim", "scene/model/h55_chinatown/h55_chinatown_wall02d.gim", "scene/model/h55_demo/h55_demo_softwall01a.gim", "scene/model/h55_demo/h55_demo_softwall01b.gim", "scene/model/h55_demo/h55_demo_softwall01c.gim", "scene/model/h55_demo/h55_demo_softwall02a.gim", "scene/model/h55_demo/h55_demo_softwall02b.gim", "scene/model/h55_demo/h55_demo_softwall02c.gim", "scene/model/h55_demo/h55_demo_softwall03a.gim", "scene/model/h55_demo/h55_demo_softwall03b.gim", "scene/model/h55_demo/h55_demo_softwall03c.gim", "scene/model/h55_demo2/h55_demo2_cabinet01_lod_close.gim", "scene/model/h55_demo2/h55_demo_halloweenbat01.gim", "scene/model/h55_demo2/h55_demo_halloweenbox01.gim", "scene/model/h55_demo2/h55_demo_halloweenbox01lod.gim", "scene/model/h55_demo2/h55_demo_sender01.gim", "scene/model/h55_demo2/h55_demo_sender01_distantview.gim", "scene/model/h55_demo2/h55_demo_sender01alow.gim", "scene/model/h55_demo2/h55_demo_woodplane01_lod_destroy.gim", "scene/model/h55_demo2/h55_demo_woodplane01_lod_down.gim", "scene/model/h55_demo2/h55_demo_woodplane01_lod_up.gim", "scene/model/h55_hospital2_dmm/dm65_scene_cabinet_01_dmm.gim", "scene/model/h55_hospital2_dmm/dm65_scene_gallows_dmm.gim", "scene/model/h55_hospital2_dmm/dm65_scene_sender_01_dmm.gim", "scene/model/h55_hospital2_dmm/dm65_scene_sender_03_dmm.gim", "scene/model/h55_hospital2_dmm/militaryfactory_prop_woodplane001_dmm.gim", "scene/model/h55_hospital2_dmm/objdm65_scene_prop_01_dmm.gim", "scene/model/h55_hospital3/h55_hospital3_box01.gim", "scene/model/h55_hospital3/h55_hospital3_gallows.gim", "scene/model/h55_hospital3/h55_hospital3_gallows02.gim", "scene/model/h55_hospital3/h55_hospital3_gallows02_distantview.gim", "scene/model/h55_hospital3/h55_hospital3_gallows02_low.gim", "scene/model/h55_hospital3/h55_hospital3_gallows_distantview.gim", "scene/model/h55_hospital3/h55_hospital3_gallows_low.gim", "scene/model/h55_hospital3/h55_hospital3_sender01snow.gim", "scene/model/h55_hospital3/h55_hospital3_sender01snow_distantview.gim", "scene/model/h55_hospital3/h55_hospital3_sender01snow_low.gim", "scene/model/h55_hospital3/h55_hospital3_sender03snow.gim", "scene/model/h55_hospital3/h55_hospital3_sender03snow_low.gim", "scene/model/h55_manor_activity2/h55_manor_24summer/h55_manor_24summer_sandbeach01_nav/h55_manor_24summer_sandbeach02.nav", "scene/model/h55_manor_activity2/h55_manor_heijin_garden/nav/h55_manor_heijin_garden01_nav.nav", "scene/model/h55_manor_activity2/h55_manor_star2026j/manor_anni8_yyzx01_nav/manor_anni8_yyzx01_nav.nav", "scene/model/h55_manor_activity2/h55_manor_ysy/manor_ysy_chitang01_nav/manor_ysy_chitang01.nav", "scene/model/h55_manor_collection/h55_manor_col_renew/h55_manor_col_renew_wishingpool01.gim", "scene/model/h55_manor_collection/h55_manor_col_renew/h55_manor_col_renew_wishingpool01low.gim", "scene/model/h55_manor_collection/h55_manor_col_renew/h55_manor_col_renew_wishingpool02.gim", "scene/model/h55_manor_collection/h55_manor_col_renew/h55_manor_col_renew_wishingpool02low.gim", "scene/model/h55_manor_collection/h55_manor_col_renew3/manor_col_renew3_cabinet08a.gim", "scene/model/h55_manor_collection/h55_manor_col_renew3/manor_col_renew3_cabinet08b.gim", "scene/model/h55_manor_collection/h55_manor_col_renew3/manor_col_renew3_cabinet08c.gim", "scene/model/h55_manor_collection/h55_manor_col_renew3/manor_col_renew3_pendant01.gim", "scene/model/h55_manor_collection/h55_manor_col_renew3/manor_col_renew3_pendant01a.gim", "scene/model/h55_manor_collection/h55_manor_col_renew3/manor_col_renew3_pendant01alow.gim", "scene/model/h55_manor_collection/h55_manor_col_renew3/manor_col_renew3_pendant01low.gim", "scene/model/h55_manor_collection/h55_manor_col_renew4/h55_manor_col_renew4_sofa01.gim", "scene/model/h55_manor_collection/h55_manor_col_renew4/h55_manor_col_renew4_sofa01low.gim", "scene/model/h55_manor_collection/h55_manor_col_renew4/h55_manor_col_renew4_sofa02.gim", "scene/model/h55_manor_collection/h55_manor_col_renew4/h55_manor_col_renew4_sofa02low.gim", "scene/model/h55_manor_collection/h55_manor_col_renew4/h55_manor_col_renew4_sofa03.gim", "scene/model/h55_manor_collection/h55_manor_col_renew4/h55_manor_col_renew4_sofa03low.gim", "scene/model/h55_manor_collection/h55_manor_col_renew4/h55_manor_col_renew4_sofa04.gim", "scene/model/h55_manor_collection/h55_manor_col_renew4/h55_manor_col_renew4_sofa04low.gim", "scene/model/h55_manor_yl/manor_yl_nav/manor_yl_boat01.nav", "scene/model/h55_playground/h55_playground_cabinet01_lod_close.gim", "scene/model/h55_playground2/h55_playground2_box01lod.gim", "scene/model/h55_playground2/h55_playground2_box01low.gim", "scene/model/h55_playground2/h55_playground2_box01lowlod.gim", "scene/model/h55_playground2/h55_playground2_trampoline01lod.gim", "scene/model/h55_playground2/h55_playground2_trampoline01low.gim", "scene/model/h55_playground_ugc/h55_playground_cabinet01_ugc.gim", "scene/model/h55_random/random01/random01_in/col_rd01_loft_s_01_tswall02.gim", "scene/model/h55_sleepingtown_ugc/dm65_scene_cabinet_03_ugc.gim", "scene/model/militaryfactory/militaryfactory_prop_woodplane001.gim", "scene/model/militaryfactory/militaryfactory_prop_woodplane001_lod_destroy.gim", "scene/model/militaryfactory/militaryfactory_prop_woodplane001_lod_down.gim", "scene/model/militaryfactory/militaryfactory_prop_woodplane001_lod_up.gim", "scene/model/ordnance_factory1/dm65_scene_cabinet_01.gim", "scene/model/ordnance_factory1/dm65_scene_cabinet_01_lod_close.gim", "scene/model/ordnance_factory1/dm65_scene_gallows02_hx.gim", "scene/model/ordnance_factory1/dm65_scene_gallows02_hx_dis.gim", "scene/model/ordnance_factory1/dm65_scene_gallows02_hx_low.gim", "scene/model/ordnance_factory1/dm65_scene_gallows_hx.gim", "scene/model/ordnance_factory1/dm65_scene_gallows_hx_dis.gim", "scene/model/ordnance_factory1/dm65_scene_gallows_hx_low.gim", "scene/model/ordnance_factory1/dm65_scene_prop_01_lod.gim", "scene/model/ordnance_factory1/dm65_scene_prop_76.gim", "scene/model/ordnance_factory1/dm65_scene_sender_01.gim", "scene/model/ordnance_factory1/dm65_scene_sender_01_distantview.gim", "scene/model/ordnance_factory1/dm65_scene_sender_01_low.gim", "scene/model/ordnance_factory1/dm65_scene_sender_02.gim", "scene/model/ordnance_factory1/dm65_scene_sender_02_distantview.gim", "scene/model/ordnance_factory1/dm65_scene_sender_03.gim", "scene/model/ordnance_factory1/dm65_scene_sender_03_low.gim", "scene/model/ordnance_factory1/dm65_scene_telephone_01.gim", "scene/model/ordnance_factory1/dm65_scene_window_001.gim", "scene/model/ordnance_factory1/h55_annisender01.gim", "scene/model/ordnance_factory1/h55_annisender01_distantview.gim", "scene/model/ordnance_factory1/h55_annisender01_low.gim", "scene/model/ordnance_factory1/h55_annisender03.gim", "scene/model/ordnance_factory1/h55_annisender03_low.gim", "scene/model/ordnance_factory1/h55_gallows_gallows_anniversary2.gim", "scene/model/ordnance_factory1/h55_gallows_gallows_anniversary2_distantview.gim", "scene/model/ordnance_factory1/h55_gallows_gallows_anniversary2_low.gim", "scene/model/ordnance_factory1/h55_ordnance_factory1_toolbox01.gim", "scene/model/ordnance_factory1/h55_ordnance_factory1_toolbox01_lod.gim", "scene/model/ordnance_factory1/objdm65_scene_prop_01.gim", "scene/model/ordnance_factory2/h55_scene_christmasbox01.gim", "scene/model/ordnance_factory2/h55_scene_christmasbox01_lod.gim", "scene/model/ordnance_factory2/militaryfactory_prop_woodplane001_lod_destroysnow.gim", "scene/model/ordnance_factory2/militaryfactory_prop_woodplane001_lod_downsnow.gim", "scene/model/ordnance_factory2/militaryfactory_prop_woodplane001_lod_upsnow.gim", "scene/model/ordnance_factory2_ugc/dm65_scene_cabinet_01snow_ugc.gim", "scene/model/ordnance_factory_ugc/dm65_scene_cabinet_01_ugc.gim", "scene/model/sp_chair/h55_spdw_chair.gim", "scene/model/sp_chair/h55_spdw_chair_distantview.gim", "scene/model/sp_chair/h55_spdw_chair_low.gim", "scene/scene_battle//h55_activity_anni6_os/nav/h55_activity_anni6_os_camera.nav", "scene/scene_battle/activity_anni7_os/activity_anni7_os.scn", "scene/scene_battle/dm65_main/dm65_main.scn", "scene/scene_battle/dm65_main2/dm65_main2.scn", "scene/scene_battle/h55_5thmafia/h55_5thmafia.scn", "scene/scene_battle/h55_activity_anni6_os/nav/h55_activity_anni6_os_boat01.nav", "scene/scene_battle/h55_activity_autumn2025/nav/h55_activity_autumn2025_camera.nav", "scene/scene_battle/h55_activity_autumn2025/nav/h55_activity_autumn2025b.nav", "scene/scene_battle/h55_activity_autumn2025/nav/h55_activity_autumn2025c.nav", "scene/scene_battle/h55_activity_ib2025/nav/h55_activity_ib2025_camera.nav", "scene/scene_battle/h55_activity_moonriver_xmas2024/nav/h55_activity_moonriver_xmas2024_huabing.nav", "scene/scene_battle/h55_activity_moonriver_zsj2025/nav/h55_activity_moonriver_zsj2025_camera.nav", "scene/scene_battle/h55_activity_moonriver_zsj2025/nav/h55_activity_moonriver_zsj2025_mtl.nav", "scene/scene_battle/h55_activity_summer2025/nav/h55_activity_summer2025b.nav", "scene/scene_battle/h55_activity_summer2025/nav/h55_activity_summer2025c.nav", "scene/scene_battle/h55_activity_summer2025/nav/h55_activity_summer2025d.nav", "scene/scene_battle/h55_activity_summer2025/nav/h55_activity_summer2025e.nav", "scene/scene_battle/h55_backroom/h55_backroom.scn", "scene/scene_battle/h55_backroom_jyyj/h55_backroom_jyyj.scn", "scene/scene_battle/h55_blackjack/h55_blackjack.scn", "scene/scene_battle/h55_chest/h55_chest.scn", "scene/scene_battle/h55_chinatown_spring2024/nav/h55_chinatown_spring2024_dragonbus.nav", "scene/scene_battle/h55_chinatown_spring2026/nav/h55_chinatown_spring2026_paradefloat.nav", "scene/scene_battle/h55_coa4wardrobe/h55_coa4wardrobe.scn", "scene/scene_battle/h55_coa7_huangyi/h55_coa7_huangyi.scn", "scene/scene_battle/h55_coa9_joseph/h55_coa9_joseph.scn", "scene/scene_battle/h55_corridor/h55_corridor.scn", "scene/scene_battle/h55_corridor2flxx_d1/h55_corridor2flxx_d1.scn", "scene/scene_battle/h55_corridor2flxx_n1/h55_corridor2flxx_n1.scn", "scene/scene_battle/h55_corridor_sn/h55_corridor_sn.scn", "scene/scene_battle/h55_corridor_sn_l/h55_corridor_sn_l.scn", "scene/scene_battle/h55_deadforest_sp/h55_deadforest_sp.scn", "scene/scene_battle/h55_defendking/h55_defendking.scn", "scene/scene_battle/h55_defendking2/h55_defendking2.scn", "scene/scene_battle/h55_fantasy/h55_fantasy.scn", "scene/scene_battle/h55_guestroom/h55_guestroom.scn", "scene/scene_battle/h55_guestroom_cl/h55_guestroom_cl.scn", "scene/scene_battle/h55_guestroom_sl/h55_guestroom_sl.scn", "scene/scene_battle/h55_guestroom_sl_main/h55_guestroom_sl_main.scn", "scene/scene_battle/h55_guestroom_sm/h55_guestroom_sm.scn", "scene/scene_battle/h55_guestroom_sn/h55_guestroom_sn.scn", "scene/scene_battle/h55_guestroom_sn_l/h55_guestroom_sn_l.scn", "scene/scene_battle/h55_ladyd_studio/h55_ladyd_studio.scn", "scene/scene_battle/h55_logicpath/h55_logicpath.scn", "scene/scene_battle/h55_manor/h55_manor.scn", "scene/scene_battle/h55_manor_agency/h55_manor_agency.scn", "scene/scene_battle/h55_manor_conandoyle/h55_manor_conandoyle.scn", "scene/scene_battle/h55_manor_conandoyle_show/h55_manor_conandoyle_show.scn", "scene/scene_battle/h55_manor_dls/h55_manor_dls.scn", "scene/scene_battle/h55_manor_holloween/h55_manor_holloween.scn", "scene/scene_battle/h55_manor_holloween_show/h55_manor_holloween_show.scn", "scene/scene_battle/h55_manor_holloween_test/h55_manor_holloween_test.scn", "scene/scene_battle/h55_manor_joseph/h55_manor_joseph.scn", "scene/scene_battle/h55_manor_mist1/h55_manor_mist1.scn", "scene/scene_battle/h55_manor_mist1plus/h55_manor_mist1plus.scn", "scene/scene_battle/h55_manor_mist2/h55_manor_mist2.scn", "scene/scene_battle/h55_manor_mist3/h55_manor_mist3.scn", "scene/scene_battle/h55_manor_show_l/h55_manor_show_l.scn", "scene/scene_battle/h55_manor_show_s/h55_manor_show_s.scn", "scene/scene_battle/h55_manor_silent/h55_manor_silent.scn", "scene/scene_battle/h55_manor_silent01_test/h55_manor_silent01_test.scn", "scene/scene_battle/h55_manor_silent_test/h55_manor_silent_test.scn", "scene/scene_battle/h55_manor_yl01/h55_manor_yl01.scn", "scene/scene_battle/h55_manor_yl01_rain/h55_manor_yl01_rain.scn", "scene/scene_battle/h55_manor_yl01_show/h55_manor_yl01_show.scn", "scene/scene_battle/h55_manor_yl01_snow/h55_manor_yl01_snow.scn", "scene/scene_battle/h55_navtset/h55_navtset.scn", "scene/scene_battle/h55_playground/h55_playground.scn", "scene/scene_battle/h55_playground_n1/h55_playground_n1.scn", "scene/scene_battle/h55_racecourse/h55_racecourse.scn", "scene/scene_battle/h55_random/h55_random01/random01_boss_01/random01_boss_01.postprocess", "scene/scene_battle/h55_random/h55_random01/random01_boss_01/random01_boss_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_core_l_01/random01_core_l_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_enter_m_01/random01_enter_m_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_enter_m_02/random01_enter_m_02.scn", "scene/scene_battle/h55_random/h55_random01/random01_enter_m_03/random01_enter_m_03.scn", "scene/scene_battle/h55_random/h55_random01/random01_enter_m_04/random01_enter_m_04.scn", "scene/scene_battle/h55_random/h55_random01/random01_loft_s_01/random01_loft_s_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_loft_s_02/random01_loft_s_02.scn", "scene/scene_battle/h55_random/h55_random01/random01_loft_s_03/random01_loft_s_03.scn", "scene/scene_battle/h55_random/h55_random01/random01_main01/random01_main01.postprocess", "scene/scene_battle/h55_random/h55_random01/random01_main01/random01_main01.scn", "scene/scene_battle/h55_random/h55_random01/random01_outdoor_01/random01_outdoor_01.postprocess", "scene/scene_battle/h55_random/h55_random01/random01_outdoor_01/random01_outdoor_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_l_01/random01_pass_l_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_l_02/random01_pass_l_02.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_l_03/random01_pass_l_03.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_l_04/random01_pass_l_04.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_l_05/random01_pass_l_05.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_m_01/random01_pass_m_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_m_02/random01_pass_m_02.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_m_03/random01_pass_m_03.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_m_04/random01_pass_m_04.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_m_05/random01_pass_m_05.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_01/random01_pass_s_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_02/random01_pass_s_02.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_03/random01_pass_s_03.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_04/random01_pass_s_04.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_05/random01_pass_s_05.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_06/random01_pass_s_06.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_07/random01_pass_s_07.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_08/random01_pass_s_08.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_09/random01_pass_s_09.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_10/random01_pass_s_10.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_11/random01_pass_s_11.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_12/random01_pass_s_12.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_13/random01_pass_s_13.scn", "scene/scene_battle/h55_random/h55_random01/random01_pass_s_14/random01_pass_s_14.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_l_01/random01_room_l_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_l_02/random01_room_l_02.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_l_03/random01_room_l_03.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_l_04/random01_room_l_04.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_l_05/random01_room_l_05.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_l_07/random01_room_l_07.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_l_08/random01_room_l_08.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_l_09/random01_room_l_09.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_l_11/random01_room_l_11.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_m_01/random01_room_m_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_m_01a/random01_room_m_01a.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_m_02/random01_room_m_02.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_m_02a/random01_room_m_02a.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_m_03/random01_room_m_03.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_m_03a/random01_room_m_03a.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_01/random01_room_s_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_02/random01_room_s_02.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_02a/random01_room_s_02a.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_03/random01_room_s_03.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_03a/random01_room_s_03a.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_04/random01_room_s_04.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_05/random01_room_s_05.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_07/random01_room_s_07.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_08/random01_room_s_08.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_09/random01_room_s_09.scn", "scene/scene_battle/h55_random/h55_random01/random01_room_s_11/random01_room_s_11.scn", "scene/scene_battle/h55_random/h55_random01/random01_treasure_l_01/random01_treasure_l_01.scn", "scene/scene_battle/h55_random/h55_random01/random01_treasure_l_03/random01_treasure_l_03.scn", "scene/scene_battle/h55_random/h55_random_collision/random01/random01_collision.scn", "scene/scene_battle/h55_random/h55_random_collision/random01_Collision.postprocess", "scene/scene_battle/h55_random/h55_random_rookie/h55_random_rookie.scn", "scene/scene_battle/h55_random/h55_random_start/h55_random_start.postprocess", "scene/scene_battle/h55_random/h55_random_start/h55_random_start.scn", "scene/scene_battle/h55_settlement/h55_settlement.scn", "scene/scene_battle/h55_shop2/h55_shop2.scn", "scene/scene_battle/h55_studyroom/h55_studyroom.scn", "scene/scene_battle/h55_studyroom1/h55_studyroom1.scn", "scene/scene_battle/h55_studyroom2/h55_studyroom2.scn", "scene/scene_battle/h55_test_heijin/h55_test_heijin.scn", "scene/scene_battle/h55_ugc_wait/h55_ugc_wait.scn", "scene/scene_battle/h55_wait/h55_wait.scn", "scene/scene_battle/h55_wait_christmas/h55_wait_christmas.scn", "scene/scene_battle/h55_wait_copycat/h55_wait_copycat.scn", "scene/scene_battle/h55_wait_copycat2/h55_wait_copycat2.scn", "scene/scene_battle/h55_wait_copycat2_spring26/h55_wait_copycat2_spring26.scn", "scene/scene_battle/h55_wait_copycat_spring26/h55_wait_copycat_spring26.scn", "scene/scene_battle/h55_wait_halloween/h55_wait_halloween.scn", "scene/scene_battle/h55_wait_spring2024/h55_wait_spring2024.scn", "scene/scene_battle/h55_wait_ww/h55_wait_lowww.scn", "scene/scene_battle/h55_wait_ww/h55_wait_ww.scn", "scene/scene_battle/h55_waitdual/h55_waitdual.scn", "scene/scene_battle/h55_waitdual_spring2026/h55_waitdual_spring2026.scn", "scene/scene_battle/h55_wardrobe/h55_wardrobe.scn", "scene/scene_battle/h55_wardrobe_geis_zbs/h55_wardrobe_geis_zbs.scn", "scene/scene_battle/h55_wardrobe_heijin_girl01/h55_wardrobe_heijin_girl01.scn", "scene/scene_battle/h55_wardrobe_heijin_jisi/h55_wardrobe_heijin_jisi.scn", "scene/scene_battle/h55_wardrobe_heijin_jisi2/h55_wardrobe_heijin_jisi2.scn", "scene/scene_battle/h55_wardrobe_heijin_redqueen/h55_wardrobe_heijin_redqueen.scn", "scene/scene_battle/h55_wardrobe_heijin_redqueen01/h55_wardrobe_heijin_redqueen01.scn", "scene/scene_battle/manor_ballroomzr_sn1/manor_ballroomzr_sn1.scn", "scene/scene_battle/manor_guestroom1f01zr_rd/manor_guestroom1f01zr_rd.scn", "scene/scene_battle/manor_guestroom2f01zr_rd/manor_guestroom2f01zr_rd.scn", "scene/scene_battle/manor_guestroom2f01zr_rn/manor_guestroom2f01zr_rn.scn", "scene/scene_battle/manor_livingroom1_cl/manor_livingroom1_cl.scn", "scene/scene_battle/manor_livingroom1_sl/manor_livingroom1_sl.scn", "scene/scene_battle/manor_livingroom1_sn/manor_livingroom1_sn.scn", "scene/scene_battle/manor_livingroom1_sn_l/manor_livingroom1_sn_l.scn", "scene/scene_battle/manor_livingroom1xx_d1/manor_livingroom1xx_d1.scn", "scene/scene_battle/manor_livingroom1zr_rd/manor_livingroom1zr_rd.scn", "scene/scene_battle/manor_livingroom1zr_rn/manor_livingroom1zr_rn.scn", "scene/scene_battle/manor_livingroom1zr_sn/manor_livingroom1zr_sn.scn", "scene/scene_battle/manor_livingroom2_cl/manor_livingroom2_cl.scn", "scene/scene_battle/manor_livingroom2_sl/manor_livingroom2_sl.scn", "scene/scene_battle/manor_livingroom2_sn/manor_livingroom2_sn.scn", "scene/scene_battle/manor_livingroom2xx_d1/manor_livingroom2xx_d1.scn", "scene/scene_battle/manor_livingroom2xx_d2/manor_livingroom2xx_d2.scn", "scene/scene_battle/manor_livingroom2xx_n1/manor_livingroom2xx_n1.scn", "scene/scene_battle/manor_livingroom3_cl/manor_livingroom3_cl.scn", "scene/scene_battle/manor_livingroom3_sl/manor_livingroom3_sl.scn", "scene/scene_battle/manor_livingroom3_sn/manor_livingroom3_sn.scn", "scene/scene_battle/manor_livingroom3_sn_l/manor_livingroom3_sn_l.scn", "scene/scene_battle/manor_livingroom3xx_d1/manor_livingroom3xx_d1.scn", "scene/scene_battle/manor_livingroom3zr_rd/manor_livingroom3zr_rd.scn", "scene/scene_battle/manor_livingroom4xx_d1/manor_livingroom4xx_d1.scn", "scene/scene_battle/manor_suitezr_rn/manor_suitezr_rn.scn", "scene/scene_battle/manor_suitezr_sn1/manor_suitezr_sn1.scn", "scene/scene_battle/manor_suitezr_sn2/manor_suitezr_sn2.scn", "scene/scene_battle/story_livingroom_l/story_livingroom_l.scn", "scene/scene_battle/story_livingroom_l_nf/story_livingroom_l_nf.scn", "scene/scene_battle/story_livingroom_l_xx_d1/story_livingroom_l_xx_d1.scn", "scene/scene_battle/story_livingroom_n/story_livingroom_n.scn", "scene/scene_battle/story_livingroomzr_rd/story_livingroomzr_rd.scn"]''')
COMMON = ["scene/scene_battle/common_col_mesh/nav/grocer_door.col_mesh"]

_state = {"stage": "init", "t0": time.time(), "got": 0, "miss": 0, "bytes": 0, "tiles": 0, "rays": 0, "err": 0}


def _write_progress():
    try:
        _state["elapsed"] = round(time.time() - _state["t0"], 1)
        with open(OUT + "/progress.json", "w") as f:
            json.dump(_state, f)
    except Exception:
        pass


class Dumper:
    def __init__(self):
        os.makedirs(OUT, exist_ok=True)
        self.log = open(OUT + "/log.txt", "w", encoding="utf-8")
        self.manifest = open(OUT + "/manifest.jsonl", "w", encoding="utf-8")
        self.missf = open(OUT + "/miss.jsonl", "w", encoding="utf-8")
        self.got = {}       # 规范路径 -> (md5, size)
        self.data = {}      # 规范路径 -> bytes（只留 .nav/.scn 供后续解析）
        self.missed = set()
        try:
            import hashlib
            self.md5 = lambda b: hashlib.md5(b).hexdigest()
        except Exception:
            self.md5 = lambda b: ""
        self.zf = None
        try:
            import zipfile
            self.zf = zipfile.ZipFile(OUT + "/res.zip", "w", zipfile.ZIP_STORED, allowZip64=True)
        except Exception as e:
            self.L("zipfile 不可用，改为散文件: %r" % e)
        import C_file
        self.C = C_file
        self.n_calls = 0

    def L(self, s):
        self.log.write("[%.1f] %s\n" % (time.time() - _state["t0"], s))
        self.log.flush()

    @staticmethod
    def norm(p):
        return p.strip().replace("\\", "/")

    def _read(self, p):
        for v in (p, p.replace("\\", "/"), p.replace("/", "\\")):
            try:
                b = self.C.get_res_file(v, "")
            except Exception:
                b = None
            self.n_calls += 1
            if self.n_calls % 40 == 0:
                time.sleep(0.002)          # 让出 GIL，别卡游戏主线程
            if b:
                if isinstance(b, str):
                    b = b.encode("utf-8", "surrogateescape")
                return v, b
        return None, None

    def fetch(self, p, src, keep=False):
        n = self.norm(p)
        if not n or n in self.missed:
            return None
        if n in self.got:
            return self.data.get(n, b"")   # 已取过：返回非 None，调用方据此判断"存在"
        used, b = self._read(p)
        if b is None:
            self.missed.add(n)
            _state["miss"] += 1
            self.missf.write(json.dumps({"path": n, "src": src}, ensure_ascii=False) + "\n")
            return None
        h = self.md5(b)
        self.got[n] = (h, len(b))
        _state["got"] += 1
        _state["bytes"] += len(b)
        if self.zf is not None:
            self.zf.writestr(n, b)
        else:
            fp = os.path.join(OUT, "files", n)
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "wb") as f:
                f.write(b)
        self.manifest.write(json.dumps({"path": n, "used": used, "size": len(b), "md5": h, "src": src}, ensure_ascii=False) + "\n")
        if keep or n.endswith((".nav", ".scn")):
            self.data[n] = b
        if _state["got"] % 50 == 0:
            self.manifest.flush(); _write_progress()
        return b


def _paths_in(v):
    out = []
    if isinstance(v, str):
        for part in v.split(","):
            s = part.strip()
            m = PATH_RE.match(s)
            if m and ("/" in s or "\\" in s):
                out.append((s, m.group(1).lower()))
    elif isinstance(v, (list, tuple, set, frozenset)):
        for x in v:
            out += _paths_in(x)
    elif isinstance(v, dict):
        for x in v.values():
            out += _paths_in(x)
    return out


def phase_a(D):
    _state["stage"] = "A_scene_config"; _write_progress()
    targets = []
    sc = GK.DM.scene_config
    navs = set()
    for sid in sorted(sc):
        cfg = sc[sid]
        for k, v in cfg.items():
            for p, ext in _paths_in(v):
                if ext in KEEP_EXT or (ext == "gim" and ("col" in k.lower() or "_col" in p.lower()
                                                         or k.lower().endswith("model_path"))):
                    targets.append((p, "sc:%s:%s" % (sid, k)))
                    if ext == "nav":
                        navs.add(p)
                    if ext == "scn_col":
                        targets.append((p[:-8] + ".col_mesh", "derive:col_mesh"))
                        targets.append((p[:-8] + "_dev.col_mesh", "derive:dev_col_mesh"))
        try:
            from common_tools import utils
            cp = utils.get_scene_col_path(sid)
            if cp:
                targets.append((cp, "utils.get_scene_col_path:%s" % sid))
                targets.append((cp.replace(".scn_col", ".col_mesh"), "derive:col_mesh"))
                targets.append((cp.replace(".scn_col", "_dev.col_mesh"), "derive:dev_col_mesh"))
        except Exception as e:
            pass
    for p in EXPLICIT:
        targets.append((p, "explicit"))
        if p.lower().endswith(".nav"):
            navs.add(p)
    for p in COMMON:
        targets.append((p, "common"))
    # 导航派生：ai_ / moveable_ 前缀（NavManager.load_scene_nav_mesh 里的命名约定）
    for nv in list(navs):
        n = D.norm(nv)
        d, base = n.rsplit("/", 1) if "/" in n else ("", n)
        for pre in ("ai_", "moveable_"):
            targets.append(((d + "/" if d else "") + pre + base, "derive:nav_" + pre))
    D.L("阶段A 目标 %d 条" % len(targets))
    for p, src in targets:
        D.fetch(p, src)
    D.L("阶段A 完成 got=%d miss=%d" % (_state["got"], _state["miss"]))


def phase_b(D):
    _state["stage"] = "B_nav_tiles"; _write_progress()
    report = {}
    for n, b in list(D.data.items()):
        if not n.endswith(".nav") or b[:4] != b"TESM":
            continue
        names = []
        # 块名是 [u32 长度][字符串]：从每个 ".tile" 结尾往回找满足长度前缀的起点
        for m in re.finditer(rb"\.tile", b):
            e = m.end()
            for L in range(6, 240):
                s0 = e - L
                if s0 < 4:
                    break
                if int.from_bytes(b[s0 - 4:s0], "little") == L:
                    raw = b[s0:e]
                    if all(32 < c < 127 for c in raw):
                        nm = raw.decode("latin1")
                        if nm not in names:
                            names.append(nm)
                        break
        d, base = n.rsplit("/", 1) if "/" in n else ("", n)
        stem = base[:-4]
        cands = [d, d + "/" + stem, d + "/" + stem + "_tile", d + "/" + stem + "_tiles", d + "/tile", d + "/tiles",
                 d + "/" + stem + "/tile", ""]
        chosen = None
        if names:
            for c in cands:
                if D.fetch((c + "/" if c else "") + names[0], "tile_probe:" + n) is not None:
                    chosen = c
                    break
        ok = 0
        if chosen is not None:
            for nm in names:
                if D.fetch((chosen + "/" if chosen else "") + nm, "tile:" + n) is not None:
                    ok += 1
        report[n] = {"tiles_listed": len(names), "dir": chosen, "ok": ok, "first": names[:3]}
        _state["tiles"] += ok
        D.L("nav %s: 列出 %d 块, 目录=%r, 取到 %d" % (n, len(names), chosen, ok))
    with open(OUT + "/nav_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)


def phase_c(D):
    _state["stage"] = "C_scn_refs"; _write_progress()
    seen = set()
    for rnd in range(3):
        new = 0
        for n, b in list(D.data.items()):
            if not n.endswith(".scn") or n in seen:
                continue
            seen.add(n)
            t = b.decode("utf-8", "replace")
            for m in re.finditer(r'"([^"<>\s]+\.([A-Za-z0-9_]{1,12}))"', t):
                p, ext = m.group(1), m.group(2).lower()
                if ext in KEEP_EXT and D.norm(p) not in D.got:
                    if D.fetch(p, "scn_ref:" + n) is not None:
                        new += 1
        D.L("阶段C 第%d轮 新增 %d" % (rnd, new))
        if not new:
            break


def _ser(r, depth=0):
    if depth > 3:
        return repr(r)[:80]
    if r is None or isinstance(r, (bool, int, float, str)):
        return r
    if isinstance(r, (list, tuple)):
        return [_ser(x, depth + 1) for x in r]
    try:
        return {"v3": [float(r.x), float(r.y), float(r.z)]}
    except Exception:
        pass
    out = {"type": type(r).__name__}
    for a in ("hit", "is_hit", "pos", "position", "hit_pos", "point", "normal", "hit_normal", "cid", "col_id",
              "dist", "distance", "fraction", "t", "unit_type", "group", "layer", "face"):
        try:
            v = getattr(r, a)
            if callable(v):
                continue
            out[a] = _ser(v, depth + 1)
        except Exception:
            pass
    if len(out) == 1:
        out["repr"] = repr(r)[:160]
    return out


def phase_d(D):
    _state["stage"] = "D_ray_truth"; _write_progress()
    w = S(lambda: GK.g_world_mgr.cur_world)
    cm = S(lambda: w.collision_mgr)
    sc = S(lambda: cm._scene_col)
    meta = {"world": type(w).__name__ if w is not None else None, "has_cm": cm is not None, "has_scene_col": sc is not None}
    if cm is None or sc is None:
        meta["skipped"] = "不在对局里(没有场景碰撞)"
        with open(OUT + "/raytruth_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=1)
        D.L("阶段D 跳过: %s" % meta["skipped"])
        return
    import math3d, random
    V = math3d.vector
    sid = S(lambda: w.scene_id)
    cfg = S(lambda: GK.DM.scene_config[sid], {}) or {}
    me = S(lambda: GK.g_unit)
    pp = S(lambda: me.get_position3()) or S(lambda: me.position)
    px, py, pz = (float(pp.x), float(pp.y), float(pp.z)) if pp is not None else (0.0, 0.0, 0.0)
    cen = cfg.get("scene_center") or (px, py, pz)
    meta.update({"scene_id": sid, "scene_center": list(cen), "player": [px, py, pz],
                 "server_col": cfg.get("server_col"), "scene_path": cfg.get("scene_path")})
    funcs = {}
    for name in ("hit_by_ray_new_with_scn_col", "hit_by_ray_new"):
        f = getattr(cm, name, None)
        if f is None:
            continue
        code = getattr(getattr(f, "__func__", f), "__code__", None)
        funcs[name] = f
        meta["sig_" + name] = {"args": list(code.co_varnames[:code.co_argcount]) if code else None,
                               "defaults": repr(getattr(getattr(f, "__func__", f), "__defaults__", None))}
    meta["flags"] = {k: S(lambda k=k: getattr(cm, k)) for k in (
        "use_smaller_capsule_size", "static_test_add_extra_size", "capsule_triangle_two_edges",
        "mesh_penetration_recalc_pen", "capsule_sweep_mesh_same_radius", "jump_height", "use_bullet")}
    meta["flags"] = {k: (v if isinstance(v, (int, float, bool, str, type(None))) else repr(v)) for k, v in meta["flags"].items()}
    with open(OUT + "/raytruth_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1, default=repr)
    if not funcs:
        D.L("阶段D 跳过: 碰撞管理器上没有射线函数")
        return
    out = open(OUT + "/raytruth.jsonl", "w", encoding="utf-8")

    def call(f, a, b):
        for extra in ((), (None,), (None, False)):
            try:
                return True, f(a, b, *extra)
            except TypeError:
                continue
            except Exception as e:
                return False, repr(e)[:120]
        return False, "TypeError"

    rng = random.Random(20261024)
    cx, cz = float(cen[0]), float(cen[2])
    R = 1300.0
    t_end = time.time() + RAY_BUDGET_SEC
    k = 0
    # 1) 竖直射线网格：得到地面/楼层高度场
    G = 96
    for i in range(G):
        for j in range(G):
            if time.time() > t_end:
                break
            x = cx - R + 2 * R * (i + 0.5) / G
            z = cz - R + 2 * R * (j + 0.5) / G
            a, b = V(x, py + 400.0, z), V(x, py - 300.0, z)
            for name, f in funcs.items():
                ok, r = call(f, a, b)
                out.write(json.dumps({"k": "v", "f": name, "a": [x, py + 400.0, z], "b": [x, py - 300.0, z],
                                      "ok": ok, "r": _ser(r)}, default=repr) + "\n")
            k += 1
            if k % 64 == 0:
                _state["rays"] = k; _write_progress(); time.sleep(0.003)
    # 2) 随机水平/斜射线：墙体与障碍
    while time.time() < t_end:
        x, z = rng.uniform(cx - R, cx + R), rng.uniform(cz - R, cz + R)
        h = py + rng.choice((3.0, 10.0, 25.0, 60.0))
        ang = rng.uniform(0, 6.2831853)
        L = rng.uniform(30.0, 400.0)
        import math
        x2, z2 = x + L * math.cos(ang), z + L * math.sin(ang)
        h2 = h + rng.uniform(-20.0, 20.0)
        a, b = V(x, h, z), V(x2, h2, z2)
        for name, f in funcs.items():
            ok, r = call(f, a, b)
            out.write(json.dumps({"k": "h", "f": name, "a": [x, h, z], "b": [x2, h2, z2], "ok": ok, "r": _ser(r)},
                                 default=repr) + "\n")
        k += 1
        if k % 64 == 0:
            _state["rays"] = k; _write_progress(); time.sleep(0.003)
    out.close()
    _state["rays"] = k
    D.L("阶段D 完成 射线 %d 条" % k)


def phase_e(D):
    _state["stage"] = "E_api_lists"; _write_progress()
    rep = {}
    rep["C_file"] = S(lambda: [a for a in dir(D.C) if not a.startswith("__")], [])
    w = S(lambda: GK.g_world_mgr.cur_world)
    cm = S(lambda: w.collision_mgr)
    rep["collision_mgr"] = S(lambda: [a for a in dir(cm) if not a.startswith("__")], [])
    sc = S(lambda: cm._scene_col)
    rep["scene_col_type"] = type(sc).__name__ if sc is not None else None
    rep["scene_col"] = S(lambda: [a for a in dir(sc) if not a.startswith("__")], [])
    try:
        import collision
        rep["collision_module"] = [a for a in dir(collision) if not a.startswith("__")]
    except Exception as e:
        rep["collision_module"] = repr(e)
    nm = S(lambda: w.nav_mgr)
    rep["nav_mgr"] = S(lambda: [a for a in dir(nm) if not a.startswith("__")], [])
    rep["world"] = type(w).__name__ if w is not None else None
    rep["scene_id"] = S(lambda: w.scene_id)
    with open(OUT + "/api_report.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=repr)


def _run():
    D = None
    try:
        D = Dumper()
        D.L("开始；get_res_file 样本类型=%s" % type(S(lambda: D.C.get_res_file(COMMON[0], ""))).__name__)
        for ph in (phase_a, phase_b, phase_c):
            try:
                ph(D)
            except Exception:
                _state["err"] += 1
                D.L("阶段异常 %s:\n%s" % (ph.__name__, traceback.format_exc()))
        if D.zf is not None:
            D.zf.close()
        D.manifest.close(); D.missf.close()
        _state["stage"] = "files_done"; _write_progress()
        D.L("文件阶段结束 got=%d miss=%d bytes=%d tiles=%d" % (_state["got"], _state["miss"], _state["bytes"], _state["tiles"]))
        for ph in (phase_e, phase_d):
            try:
                ph(D)
            except Exception:
                _state["err"] += 1
                D.L("阶段异常 %s:\n%s" % (ph.__name__, traceback.format_exc()))
        _state["stage"] = "done"; _write_progress()
        D.L("全部完成")
    except Exception:
        _state["stage"] = "fatal"; _state["fatal"] = traceback.format_exc()[-1500:]
        _write_progress()


if globals().get("RESDUMP_SYNC"):
    _run()
else:
    threading.Thread(target=_run, name="resdump", daemon=True).start()
    P("resdump 已在后台启动 -> %s (看 progress.json)" % OUT)
