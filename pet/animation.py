"""序列帧加载。

素材约定：assets/<动作名>/ 下放一排 PNG（00.png、01.png ...），
文件名按数字顺序排列即为播放顺序，透明通道会保留。
"""
from __future__ import annotations

from PySide6.QtGui import QPixmap

from .config import ACTIONS, ASSETS


class FrameSet:
    """一个动作的帧集合。"""

    def __init__(self, name: str) -> None:
        folder = ASSETS / name
        files = sorted(folder.glob("*.png"))
        if not files:
            raise FileNotFoundError(f"缺少素材：{folder}（先跑 python tools/make_placeholder_assets.py）")
        self.name = name
        self.frames = [QPixmap(str(f)) for f in files]

    def __len__(self) -> int:
        return len(self.frames)

    def frame(self, index: int) -> QPixmap:
        return self.frames[index % len(self.frames)]


def load_sets() -> dict[str, FrameSet]:
    return {name: FrameSet(name) for name in ACTIONS}
