"""第五人格录像解析：读出每局所有玩家的天赋(genius)。

录像目录(设备上)：
  /storage/emulated/0/Android/data/com.netease.dwrg/files/netease/
      dwrg.common/Documents/video/<账号uid>/<对局guuid>/

每个对局文件夹里：
  battle_frames_snapshot_N.txt   分段的帧快照。**天赋只在 _0 里**(开局同步帧)
  game_info.txt                  结算信息，含 genius_data
  total_info.txt                 时间轴事件(破译完成/开门)
上一级还有 vmap.txt，是录像索引。

文件格式：**Python pickle 协议 2**，不是自定义二进制。游戏内嵌 CPython，
直接 pickle.dump 出来的。所以不用写解析器，`pickle.load` 即可 —— 但
反序列化会执行任意代码，本文件用受限 Unpickler 只放行纯数据 + 几个已知安全的类。

天赋在：data[0].snap_shot.event_data.entities[uid].genius_id_lvs = [[天赋id, 等级], ...]
game_info.txt 的 genius_data 也有一份(按分支分页)，两者互为校验。

用法：
  replay_genius.py pull [目标目录]        从设备拉全部录像的 snapshot_0 + game_info
  replay_genius.py <对局目录或录像根目录>   解析并打印
"""
import io
import os
import pickle
import subprocess
import sys

ADB = r"C:\Users\31297\AppData\Local\Android\Sdk\platform-tools\adb.exe"
设备录像根 = ("/storage/emulated/0/Android/data/com.netease.dwrg/files/"
            "netease/dwrg.common/Documents/video")


# ---------------------------------------------------------------- 安全反序列化

class 拒绝导入(pickle.UnpicklingError):
    pass


class ObjectId:
    """bson.objectid.ObjectId 的本地桩：只当 12 字节 id 容器，不引入 bson。"""

    def __init__(self, oid=None):
        self.oid = oid

    def __setstate__(self, state):
        self.oid = state.get("_ObjectId__id", state) if isinstance(state, dict) else state

    def __repr__(self):
        b = self.oid
        if isinstance(b, str):
            b = b.encode("latin1")
        return f"ObjectId({b.hex() if isinstance(b, bytes) else b!r})"


def 受限encode(对象, 编码="latin1", 错误="strict"):
    """py3 pickle 里 bytes 靠 _codecs.encode(str,'latin1') 还原。只放行这一种用法。"""
    if not isinstance(对象, str) or 编码 not in ("latin1", "latin-1"):
        raise 拒绝导入(f"不接受的 _codecs.encode 用法: {type(对象).__name__}, {编码!r}")
    return 对象.encode(编码, 错误)


# 只有这张表里的才允许还原，其余一律拒绝。游戏写 pickle 用的是 py2 风格模块名。
白名单 = {
    ("bson.objectid", "ObjectId"): ObjectId,
    ("_codecs", "encode"): 受限encode,
    ("__builtin__", "set"): set,
    ("__builtin__", "frozenset"): frozenset,
    ("builtins", "set"): set,
    ("builtins", "frozenset"): frozenset,
}


class 安全Unpickler(pickle.Unpickler):
    def find_class(self, module, name):
        try:
            return 白名单[(module, name)]
        except KeyError:
            raise 拒绝导入(f"未知类引用 {module}.{name}，已拒绝") from None


def 读(路径):
    with open(路径, "rb") as f:
        return 安全Unpickler(io.BytesIO(f.read()), encoding="latin1").load()


# ---------------------------------------------------------------- 天赋名表

# id 分段：4 个分支各 8 个槽位 —— 1~8 / 9~16 / 17~24 / 25~32，33+ 是散号。
# 依据：game_info.txt 的 show_genius_dict 就是按 '1'~'4' 分页存的，页内 id 严格落在对应段。
# 监管和求生者**共用同一套 id 号段**，同一个 id 在两边是不同天赋，必须靠 unit_type 区分。
#
# 每个分支的终端(8/16/24/32)就是四个大天赋。实测 14 名求生者每人恰好占 2 个
# (一个来自 {8,16}、一个来自 {24,32})，与"点数只够走通两条分支"吻合。
#
# 只填了实战关心的那几个，其余小天赋对判断没用，留空显示成 #id。
天赋表 = {
    2: {                    # 求生者
        8:  "飞轮效应",
        16: "回光返照",
        24: "化险为夷",
        32: "膝跳反射",
        26: "绝处逢生",     # 不是分支终端，落在第 4 分支中段
    },
    1: {                    # 监管者
        8:  "紧闭空间",     # ⚠ 排除法得到，五局样本里一次都没出现过，未直接验证
        16: "底牌",
        24: "挽留",
        32: "张狂",
    },
}

# 每个分支的终端，也就是四个大天赋
终端 = (8, 16, 24, 32)

# 监管者的辅助特质，entity 的 support_skill_id 字段(是个 list，实测都只有一个元素)。
# 求生者该字段恒为 None。跟天赋是两套独立编号，别混。
# 全表由用户给出；其中 4/7/8 另有五局录像佐证，5 另有 Python 层活体读取佐证。
辅助特质 = {
    1: "聆听",
    2: "失常",
    3: "兴奋",
    4: "巡视者",
    5: "传送",
    6: "窥视者",
    7: "闪现",
    8: "移形",
}

阵营名 = {1: "监管", 2: "求生"}


def 天赋名(unit_type, gid):
    return 天赋表.get(unit_type, {}).get(gid) or f"#{gid}"


# ---------------------------------------------------------------- 解析

def 解析对局(目录):
    """返回 (对局信息 dict, 玩家列表)。玩家按 阵营 -> uid 排序。"""
    快照 = os.path.join(目录, "battle_frames_snapshot_0.txt")
    ed = 读(快照)["data"][0]["snap_shot"]["event_data"]

    信息 = {
        "guuid": ed.get("guuid"),
        "场景": ed.get("scene_id"),
        "人数": ed.get("player_num"),
        "密码机数": ed.get("generator_num"),
        "本机uid": ed.get("self_uid"),
    }

    # 认出本机玩家：game_info 顶层的 unique_id 就是本机账号 uid，对上 entity 的 unique_id。
    # 注意别拿 genius_data 的键来认 —— 真人对局里它装的是全场五个人，不止自己。
    我的账号 = None
    gi路径 = os.path.join(目录, "game_info.txt")
    if os.path.exists(gi路径):
        try:
            我的账号 = str(读(gi路径).get("unique_id"))
        except Exception:
            pass

    玩家 = []
    for uid, e in ed["entities"].items():
        if not (isinstance(e, dict) and "genius_id_lvs" in e):
            continue    # 只有玩家实体带天赋，密码机/椅子等没有
        ut = e["unit_type"]
        天赋 = sorted(e["genius_id_lvs"])
        玩家.append({
            "uid": uid,
            "阵营": ut,
            "角色id": e.get("pid"),
            "名字": e.get("player_name"),
            "机器人": bool(e.get("is_bot")),
            "皮肤id": e.get("cloth_id"),
            "本人": 我的账号 is not None and str(e.get("unique_id")) == 我的账号,
            "天赋": 天赋,
            "大天赋": [i for i, _ in 天赋 if i in 终端],
            # 有名字的非终端天赋(目前只有绝处逢生)，单独列出来
            "其他已知": [i for i, _ in 天赋
                     if i not in 终端 and i in 天赋表.get(ut, {})],
            "辅助特质": e.get("support_skill_id") or [],
        })
    玩家.sort(key=lambda p: (p["阵营"], p["uid"]))
    return 信息, 玩家


def 打印对局(目录):
    信息, 玩家 = 解析对局(目录)
    print(f'--- {os.path.basename(目录)}  场景{信息["场景"]}  '
          f'{信息["人数"]}人  密码机{信息["密码机数"]}台 ---')
    for p in 玩家:
        标 = "★" if p["本人"] else ("b" if p["机器人"] else " ")
        名 = [天赋名(p["阵营"], i) for i in p["大天赋"] + p["其他已知"]]
        名 += [辅助特质.get(i, f"辅助#{i}") for i in p["辅助特质"]]
        print(f'  {标} [{阵营名[p["阵营"]]}] {str(p["名字"])[:14]:<16} '
              f'角色{p["角色id"]:<4} {" ".join(名) or "(无)"}')
        全 = " ".join(f"{i}·{lv}" for i, lv in p["天赋"])
        print(f'       全部: {全}')
    print()


# ---------------------------------------------------------------- 从设备拉取

def adb(*参数):
    return subprocess.run([ADB, *参数], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def 拉取(目标):
    账号 = [x for x in adb("shell", f"su -c 'ls {设备录像根}'").split() if x.isdigit()]
    if not 账号:
        print("没找到录像目录，游戏至少要存过一局录像")
        return
    根 = f"{设备录像根}/{账号[0]}"
    对局 = [x for x in adb("shell", f"su -c 'ls {根}'").split() if len(x) == 24]
    print(f"账号 {账号[0]}，{len(对局)} 局")
    os.makedirs(目标, exist_ok=True)
    for m in 对局:
        # 录像属 u0_a310 且目录是 drwxrws---，shell 用户读不到，得先 su 拷到可读处
        中转 = f"/data/local/tmp/rp_pull/{m}"
        adb("shell", f"su -c 'mkdir -p {中转} && "
                     f"cp {根}/{m}/battle_frames_snapshot_0.txt {根}/{m}/game_info.txt {中转}/ && "
                     f"chmod 777 /data/local/tmp/rp_pull {中转} && chmod 666 {中转}/*'")
        adb("pull", 中转, 目标)
        print(f"  {m}")
    print(f"拉到 {目标}")


# ---------------------------------------------------------------- 入口

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "pull":
        拉取(sys.argv[2] if len(sys.argv) > 2 else "replays")
        sys.exit(0)

    路径 = sys.argv[1]
    if os.path.exists(os.path.join(路径, "battle_frames_snapshot_0.txt")):
        打印对局(路径)
    else:   # 当成录像根目录，遍历下面每一局
        for m in sorted(os.listdir(路径)):
            d = os.path.join(路径, m)
            if os.path.isdir(d) and os.path.exists(
                    os.path.join(d, "battle_frames_snapshot_0.txt")):
                打印对局(d)

# ---------------------------------------------------------------- 映射是怎么定的
#
# id→天赋名 推不出来，必须外部对照。已用的两种办法，以后补新天赋照做：
#
# 1. 用户直接报自己的配装。game_info.txt 的 genius_data 就是本机玩家的天赋，
#    对着 id 报名字即可。四个终端天赋是这么定的。
#
# 2. 「谁有谁没有」差分。绝处逢生(26) 就是这么找出来的：
#    已知 A 局四个求生者全有、B 局只有其中两人有，求
#        (A 局全员交集) ∩ (B 局有的人交集) - (B 局没有的人并集)
#    五局样本下唯一候选 26，无歧义。两局的约束方向相反是关键，
#    只给一局的话候选会剩一大把。
#
# 监管的 8(紧闭空间) 是排除法得到的，五局样本里一次都没出现过，**没有直接验证**。
# 哪天遇到一个带紧闭空间的监管，确认一下 id 确实是 8。
