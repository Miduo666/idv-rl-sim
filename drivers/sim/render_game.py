# -*- coding: utf-8 -*-
"""把 record_game.py 录的一局渲染成 MP4：左边监管跟随视角（俯视），右边全图小地图 + 状态栏。
用法: python render_game.py <录像.jsonl> <输出.mp4> [fps=30] [视野半径=360] [并行进程数=8，环境变量 RENDER_JOBS 亦可]
底图：AI 导航多边形 = 地面；.scn_col 静态碰撞里竖直的三角形（|法线y|<0.5、高度在地面附近）投影成墙线。
模拟器没有引擎的模型/贴图，这里是逻辑状态的俯视示意图。
并行：主进程建一次底图（存临时 .npy）、扫一遍录像算每帧"已挂椅秒数"（唯一的跨帧状态）；帧按小块分给工作进程画，
画好的帧按顺序交回主进程直接编码（先写分段再拼接要多一遍解码+重编码，实测每帧 17ms，比画图还慢）。"""
import sys, os, json, zipfile, tempfile, shutil, time
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RES_ZIP = os.environ.get("IDV_RES_ZIP", os.path.normpath(os.path.join(HERE, "..", "..", "res_pull", "resdump_1025_015456", "res_recovered.zip")))
NAV = "scene/scene_battle/ordnance_factory1/nav/ordnance_factory_test1.nav"
COL = "scene/scene_battle/ordnance_factory1/nav/ordnance_factory1.scn_col"
W, H, MAIN = 1600, 900, 900
MM = 640
SC = 2.0             # 底图：1 世界单位 = SC 像素
CHUNK = 8            # 工作进程每次交回的帧数
FONT = r"C:\Windows\Fonts\msyh.ttc"
# 角色中文名：配表只有 TID（文本表模拟器没载入），按 DM.player[pid].pinyin 认
PID_CN = {1: "厂长", 14: "医生", 15: "律师", 16: "慈善家", 17: "园丁", 30: "杰克", 32: "空军"}
CIV_COLORS = [(80, 200, 255), (120, 255, 120), (255, 220, 90), (230, 140, 255)]   # BGR
TAG_CN = {"HANG": "上椅", "HANGING": "上椅", "FALL": "倒地", "CARRY": "被扛", "CATCHED": "被扛", "STRUGGLE_DROP": "挣脱",
          "HURT": "受伤", "FIX": "修机", "OPEN_DOOR": "开门"}

G = {}               # 工作进程的渲染上下文（init_worker 填）


def build_base():
    """底图（地面多边形 + 墙线）与世界→底图的平移量。"""
    import navmesh, scncol
    z = zipfile.ZipFile(RES_ZIP)
    nav = navmesh.load_nav(z, NAV)
    polys = []
    for t in nav["tiles"]:
        for p in t["polys"]:
            if p["type"] == 0 and (p["flags"] & 65531) and len(p["verts"]) >= 3:
                polys.append([t["verts"][i] for i in p["verts"]])
    xs = [v[0] for pl in polys for v in pl]; zs = [v[2] for pl in polys for v in pl]
    X0, X1, Z0, Z1 = min(xs) - 60, max(xs) + 60, min(zs) - 60, max(zs) + 60
    BW, BH = int((X1 - X0) * SC), int((Z1 - Z0) * SC)

    def to_base(x, zz):
        return (x - X0) * SC, (zz - Z0) * SC
    base = np.full((BH, BW, 3), (28, 26, 24), np.uint8)
    for pl in polys:
        col = (52, 50, 46) if min(v[1] for v in pl) < -40 else (74, 72, 66)     # 地下室层画深一点
        cv2.fillPoly(base, [np.array([to_base(v[0], v[2]) for v in pl], np.int32)], col, cv2.LINE_AA)
    segs = []
    for o in scncol.parse(z.read(COL)):
        wv = scncol.world_verts(o, "row")
        for k in range(0, len(o.idx), 3):
            a, b, c = (np.array(wv[o.idx[k + j]]) for j in range(3))
            n = np.cross(b - a, c - a)
            ln = np.linalg.norm(n)
            if ln < 1e-6 or abs(n[1]) / ln > 0.5:
                continue
            ys = (a[1], b[1], c[1])
            if max(ys) < 2 or min(ys) > 22:      # 只要角色高度附近的墙
                continue
            if not (X0 <= a[0] <= X1 and Z0 <= a[2] <= Z1):
                continue
            segs.append(np.array([to_base(p[0], p[2]) for p in (a, b, c)], np.int32))
    cv2.polylines(base, segs, True, (150, 160, 170), 1, cv2.LINE_AA)
    print("底图 %dx%d，地面多边形 %d，墙三角 %d" % (BW, BH, len(polys), len(segs)), flush=True)
    return base, (X0, X1, Z0, Z1)


def scan(src):
    """一遍扫录像：每帧行的字节偏移、每帧的 {uid: 本次上椅开始秒}（椅子 cur_process 恒 0，按持续时间显示）。"""
    offsets, hang_per_frame, since = [], [], {}
    with open(src, "rb") as f:
        hdr = json.loads(f.readline())
        while True:
            off = f.tell()
            line = f.readline()
            if not line.strip():
                break
            fr = json.loads(line)
            for c in fr["chars"]:
                if c["hook"] and ("HANG" in c["tags"] or "HANGING" in c["tags"]):
                    since.setdefault(c["uid"], fr["t"])
                else:
                    since.pop(c["uid"], None)
            alive = {c["uid"] for c in fr["chars"]}
            for u in list(since):
                if u not in alive:
                    since.pop(u)
            offsets.append(off)
            hang_per_frame.append(dict(since))
    return hdr, offsets, hang_per_frame


def init_worker(src, base_path, bounds, view_r, hdr):
    base = np.load(base_path)
    X0, X1, Z0, Z1 = bounds
    BH, BW = base.shape[:2]
    roles = {int(k): v for k, v in hdr["roles"].items()}
    for v in roles.values():
        v["name"] = PID_CN.get(v["pid"], str(v["pid"]))
    civ_order = [uid for uid in sorted(roles) if roles[uid]["role"] == "civilian"]
    color = {uid: CIV_COLORS[i % 4] for i, uid in enumerate(civ_order)}
    but = [uid for uid in roles if roles[uid]["role"] == "butcher"][0]
    color[but] = (60, 60, 255)
    mm_scale = MM / max(BW, BH)
    G.update(src=src, base=base, X0=X0, X1=X1, Z0=Z0, Z1=Z1, BW=BW, BH=BH, view_r=view_r, hdr=hdr, roles=roles,
             civ_order=civ_order, color=color, but=but, mm_scale=mm_scale,
             mm_base=cv2.resize(base, (int(BW * mm_scale), int(BH * mm_scale)), interpolation=cv2.INTER_AREA),
             static={k: {d["uid"]: d for d in hdr.get(k, [])} for k in ("gens", "panels", "windows", "hooks", "doors", "switches")},
             fonts={s: ImageFont.truetype(FONT, s) for s in (16, 22, 30)})


def to_base(x, zz):
    return (x - G["X0"]) * SC, (zz - G["Z0"]) * SC


def draw_static_dyn(img, fr, tf, scale, thick):
    """在 img 上画物件；tf(x,z)->像素。"""
    st = G["static"]

    def P(p):
        x, y = tf(p[0], p[2]); return int(x), int(y)
    for w in st["windows"].values():
        c = np.array(w["pos"]); d = np.array([w["dir"][1], 0, -w["dir"][0]]) * 7
        cv2.line(img, P(c - d), P(c + d), (230, 170, 60), max(2, thick), cv2.LINE_AA)
    pst = {u: (s, dst) for u, s, dst in fr["panels"]}
    for uid, p in st["panels"].items():
        s, dst = pst.get(uid, (1, False))
        c = np.array(p["pos"]); d = np.array([p["dir"][1], 0, -p["dir"][0]]) * 8
        if dst:
            cv2.drawMarker(img, P(c), (90, 90, 90), cv2.MARKER_TILTED_CROSS, int(10 * scale), 1)
        elif s == 1:
            cv2.line(img, P(c - d), P(c + d), (40, 110, 190), max(2, thick), cv2.LINE_AA)       # 立着
        else:
            cv2.line(img, P(c - d), P(c + d), (30, 160, 255), max(3, thick * 2), cv2.LINE_AA)   # 放倒
    occupied = {c["hook"] for c in fr["chars"] if c["hook"]}
    for uid, h in st["hooks"].items():
        col = (60, 60, 230) if uid in occupied else (120, 120, 140)
        x, y = P(h["pos"]); r = max(3, int(5 * scale))
        cv2.line(img, (x - r, y - r), (x + r, y - r), col, 2); cv2.line(img, (x, y - r), (x, y + r), col, 2)
    dst = {u: (pr, co, ho) for u, pr, co, ho in fr["doors"]}
    for uid, d in st["doors"].items():
        pr, co, ho = dst.get(uid, (0, False, False))
        col = (80, 255, 80) if ho else ((80, 200, 255) if co else (70, 120, 70))
        x, y = P(d["pos"]); r = max(5, int(10 * scale))
        cv2.rectangle(img, (x - r, y - r // 2), (x + r, y + r // 2), col, 2)
    gst = {u: pr for u, pr in fr["gens"]}
    for uid, g in st["gens"].items():
        pr = gst.get(uid, 0)
        x, y = P(g["pos"]); r = max(5, int(9 * scale))
        cv2.rectangle(img, (x - r, y - r), (x + r, y + r), (60, 60, 60), -1)
        col = (90, 230, 255) if pr >= 100 else (40, 170, 230)
        cv2.ellipse(img, (x, y), (r + 3, r + 3), -90, 0, int(3.6 * pr), col, 2, cv2.LINE_AA)
        if pr >= 100:
            cv2.rectangle(img, (x - r, y - r), (x + r, y + r), (90, 230, 255), 2)


def draw_chars(img, fr, tf, scale, labels, hang):
    but, color, roles = G["but"], G["color"], G["roles"]
    byuid = {c["uid"]: c for c in fr["chars"]}
    b = byuid.get(but)
    if b and b["ptarget"] in byuid:
        t = byuid[b["ptarget"]]
        cv2.line(img, tuple(map(int, tf(b["pos"][0], b["pos"][2]))), tuple(map(int, tf(t["pos"][0], t["pos"][2]))), (60, 60, 200), 1, cv2.LINE_AA)
    for c in fr["chars"]:
        x, y = tf(c["pos"][0], c["pos"][2]); x, y = int(x), int(y)
        r = max(4, int((8 if c["uid"] == but else 6) * scale))
        col = color.get(c["uid"], (200, 200, 200))
        down = any(t in c["tags"] for t in ("FALL", "HANG", "HANGING"))
        cv2.circle(img, (x, y), r, col, -1 if not down else 2, cv2.LINE_AA)
        dx, dy = c["dir"]
        cv2.line(img, (x, y), (int(x + dx * r * 2.2), int(y + dy * r * 2.2)), col, 2, cv2.LINE_AA)
        if c["uid"] == but:
            cv2.circle(img, (x, y), int(30 * scale), (60, 60, 200), 1, cv2.LINE_AA)          # 近身攻击范围示意
        if labels is not None:
            st = "/".join(TAG_CN[t] for t in c["tags"] if t in TAG_CN)
            if c["uid"] in hang:
                st += " %ds" % (fr["t"] - hang[c["uid"]])
            if c["uid"] == but:      # 监管标在下方，免得和身边的求生者标签叠在一起
                labels.append((x - 16, y + r + 4, roles[c["uid"]]["name"], col))
            else:
                labels.append((x + r + 4, y - r - 6, roles[c["uid"]]["name"] + (" " + st if st else ""), col))


def put_texts(img, items, font):
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    dr = ImageDraw.Draw(pil)
    for x, y, s, col in items:
        rgb = (col[2], col[1], col[0])
        dr.text((x + 1, y + 1), s, font=font, fill=(0, 0, 0))
        dr.text((x, y), s, font=font, fill=rgb)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def render_frame(fr, hang):
    base, BW, BH, view_r, mm_scale = G["base"], G["BW"], G["BH"], G["view_r"], G["mm_scale"]
    but, roles, color, hdr = G["but"], G["roles"], G["color"], G["hdr"]
    by = {c["uid"]: c for c in fr["chars"]}
    b = by.get(but)
    cx, cz = (b["pos"][0], b["pos"][2]) if b else ((G["X0"] + G["X1"]) / 2, (G["Z0"] + G["Z1"]) / 2)
    # 主视图：从底图裁一块再放大
    k_main = MAIN / (2 * view_r * SC)          # 底图像素 → 主视图像素
    bx, bz = to_base(cx, cz)
    half = int(view_r * SC)
    pad = np.full((2 * half, 2 * half, 3), (20, 18, 16), np.uint8)
    xa, za = int(bx) - half, int(bz) - half
    sx0, sz0 = max(0, xa), max(0, za); sx1, sz1 = min(BW, xa + 2 * half), min(BH, za + 2 * half)
    if sx1 > sx0 and sz1 > sz0:
        pad[sz0 - za:sz1 - za, sx0 - xa:sx1 - xa] = base[sz0:sz1, sx0:sx1]
    main = cv2.resize(pad, (MAIN, MAIN), interpolation=cv2.INTER_LINEAR)

    def tf_main(x, zz):
        px, pz = to_base(x, zz)
        return (px - xa) * k_main, (pz - za) * k_main
    draw_static_dyn(main, fr, tf_main, k_main * SC, 2)
    labels = []
    draw_chars(main, fr, tf_main, k_main * SC, labels, hang)
    main = put_texts(main, labels, G["fonts"][16])

    # 右栏
    side = np.full((H, W - MAIN, 3), (34, 32, 30), np.uint8)
    mm = G["mm_base"].copy()
    MMH, MMW = mm.shape[:2]

    def tf_mm(x, zz):
        px, pz = to_base(x, zz)
        return px * mm_scale, pz * mm_scale
    draw_static_dyn(mm, fr, tf_mm, mm_scale * SC, 1)
    draw_chars(mm, fr, tf_mm, mm_scale * SC, None, hang)
    vx0, vz0 = tf_mm(cx - view_r, cz - view_r); vx1, vz1 = tf_mm(cx + view_r, cz + view_r)
    cv2.rectangle(mm, (int(vx0), int(vz0)), (int(vx1), int(vz1)), (200, 200, 200), 1)
    ox = (W - MAIN - MMW) // 2
    side[10:10 + MMH, ox:ox + MMW] = mm
    texts = []
    y = 20 + MMH
    texts.append((20, y, "第五人格模拟器 · 军工厂 · 种子 %d   模拟 %d:%04.1f  (2× 速)" % (hdr["seed"], int(fr["t"] // 60), fr["t"] % 60), (240, 240, 240)))
    y += 36
    gp = [pr for _, pr in fr["gens"]]
    texts.append((20, y, "密码机  已修 %d / 7（开门需 5）" % sum(1 for p in gp if p >= 100), (90, 230, 255)))
    for i, pr in enumerate(gp):
        x0 = 20 + i * 96
        cv2.rectangle(side, (x0, y + 30), (x0 + 86, y + 44), (70, 70, 70), -1)
        cv2.rectangle(side, (x0, y + 30), (x0 + int(86 * min(pr, 100) / 100), y + 44), (90, 230, 255) if pr >= 100 else (40, 170, 230), -1)
    y += 62
    pb = (b["policy"] or "") if b else ""
    texts.append((20, y, "%s（监管）  策略: %s" % (roles[but]["name"], pb or "-"), color[but]))
    y += 30
    for uid in G["civ_order"]:
        c = by.get(uid)
        if c is None:
            st = "已淘汰"
        elif c["leave"]:
            st = "已逃生"
        else:
            st = "/".join(TAG_CN[t] for t in c["tags"] if t in TAG_CN) or "自由"
            if uid in hang:
                st += "  已挂 %d 秒" % (fr["t"] - hang[uid])
            if c["policy"]:
                st += "   策略 " + c["policy"]
        texts.append((20, y, "%s：%s" % (roles[uid]["name"], st), color[uid]))
        y += 28
    side = put_texts(side, texts, G["fonts"][16])
    return np.concatenate([main, side], axis=1)


def render_chunk(task):
    """工作进程：渲染一小块连续帧，原样交回 BGR 帧（由主进程按顺序编码）。"""
    offsets, hangs = task
    out = []
    with open(G["src"], "rb") as f:
        for off, hang in zip(offsets, hangs):
            f.seek(off)
            out.append(render_frame(json.loads(f.readline()), hang))
    return out


def main():
    src, out = sys.argv[1], sys.argv[2]
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    view_r = float(sys.argv[4]) if len(sys.argv) > 4 else 360.0
    jobs = int(sys.argv[5]) if len(sys.argv) > 5 else int(os.environ.get("RENDER_JOBS", "8"))
    t0 = time.time()
    hdr, offsets, hangs = scan(src)
    n = len(offsets)
    base, bounds = build_base()
    tmp = tempfile.mkdtemp(prefix="render_")
    vw = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    assert vw.isOpened(), "VideoWriter 打不开: " + out
    total = 0
    try:
        base_path = os.path.join(tmp, "base.npy")
        np.save(base_path, base)
        del base
        jobs = max(1, min(jobs, n))
        tasks = [(offsets[a:a + CHUNK], hangs[a:a + CHUNK]) for a in range(0, n, CHUNK)]
        print("共 %d 帧，%d 块，%d 个进程（准备 %.1fs）" % (n, len(tasks), jobs, time.time() - t0), flush=True)
        if jobs == 1:
            init_worker(src, base_path, bounds, view_r, hdr)
            chunks = (render_chunk(t) for t in tasks)
            pool = None
        else:
            import multiprocessing as mp
            pool = mp.get_context("spawn").Pool(jobs, initializer=init_worker, initargs=(src, base_path, bounds, view_r, hdr))

            def ordered():
                # 主进程按顺序编码；最多让工作进程领先 jobs+2 块，防止帧堆在内存里（每帧 1600×900×3 ≈ 4.3MB）
                pending = {}
                nxt = 0
                for i, t in enumerate(tasks):
                    pending[i] = pool.apply_async(render_chunk, (t,))
                    while len(pending) > jobs + 2:
                        yield pending.pop(nxt).get(); nxt += 1
                while pending:
                    yield pending.pop(nxt).get(); nxt += 1
            chunks = ordered()
        last_print = 0
        for frames in chunks:
            for img in frames:
                vw.write(img)
            total += len(frames)
            if total - last_print >= 1200 or total == n:
                last_print = total
                print("  渲染 %d/%d（%.0fs）" % (total, n, time.time() - t0), flush=True)
        if pool is not None:
            pool.close(); pool.join()
    finally:
        vw.release()
        shutil.rmtree(tmp, ignore_errors=True)
    print("写出", out, os.path.getsize(out) // (1024 * 1024), "MB", total, "帧（录像 %d 帧），用时 %.0fs" % (n, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
