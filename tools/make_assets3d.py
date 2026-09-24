"""生成 3D 小猫的全套动作帧。

    python tools/make_assets3d.py

每个动作是一组参数化姿态；表情类动作（happy/angry/sad/...）由情绪系统按标签触发。
渲染是离线的，运行时照旧播 PNG 序列帧，主程序零额外开销。
2D 叠加元素（爱心、怒气、泪滴、Zzz）画在 3D 合成之后，不参与遮挡。
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from render.cat import Pose, build_cat  # noqa: E402
from render.raster import Renderer  # noqa: E402

ASSETS = ROOT / "assets"
SIZE = 180
SS = 3


# ---------- 2D 叠加 ----------
def _heart(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color=(255, 110, 140)) -> None:
    d.ellipse([cx - s, cy - s * 0.9, cx, cy], fill=color)
    d.ellipse([cx, cy - s * 0.9, cx + s, cy], fill=color)
    d.polygon([(cx - s, cy - s * 0.25), (cx + s, cy - s * 0.25), (cx, cy + s)], fill=color)


def _drop(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color=(120, 170, 235)) -> None:
    d.polygon([(cx, cy - s), (cx - s * 0.62, cy + s * 0.15), (cx + s * 0.62, cy + s * 0.15)], fill=color)
    d.ellipse([cx - s * 0.62, cy - s * 0.05, cx + s * 0.62, cy + s * 0.85], fill=color)


def _anger_mark(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color=(232, 80, 80)) -> None:
    """漫画怒气筋：四段短弧拼成的十字花。"""
    for a0 in (20, 110, 200, 290):
        d.arc([cx - s, cy - s * 0.8, cx + s, cy + s * 0.8], a0, a0 + 55, fill=color, width=3)


def _zzz(d: ImageDraw.ImageDraw, cx: float, cy: float, step: float) -> None:
    for i in range(3):
        s = 7 + i * 3
        x, y = cx + i * 11, cy - i * 13 - step * 3
        alpha = max(60, 220 - i * 60)
        color = (130, 116, 150, alpha)
        d.line([(x, y), (x + s, y), (x, y + s), (x + s, y + s)], fill=color, width=3)


def _sparkle(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, color=(255, 208, 96)) -> None:
    d.line([(cx - s, cy), (cx + s, cy)], fill=color, width=3)
    d.line([(cx, cy - s), (cx, cy + s)], fill=color, width=3)


def _exclaim(d: ImageDraw.ImageDraw, cx: float, cy: float, color=(255, 150, 90)) -> None:
    d.line([(cx, cy), (cx, cy + 16)], fill=color, width=5)
    d.ellipse([cx - 3, cy + 22, cx + 3, cy + 28], fill=color)


def draw_extras(img: Image.Image, extras: tuple[str, ...], phase: float = 0.0) -> Image.Image:
    if not extras:
        return img
    d = ImageDraw.Draw(img)
    bob = math.sin(phase * math.tau) * 2
    for item in extras:
        if item == "hearts":
            _heart(d, 132, 34 + bob, 9)
            _heart(d, 148, 52 - bob, 6)
        elif item == "anger":
            _anger_mark(d, 136, 30, 11)
        elif item == "tear":
            _drop(d, 116, 84, 6)
        elif item == "sweat":
            _drop(d, 42, 48, 6)
        elif item == "zzz":
            _zzz(d, 128, 46, phase)
        elif item == "sparkle":
            _sparkle(d, 136, 28 + bob, 8)
            _sparkle(d, 154, 50 - bob, 5)
        elif item == "exclaim":
            _exclaim(d, 140, 22)
        elif item == "music":
            d.ellipse([138, 44, 148, 54], outline=(150, 130, 170), width=2)
            d.line([(148, 44), (148, 28)], fill=(150, 130, 170), width=2)
            d.line([(148, 28), (156, 25)], fill=(150, 130, 170), width=2)
    return img


# ---------- 动作定义 ----------
def action_frames() -> dict[str, list[tuple[Pose, tuple[str, ...]]]]:
    """动作名 → [(姿态, 2D叠加), ...] 按播放顺序。"""
    tau = math.tau
    out: dict[str, list] = {}

    # idle：呼吸 + 尾巴摆 + 眨眼
    frames = []
    for i in range(8):
        ph = tau * i / 8
        frames.append((
            Pose(mouth="omega", breath=math.sin(ph), tail=(math.sin(ph) * 0.5, math.sin(ph + 1) * 0.4, 0.0),
                 eye_open=(0.05, 0.05) if i == 5 else (1, 1)),
            (),
        ))
    out["idle"] = frames

    # walk：爪子交替 + 身体起伏
    frames = []
    for i in range(8):
        ph = tau * i / 8
        frames.append((
            Pose(mouth="smile", bob=abs(math.sin(ph)) * 0.05,
                 paw=(math.sin(ph) * 0.16, -math.sin(ph) * 0.16),
                 paw_lift=(max(0.0, math.sin(ph)) * 0.10, max(0.0, -math.sin(ph)) * 0.10),
                 tail=(math.sin(ph) * 0.7, math.sin(ph + 0.8) * 0.5, 0.0),
                 head_yaw=math.sin(ph) * 0.03),
            (),
        ))
    out["walk"] = frames

    # click / happy：蹲下-起跳-落地，星星
    seq = [(0.06, -0.0, ()), (0.12, 0.0, ()), (-0.10, 0.30, ("sparkle",)),
           (-0.16, 0.55, ("sparkle",)), (-0.06, 0.25, ("sparkle",)), (0.0, 0.0, ())]
    frames = []
    for squat, hop, ex in seq:
        frames.append((
            Pose(mouth="open" if hop > 0.2 else "smile", eye_open=(0.35, 0.35) if hop > 0.2 else (1, 1),
                 squat=squat, hop=hop, blush=0.55, ear=(0.25, 0.25), tail=(0.4, 0.3, 0.1)),
            ex,
        ))
    out["click"] = frames
    out["happy"] = [(Pose(mouth="open", eye_open=(0.3, 0.3), blush=0.6, ear=(0.3, 0.3),
                          hop=abs(math.sin(tau * i / 6)) * 0.10,
                          tail=(0.5 * math.sin(tau * i / 6), 0.3, 0.0)), ("hearts",) if i in (2, 5) else ())
                    for i in range(6)]

    # think：抬头看天 + 眼珠上飘
    frames = []
    for i in range(6):
        ph = tau * i / 6
        frames.append((
            Pose(mouth="flat", head_pitch=-0.14, eye_open=(0.85, 0.85),
                 tail=(0.2 * math.sin(ph), 0.15 * math.sin(ph + 1), 0.0),
                 breath=math.sin(ph) * 0.4),
            (),
        ))
    out["think"] = frames

    # sit：轻微呼吸
    frames = []
    for i in range(4):
        ph = tau * i / 4
        frames.append((Pose(mouth="omega", squat=0.06, breath=math.sin(ph) * 0.8,
                            tail=(0.2, 0.1, 0.0)), ()))
    out["sit"] = frames

    # sleep：闭眼 + Zzz
    frames = []
    for i in range(6):
        ph = tau * i / 6
        frames.append((
            Pose(mouth="flat", eye_open=(0.04, 0.04), squat=0.10, breath=math.sin(ph),
                 head_pitch=0.16, head_roll=0.06, tail=(0.1, 0.05, 0.0)),
            ("zzz",),
        ))
    out["sleep"] = frames

    # angry：皱眉 + 耳朵压后 + 尾巴僵直
    frames = []
    for i in range(6):
        ph = tau * i / 6
        frames.append((
            Pose(mouth="sad", brow=(0.55, 0.55), ear=(-0.65, -0.65), eye_open=(0.72, 0.72),
                 head_pitch=0.08, tail=(-0.1, -0.2, -0.3), breath=math.sin(ph) * 0.3),
            ("anger",) if i in (1, 4) else (),
        ))
    out["angry"] = frames

    # sad：耳朵耷拉 + 眉毛内挑 + 泪
    frames = []
    for i in range(6):
        ph = tau * i / 6
        frames.append((
            Pose(mouth="sad", brow=(-0.45, -0.45), ear=(-0.45, -0.45), eye_open=(0.55, 0.55),
                 head_pitch=0.18, head_roll=0.04, blush=0.15, tail=(-0.2, -0.1, 0.0)),
            ("tear",) if i in (2, 5) else (),
        ))
    out["sad"] = frames

    # surprised：瞪眼 + 张嘴 + 耳朵竖起 + 后仰
    frames = []
    for i in range(6):
        ph = tau * i / 6
        frames.append((
            Pose(mouth="o", eye_open=(1.18, 1.18), ear=(0.5, 0.5), head_pitch=-0.10,
                 squat=0.04 * math.sin(ph), tail=(0.0, -0.3, -0.5), pupil=0.8),
            ("exclaim",) if i == 0 else (),
        ))
    out["surprised"] = frames

    # shy：大面积腮红 + 歪头 + 眯眼
    frames = []
    for i in range(6):
        ph = tau * i / 6
        frames.append((
            Pose(mouth="wave", eye_open=(0.4, 0.4), blush=1.0, head_roll=0.12, head_pitch=0.10,
                 ear=(0.1, 0.1), tail=(0.3, 0.2, 0.0), breath=math.sin(ph) * 0.5),
            (),
        ))
    out["shy"] = frames

    # curious：歪头 + 竖耳
    frames = []
    for i in range(6):
        ph = tau * i / 6
        frames.append((
            Pose(mouth="smile", eye_open=(1.0, 1.0), head_roll=-0.14, ear=(0.35, 0.1),
                 tail=(0.3 * math.sin(ph), 0.2, 0.0)),
            ("music",) if i in (1, 4) else (),
        ))
    out["curious"] = frames

    return out


def render_pose(pose: Pose, extras: tuple[str, ...], index: int, total: int) -> Image.Image:
    renderer = Renderer(SIZE, SIZE, supersample=SS, camera_yaw=pose.camera_yaw)
    arr = renderer.render(build_cat(pose))
    img = Image.fromarray(arr, mode="RGBA")
    return draw_extras(img, extras, index / max(1, total))


def main() -> int:
    actions = action_frames()
    total_frames = sum(len(v) for v in actions.values())
    print(f"共 {len(actions)} 个动作 {total_frames} 帧")
    t0 = time.time()
    done = 0

    for name, frames in actions.items():
        folder = ASSETS / name
        folder.mkdir(parents=True, exist_ok=True)
        for f in folder.glob("*.png"):
            f.unlink()
        for index, (pose, extras) in enumerate(frames):
            img = render_pose(pose, extras, index, len(frames))
            img.save(folder / f"{index:02d}.png")
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{total_frames}  {time.time() - t0:.0f}s")

    # 托盘图标
    renderer = Renderer(256, 256, supersample=3)
    arr = renderer.render(build_cat(Pose(mouth="omega")))
    Image.fromarray(arr, "RGBA").resize((128, 128), Image.LANCZOS).save(ASSETS / "tray.png")

    print(f"完成：{total_frames} 帧，用时 {time.time() - t0:.0f}s -> {ASSETS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
