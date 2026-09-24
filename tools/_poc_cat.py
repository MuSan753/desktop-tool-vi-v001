"""把 3D 小猫渲出来看效果（迭代用，定稿会换成正式生成器）。

    python tools/_poc_cat.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from render.cat import Pose, build_cat  # noqa: E402
from render.raster import Renderer  # noqa: E402

OUT = ROOT / "_poc_cat.png"


def render_one(pose: Pose, size: int = 180, ss: int = 3) -> Image.Image:
    renderer = Renderer(size, size, supersample=ss, camera_yaw=pose.camera_yaw)
    parts = build_cat(pose)
    arr = renderer.render(parts)
    return Image.fromarray(arr, mode="RGBA")


def main() -> int:
    poses: list[tuple[str, Pose]] = [
        ("idle", Pose(mouth="omega")),
        ("happy", Pose(mouth="smile", eye_open=(0.45, 0.45), ear=(0.2, 0.2), blush=0.6,
                       head_roll=0.05, paw_lift=(0.06, 0.06))),
        ("angry", Pose(mouth="sad", brow=(0.55, 0.55), ear=(-0.5, -0.5), eye_open=(0.75, 0.75))),
        ("sad", Pose(mouth="sad", brow=(-0.45, -0.45), ear=(-0.35, -0.35), eye_open=(0.6, 0.6))),
        ("surprised", Pose(mouth="o", eye_open=(1.15, 1.15), ear=(0.45, 0.45), head_pitch=-0.1)),
        ("sleepy", Pose(mouth="flat", eye_open=(0.18, 0.18), head_pitch=0.22, tail=(0.3, 0.2, 0.1))),
        ("walk", Pose(mouth="smile", paw=(0.18, -0.18), paw_lift=(0.08, 0.0), head_yaw=0.12)),
        ("side", Pose(mouth="omega", camera_yaw=0.5)),
    ]

    tiles = []
    t0 = time.time()
    for name, pose in poses:
        img = render_one(pose)
        tiles.append((name, img))
    print(f"渲染 {len(poses)} 帧，用时 {time.time() - t0:.1f}s")

    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    w = tiles[0][1].width
    sheet = Image.new("RGBA", (cols * w, rows * w), (44, 44, 58, 255))
    for i, (_, img) in enumerate(tiles):
        sheet.alpha_composite(img, ((i % cols) * w, (i // cols) * w))
    sheet.convert("RGB").save(OUT)
    print("->", OUT, sheet.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
