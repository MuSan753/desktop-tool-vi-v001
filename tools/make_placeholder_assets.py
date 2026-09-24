"""生成角色素材（PNG 序列帧 + 托盘图标）。

    python tools/make_placeholder_assets.py

为了让程序画的猫也能看，做了三件事：
1. 全部按 4 倍分辨率绘制，最后降采样——边缘是平滑的，没有锯齿；
2. 阴影、高光、腮红都用径向渐变贴图叠加，而不是硬边色块；
3. 每种光影都按身体轮廓裁切，不会糊到轮廓外面的透明区上。

素材约定不变：assets/<动作>/ 下 PNG 按文件名数字顺序播放，透明通道保留。
想换成别的角色，直接替换这些 PNG 即可，代码一行不用改。
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

SIZE = 180        # 输出尺寸（逻辑像素）
SS = 4            # 超采样倍数
CANVAS = SIZE * SS

# ---- 调色板 ----
FUR = (250, 244, 235, 255)
FUR_TOP = (255, 253, 249, 255)
BELLY = (255, 255, 252, 255)
SHADE = (198, 184, 176, 255)
OUT = (96, 76, 86, 255)
EAR_IN = (246, 176, 186, 255)
BLUSH = (248, 158, 174, 255)
NOSE = (226, 138, 150, 255)
EYE_DARK = (72, 56, 76, 255)
EYE_IRIS = (132, 96, 78, 255)
EYE_LIGHT = (255, 255, 255, 255)
STAR = (255, 206, 96, 255)
DOT = (124, 108, 138, 255)
SHADOW = (44, 34, 44, 255)

W = 3.0           # 主线宽（逻辑像素）


# ---------- 画笔：逻辑坐标 → 超采样坐标 ----------
class Pen:
    def __init__(self, draw: ImageDraw.ImageDraw) -> None:
        self.d = draw

    def _box(self, x0, y0, x1, y1):
        return [v * SS for v in (x0, y0, x1, y1)]

    def ellipse(self, box, fill=None, outline=None, width=W):
        self.d.ellipse(self._box(*box), fill=fill, outline=outline, width=int(width * SS))

    def polygon(self, pts, fill=None, outline=None, width=W):
        self.d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill, outline=outline, width=int(width * SS))

    def line(self, pts, fill, width=W):
        self.d.line([(x * SS, y * SS) for x, y in pts], fill=fill, width=int(width * SS))

    def arc(self, box, start, end, fill, width=W):
        self.d.arc(self._box(*box), start, end, fill=fill, width=int(width * SS))


# ---------- 柔光贴图 ----------
def soft_ellipse(w: float, h: float, color, strength: int = 255) -> Image.Image:
    """边缘渐隐的椭圆贴图：做阴影、高光、腮红都靠它。"""
    w, h = max(2, int(w * SS)), max(2, int(h * SS))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([0, 0, w - 1, h - 1], fill=color)
    mask = ImageChops.invert(Image.radial_gradient("L").resize((w, h), Image.LANCZOS))
    if strength < 255:
        mask = mask.point(lambda v: int(v * strength / 255))
    layer.putalpha(mask)
    return layer


def paint_shape(img, draw_fn, base=None, textures=(), outline=None, width=W):
    """画一个带光影的形状。

    draw_fn(pen, fill, outline, width) 负责同一种几何形状；
    先在临时层上填底色、叠光影贴图，再用该形状自身轮廓裁掉溢出的部分，
    最后贴回主图并描边——这样渐变永远不会漏到透明背景上。
    """
    piece = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_fn(Pen(ImageDraw.Draw(piece)), fill=base, outline=None, width=width)
    for layer, pos in textures:
        cx, cy = pos
        piece.alpha_composite(layer, (int(cx * SS - layer.width / 2), int(cy * SS - layer.height / 2)))

    mask = Image.new("L", img.size, 0)
    draw_fn(Pen(ImageDraw.Draw(mask)), fill=255, outline=None, width=width)
    piece.putalpha(ImageChops.multiply(piece.getchannel("A"), mask))
    img.alpha_composite(piece)

    if outline is not None:
        draw_fn(Pen(ImageDraw.Draw(img)), fill=None, outline=outline, width=width)


# ---------- 局部零件 ----------
def _bezier(p0, p1, p2, p3, count=28):
    pts = []
    for i in range(count + 1):
        t = i / count
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def draw_tail(pen, x, y, sway):
    tip = (x + 44 + sway * 0.45, y - 34 + sway * 0.4)
    ctrl = (x + 58 + sway * 0.75, y + 4 + sway * 0.5)
    pts = _bezier((x + 16, y + 4), (x + 38, y + 14), ctrl, tip)
    pen.line(pts, OUT, width=12)
    pen.line(pts, SHADE, width=8)
    pen.line(pts[8:], FUR_TOP, width=4)


def ear_box(flip):
    """返回耳朵三角形顶点。flip: -1 左 / 1 右"""
    bx, by = flip * 26, -24
    return [
        (bx - flip * 6, by + 4),
        (bx + flip * 14, by - 46),
        (bx + flip * 24, by + 6),
    ]


def draw_ear(pen, cx, cy, flip):
    pts = [(cx + x, cy + y) for x, y in ear_box(flip)]
    pen.polygon(pts, fill=FUR, outline=OUT)
    inner = [
        (pts[0][0] + flip * 6, pts[0][1] - 5),
        (pts[1][0] + flip * 1, pts[1][1] + 14),
        (pts[2][0] - flip * 5, pts[2][1] - 5),
    ]
    pen.polygon(inner, fill=EAR_IN)


def draw_eye(pen, cx, cy, expr, look=(0, 0)):
    rx, ry = 8.5, 10.5
    if expr == "closed":
        pen.arc((cx - rx, cy - 2, cx + rx, cy + 8), 205, 335, OUT, width=2.6)
        return
    if expr == "happy":
        pen.arc((cx - rx, cy - 1, cx + rx, cy + 9), 215, 325, OUT, width=2.8)
        return

    pen.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=EYE_DARK, outline=OUT)
    ir = 5.4
    pen.ellipse((cx - ir, cy - ir + look[1], cx + ir, cy + ir + look[1]), fill=EYE_IRIS)
    pen.ellipse((cx - 2.6, cy - 6.6 + look[1], cx + 1.2, cy - 2.8 + look[1]), fill=EYE_LIGHT)
    pen.ellipse((cx + 2.0, cy + 1.4 + look[1], cx + 4.6, cy + 4.0 + look[1]), fill=EYE_LIGHT)


def draw_mouth(pen, cx, cy, style):
    if style == "sleep":
        pen.line([(cx - 4, cy + 1), (cx - 1, cy - 3)], OUT, width=2)
        return
    pen.line([(cx - 6, cy), (cx - 2, cy + 4)], NOSE, width=2.6)
    pen.line([(cx - 2, cy + 4), (cx + 2, cy)], NOSE, width=2.6)
    if style == "open":
        pen.ellipse((cx - 6, cy + 3, cx + 6, cy + 13), fill=(214, 122, 138, 255), outline=OUT, width=2)
        return
    pen.arc((cx - 9, cy + 2, cx - 1, cy + 10), 25, 195, OUT, width=2.2)
    pen.arc((cx + 1, cy + 2, cx + 9, cy + 10), 25, 195, OUT, width=2.2)


def draw_star(pen, cx, cy, r):
    pts = []
    for i in range(10):
        ang = math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.44
        pts.append((cx + math.cos(ang) * rad, cy - math.sin(ang) * rad))
    pen.polygon(pts, fill=STAR)


def draw_dots(pen, cx, cy, phase):
    """思考气泡：三个点轮着跳一下。"""
    for i in range(3):
        r = 4.2 if i == phase else 3.2
        cy_i = cy - (5 if i == phase else 0)
        pen.ellipse((cx + 12 + i * 13 - r, cy_i - r, cx + 12 + i * 13 + r, cy_i + r), fill=DOT)


def draw_z(pen, cx, cy, size, alpha=200):
    """手画一个 z，避免依赖字体文件。"""
    color = (108, 94, 122, alpha)
    pts_up = [(cx, cy), (cx + size, cy), (cx, cy + size), (cx + size, cy + size)]
    pen.line(pts_up, color, width=2.4)


# ---------- 主体 ----------
def draw_cat(
    *,
    breath: float = 0,
    bob: float = 0,
    crouch: float = 0,
    look=(0, 0),
    eye: str = "normal",
    mouth: str = "smile",
    tail_sway: float = 0,
    step_x: float = 0,
    sparkle: int = 0,
    dots: int = -1,
    zzz: int = 0,
    shadow: bool = True,
) -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    pen = Pen(ImageDraw.Draw(img))

    cx = SIZE / 2
    ground = 150
    body_cy = 116 - crouch + bob
    head_cy = 66 - crouch + bob + breath * 0.5

    if shadow:
        img.alpha_composite(soft_ellipse(104, 24, SHADOW, 64), (int(cx * SS - 52 * SS), int((ground - 6) * SS)))

    # ---- 尾巴 ----
    draw_tail(pen, cx, body_cy + 6, tail_sway)

    # ---- 身体 ----
    def body(pen, fill, outline, width):
        pen.ellipse((cx - 38, body_cy - 28, cx + 38, body_cy + 30 + breath * 0.5),
                    fill=fill, outline=outline, width=width)

    paint_shape(img, body, base=FUR, outline=OUT,
                textures=[(soft_ellipse(64, 30, SHADE, 90), (cx, body_cy + 22)),
                          (soft_ellipse(46, 34, BELLY, 150), (cx, body_cy + 6))])

    # ---- 前爪 ----
    for side, offset in ((-1, step_x), (1, -step_x)):
        px = cx + side * 17 + offset
        py = body_cy + 26 - abs(offset) * 0.35
        pen.ellipse((px - 10, py - 6, px + 10, py + 8), fill=FUR_TOP, outline=OUT, width=2.4)

    # ---- 耳朵（在头后面）----
    for flip in (-1, 1):
        draw_ear(pen, cx, head_cy, flip)

    # ---- 头 ----
    def head(pen, fill, outline, width):
        pen.ellipse((cx - 45, head_cy - 40, cx + 45, head_cy + 38), fill=fill, outline=outline, width=width)

    paint_shape(img, head, base=FUR, outline=OUT,
                textures=[(soft_ellipse(78, 34, FUR_TOP, 170), (cx, head_cy - 22)),
                          (soft_ellipse(84, 30, SHADE, 80), (cx, head_cy + 30)),
                          (soft_ellipse(20, 12, BLUSH, 150), (cx - 31, head_cy + 19)),
                          (soft_ellipse(20, 12, BLUSH, 150), (cx + 31, head_cy + 19))])

    # ---- 脸 ----
    for ex in (-17, 17):
        draw_eye(pen, cx + ex, head_cy + 3, eye, look)
    draw_mouth(pen, cx, head_cy + 22, mouth)

    # 胡须
    for side in (-1, 1):
        pen.line([(cx + side * 22, head_cy + 20), (cx + side * 42, head_cy + 14)], OUT, width=1.8)
        pen.line([(cx + side * 22, head_cy + 24), (cx + side * 44, head_cy + 25)], OUT, width=1.8)

    # ---- 装饰 ----
    for i in range(sparkle):
        draw_star(pen, cx - 48 + i * 34, head_cy - 54 - (i % 2) * 14, 8 + (i % 2) * 3)
    if dots >= 0:
        draw_dots(pen, cx + 18, head_cy - 46, dots)
    for i in range(zzz):
        draw_z(pen, cx + 30 + i * 9, head_cy - 46 - i * 11, 7 + i * 2, alpha=200 - i * 45)

    return img.resize((SIZE, SIZE), Image.LANCZOS)


# ---------- 动作 ----------
def build_frames():
    import math as m

    actions: dict[str, list[Image.Image]] = {}

    # idle：呼吸 + 尾巴轻摆，第 4 帧眨一下眼
    frames = []
    for i in range(6):
        phase = 2 * m.pi * i / 6
        frames.append(draw_cat(
            breath=m.sin(phase) * 1.6,
            bob=m.sin(phase) * 1.2,
            tail_sway=m.sin(phase) * 9,
            eye="closed" if i == 3 else "normal",
        ))
    actions["idle"] = frames

    # walk：身体上下起伏，前后爪交替
    frames = []
    for i in range(6):
        phase = 2 * m.pi * i / 6
        frames.append(draw_cat(
            bob=-abs(m.sin(phase)) * 2.4,
            step_x=m.sin(phase) * 9,
            tail_sway=m.sin(phase + 0.6) * 14,
            eye="happy" if i in (1, 4) else "normal",
        ))
    actions["walk"] = frames

    # click：蹲一下再蹦起来，星星跟着冒
    crouch_seq = [5, 9, -4, -16, -6, 0]
    sparkle_seq = [0, 0, 2, 3, 1, 0]
    frames = []
    for c, s in zip(crouch_seq, sparkle_seq):
        frames.append(draw_cat(
            crouch=c,
            sparkle=s,
            eye="happy",
            mouth="open" if s else "smile",
            tail_sway=s * 6,
        ))
    actions["click"] = frames

    # think：抬眼看上方，头顶三个思考点轮流动
    frames = []
    for i in range(4):
        frames.append(draw_cat(
            look=(2, -3),
            tail_sway=m.sin(i) * 4,
            eye="normal",
            dots=i % 3,
            breath=m.sin(i) * 0.8,
        ))
    actions["think"] = frames

    # sit：坐下来的姿势，只有轻微呼吸
    frames = []
    for i in range(3):
        phase = 2 * m.pi * i / 3
        frames.append(draw_cat(
            crouch=6,
            breath=m.sin(phase) * 1.2,
            tail_sway=m.sin(phase) * 5,
        ))
    actions["sit"] = frames

    # sleep：闭眼放松，Z 一串串往上飘
    frames = []
    for i in range(4):
        frames.append(draw_cat(
            crouch=8,
            breath=m.sin(2 * m.pi * i / 4) * 1.4,
            eye="closed",
            mouth="sleep",
            tail_sway=m.sin(i) * 3,
            zzz=(i % 3) + 1,
        ))
    actions["sleep"] = frames

    return actions


def save_actions(actions: dict[str, list[Image.Image]]) -> None:
    for name, frames in actions.items():
        folder = ASSETS / name
        folder.mkdir(parents=True, exist_ok=True)
        for f in folder.glob("*.png"):
            f.unlink()
        for index, frame in enumerate(frames):
            frame.save(folder / f"{index:02d}.png")
        print(f"{name}: {len(frames)} 帧 -> {folder}")


def main() -> None:
    actions = build_frames()
    save_actions(actions)

    icon = draw_cat(crouch=0, eye="normal")
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon.resize((128, 128), Image.LANCZOS).save(ASSETS / "tray.png")
    print(f"图标 -> {ASSETS / 'tray.png'}")
    print("素材生成完毕")


if __name__ == "__main__":
    main()
