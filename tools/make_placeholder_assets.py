"""生成占位角色素材（PNG 序列帧 + 托盘图标）。

    python tools/make_placeholder_assets.py

画的是一只凑合能看的小猫，用来把程序跑通。
想换成自己的角色时，直接替换 assets/<动作>/ 下的 PNG 即可：
文件名按数字顺序排列就是播放顺序，背景保持透明。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIZE = 160
CENTER = SIZE // 2

BG = (0, 0, 0, 0)
FUR = (247, 241, 232, 255)
FUR_SHADE = (226, 216, 205, 255)
LINE = (64, 58, 64, 255)
PINK = (255, 168, 178, 255)
STAR = (255, 205, 90, 255)


def draw_star(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    d.line([cx - r, cy, cx + r, cy], fill=STAR, width=3)
    d.line([cx, cy - r, cx, cy + r], fill=STAR, width=3)


def draw_pet(
    d: ImageDraw.ImageDraw,
    dy: int = 0,
    dx: int = 0,
    blink: bool = False,
    happy: bool = False,
    tail_dx: int = 0,
    sparkle: int = 0,
) -> None:
    cx = CENTER + dx
    cy = CENTER + dy + 12

    # 尾巴
    d.ellipse([cx + 42 + tail_dx, cy + 6, cx + 78 + tail_dx, cy + 34], fill=FUR_SHADE, outline=LINE, width=3)
    # 耳朵
    d.polygon([(cx - 38, cy - 22), (cx - 46, cy - 70), (cx - 10, cy - 42)], fill=FUR, outline=LINE, width=3)
    d.polygon([(cx + 38, cy - 22), (cx + 46, cy - 70), (cx + 10, cy - 42)], fill=FUR, outline=LINE, width=3)
    # 身体
    d.ellipse([cx - 50, cy - 38, cx + 50, cy + 48], fill=FUR, outline=LINE, width=3)

    # 眼睛
    if blink:
        d.line([cx - 26, cy - 6, cx - 10, cy - 6], fill=LINE, width=4)
        d.line([cx + 10, cy - 6, cx + 26, cy - 6], fill=LINE, width=4)
    elif happy:
        d.arc([cx - 28, cy - 20, cx - 8, cy - 2], 180, 360, fill=LINE, width=4)
        d.arc([cx + 8, cy - 20, cx + 28, cy - 2], 180, 360, fill=LINE, width=4)
    else:
        for ex in (-18, 18):
            d.ellipse([cx + ex - 7, cy - 16, cx + ex + 7, cy + 0], fill=LINE)
            d.ellipse([cx + ex - 3, cy - 14, cx + ex + 1, cy - 10], fill=(255, 255, 255, 255))

    # 腮红 + 嘴
    d.ellipse([cx - 40, cy + 6, cx - 24, cy + 16], fill=PINK)
    d.ellipse([cx + 24, cy + 6, cx + 40, cy + 16], fill=PINK)
    d.arc([cx - 9, cy + 4, cx + 9, cy + 20], 0, 180, fill=LINE, width=3)

    # 开心的星星
    for i in range(sparkle):
        draw_star(d, cx - 52 + i * 36, cy - 74 - (i % 2) * 14, 8)


def save(action: str, params: list[dict]) -> None:
    folder = ASSETS / action
    folder.mkdir(parents=True, exist_ok=True)
    for f in folder.glob("*.png"):
        f.unlink()
    for index, p in enumerate(params):
        img = Image.new("RGBA", (SIZE, SIZE), BG)
        draw_pet(ImageDraw.Draw(img), **p)
        img.save(folder / f"{index:02d}.png")
    print(f"{action}: {len(params)} 帧 -> {folder}")


def main() -> None:
    save(
        "idle",
        [
            {"dy": 0},
            {"dy": -2},
            {"dy": -4, "blink": True},
            {"dy": -1},
        ],
    )
    save(
        "walk",
        [
            {"dy": 0, "dx": 0, "tail_dx": -8},
            {"dy": -3, "dx": 2, "tail_dx": 0},
            {"dy": 0, "dx": 3, "tail_dx": 8},
            {"dy": -3, "dx": 1, "tail_dx": 0},
        ],
    )
    save(
        "click",
        [
            {"dy": 6, "happy": True},
            {"dy": 10, "happy": True},
            {"dy": -12, "happy": True, "sparkle": 2},
            {"dy": -20, "happy": True, "sparkle": 3},
            {"dy": -8, "happy": True, "sparkle": 1},
            {"dy": 0, "happy": True},
        ],
    )

    # 托盘图标：画一张 160 的再缩到 64
    large = Image.new("RGBA", (SIZE, SIZE), BG)
    draw_pet(ImageDraw.Draw(large))
    ASSETS.mkdir(parents=True, exist_ok=True)
    large.resize((64, 64), Image.LANCZOS).save(ASSETS / "tray.png")
    print(f"图标 -> {ASSETS / 'tray.png'}")
    print("素材生成完毕")


if __name__ == "__main__":
    main()
