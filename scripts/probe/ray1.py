u=(units_of(2) or [None])[0]
mo=S(lambda: u.model)
# hit_by_ray 文档/签名
hbr=S(lambda: mo.hit_by_ray)
P("hit_by_ray doc=%s" % R(S(lambda: hbr.__doc__),200))
# 试几种签名（起点=相机，方向=指向目标），先探参数个数
import math
cam=S(lambda: me.position)
tgt=S(lambda: u.position)
tries=[
 ("()", lambda: mo.hit_by_ray()),
 ("(cam,tgt)", lambda: mo.hit_by_ray(cam,tgt)),
 ("(cam,tgt,0)", lambda: mo.hit_by_ray(cam,tgt,0)),
 ("(3f start,3f dir)", lambda: mo.hit_by_ray((cam[0],cam[1]+1.5,cam[2]),(tgt[0]-cam[0],tgt[1]-cam[1],tgt[2]-cam[2]))),
]
for tag,fn in tries:
    try: P("hbr%s = %s" % (tag, R(fn(),120)))
    except Exception as e: P("hbr%s ERR %s" % (tag, R(e,100)))
# 相机对象：找真正的相机位置/朝向来源
gcc=S(lambda: GK.g_cam_ctrl) or S(lambda: getattr(GK,'g_camera',None))
P("g_cam_ctrl=%s attrs=%s" % (cname(gcc), R([a for a in (S(lambda: dir(gcc),[]) or []) if any(k in a.lower() for k in ('pos','dir','forward','eye','look','target','ray','screen','project','world_to','to_screen'))],400)))
