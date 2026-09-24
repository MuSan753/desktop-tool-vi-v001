"""序列帧加载。

素材约定不变：assets/<动作名>/ 下放一排 PNG（00.png、01.png ...），
文件名按数字顺序排列即为播放顺序，透明通道会保留。

v2 加了两条：
1. 缺素材的动作自动回落到 idle，不会因为你没准备睡姿就崩掉；
2. 预生成一份水平镜像帧，猫转身时不用每帧现算。
"""
from __future__ import annotations

from PySide6.QtGui import QPixmap, QTransform

from .config import ACTIONS


class FrameSet:
    """一个动作的帧集合。"""

    def __init__(self, name: str, folder=None) -> None:
        from app.paths import ASSETS

        folder = folder or (ASSETS / name)
        files = sorted(folder.glob("*.png"))
        if not files:
            raise FileNotFoundError(f"缺少素材：{folder}")
        self.name = name
        self.frames = [QPixmap(str(f)) for f in files]
        flip = QTransform().scale(-1, 1)
        self.mirrored = [p.transformed(flip) for p in self.frames]

    def __len__(self) -> int:
        return len(self.frames)

    def frame(self, index: int, flip: bool = False) -> QPixmap:
        source = self.mirrored if flip else self.frames
        if not source:
            raise FileNotFoundError(f"动作 {self.name} 没有帧")
        return source[index % len(source)]

    @property
    def base_size(self) -> tuple[int, int]:
        first = self.frames[0]
        return first.width(), first.height()


def load_sets(actions=ACTIONS) -> dict[str, FrameSet]:
    """加载所有动作；缺素材的用 idle 顶上。"""
    idle = FrameSet("idle")
    sets: dict[str, FrameSet] = {"idle": idle}
    for name in actions:
        if name == "idle":
            continue
        try:
            sets[name] = FrameSet(name)
        except FileNotFoundError:
            sets[name] = idle
    return sets
