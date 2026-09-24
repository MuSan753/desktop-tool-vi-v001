"""小星芽渲染迭代预览（临时脚本）。"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from render.cat import Pose, build_cat  # noqa: E402
from render.raster import Renderer  # noqa: E402

OUT = ROOT / "_poc_bud.png"


def render_one(pose: Pose, size: int = 180, ss: int = 3) -> Image.Image:
    renderer = Renderer(size, size, supersample=ss, camera_yaw=pose.camera_yaw)
    arr = renderer.render(build_cat(pose))
    return Image.fromarray(arr, mode="RGBA")


def main() -> int:
    poses = [
        ("idle", Pose(mouth="omega")),
        ("happy", Pose(mouth="open", eye_open=(0.3, 0.3), blush=0.7, ear=(0.5, 0.5), hop=0.06)),
        ("curious", Pose(mouth="smile", ear=(0.7, -0.2), head_roll=-0.12)),
        ("surprised", Pose(mouth="o", eye_open=(1.15, 1.15), ear=(0.8, 0.8), head_pitch=-0.08)),
        ("shy", Pose(mouth="wave", eye_open=(0.4, 0.4), blush=1.0, head_roll=0.12, ear=(-0.2, -0.2))),
        ("sad", Pose(mouth="sad", eye_open=(0.55, 0.55), ear=(-0.7, -0.7), head_pitch=0.15)),
        ("angry", Pose(mouth="flat", eye_open=(0.6, 0.6), ear=(-0.6, -0.6), head_pitch=0.06)),
        ("sleep", Pose(mouth="flat", eye_open=(0.04, 0.04), squat=0.2, head_pitch=0.18)),
        ("side", Pose(mouth="omega", camera_yaw=0.55)),
        ("back", Pose(mouth="omega", camera_yaw=3.14159)),
    ]

    tiles = [render_one(p) for _, p in poses]
    cols = 3
    w = 180
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * w, rows * w), (240, 238, 244, 255))
    for i, img in enumerate(tiles):
        sheet.alpha_composite(img, ((i % cols) * w, (i // cols) * w))
    sheet.convert("RGB").save(OUT)
    print("->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
