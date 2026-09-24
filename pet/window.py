"""桌宠主窗口：无边框透明置顶 + 序列帧动画 + 拖拽 + 随机游走 + 点击互动。"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .animation import load_sets
from .bubble import Bubble
from .config import (
    FRAME_MS,
    IDLE_MAX_MS,
    IDLE_MIN_MS,
    LINES,
    WALK_MAX_MS,
    WALK_MIN_MS,
    WALK_SPEED,
    WALK_TICK_MS,
)


class PetWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._sets = load_sets()
        self._mode = "idle"
        self._frame = 0
        self._dir = 1
        self._drag_offset = None
        self._dragged = False
        self.walk_enabled = True

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setWindowTitle("桌宠")

        self._label = QLabel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._bubble = Bubble()

        # 帧动画
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._tick_frame)
        self._frame_timer.start(FRAME_MS)

        # 游走位置刷新
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(self._tick_walk)

        # 状态切换：发呆 ↔ 游走
        self._mood_timer = QTimer(self)
        self._mood_timer.timeout.connect(self._switch_mood)
        self._mood_timer.start(random.randint(IDLE_MIN_MS, IDLE_MAX_MS))

        self._apply_frame()
        self._place_bottom_center()

    # ---------- 渲染 ----------
    @property
    def mode(self) -> str:
        return self._mode

    def _apply_frame(self) -> None:
        frames = self._sets[self._mode]
        pixmap = frames.frame(self._frame)
        if pixmap.size() != self._label.size():
            self._label.setFixedSize(pixmap.size())
            self.setFixedSize(pixmap.size())
        self._label.setPixmap(pixmap)

    def _tick_frame(self) -> None:
        frames = self._sets[self._mode]
        if self._mode == "click":
            # 点击动作只播一遍，停在最后一帧
            if self._frame < len(frames) - 1:
                self._frame += 1
        else:
            self._frame = (self._frame + 1) % len(frames)
        self._apply_frame()

    # ---------- 行为 ----------
    def _switch_mood(self) -> None:
        if self._mode == "click" or not self.walk_enabled:
            return
        if self._mode == "walk":
            self._mode = "idle"
            self._walk_timer.stop()
            self._mood_timer.start(random.randint(IDLE_MIN_MS, IDLE_MAX_MS))
        else:
            self._mode = "walk"
            self._dir = random.choice((-1, 1))
            self._walk_timer.start(WALK_TICK_MS)
            self._mood_timer.start(random.randint(WALK_MIN_MS, WALK_MAX_MS))
        self._frame = 0

    def _tick_walk(self) -> None:
        area = self.screen().availableGeometry()
        x = self.x() + WALK_SPEED * self._dir
        if x <= area.left():
            x, self._dir = area.left(), 1
        elif x + self.width() >= area.right():
            x, self._dir = area.right() - self.width(), -1
        self.move(x, self.y())
        self._sync_bubble()

    def _place_bottom_center(self) -> None:
        area = self.screen().availableGeometry()
        self.move(
            area.center().x() - self.width() // 2,
            area.bottom() - self.height() - 40,
        )
        self._sync_bubble()

    def set_walk_enabled(self, enabled: bool) -> None:
        self.walk_enabled = enabled
        if not enabled and self._mode == "walk":
            self._mode = "idle"
            self._walk_timer.stop()
            self._mood_timer.start(random.randint(IDLE_MIN_MS, IDLE_MAX_MS))

    # ---------- 交互 ----------
    def say(self, text: str) -> None:
        self._bubble.show_text(text)
        self._sync_bubble()

    def _sync_bubble(self) -> None:
        if not self._bubble.isVisible():
            return
        x = self.x() + self.width() // 2 - self._bubble.width() // 2
        y = self.y() - self._bubble.height() - 8
        self._bubble.move(max(0, x), max(0, y))

    def interact(self) -> None:
        """被点一下：播点击动画 + 随机说句话。"""
        self._mode = "click"
        self._frame = 0
        self._walk_timer.stop()
        self._mood_timer.stop()
        self._apply_frame()
        self.say(random.choice(LINES))
        QTimer.singleShot(FRAME_MS * len(self._sets["click"]) + 400, self._back_to_idle)

    def _back_to_idle(self) -> None:
        self._mode = "idle"
        self._frame = 0
        self._apply_frame()
        self._mood_timer.start(random.randint(IDLE_MIN_MS, IDLE_MAX_MS))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragged = False
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._dragged = True
            self._sync_bubble()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            if not self._dragged:
                self.interact()
            event.accept()
