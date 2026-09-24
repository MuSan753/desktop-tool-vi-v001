"""桌宠主窗口：动画 / 拖拽 / 游走 / 互动 / 跟着问题思考。

相比 v1 的改动：
- 状态交给 PetStateMachine 管理（见 pet/states.py），这里只负责渲染和转发事件；
- 新增 think / talk 两个状态：问它问题时盒子上会"嗯……"，答案流式冒泡；
- 双击打开对话面板，滚轮缩放体型；
- 自身不再直接持有任何网络逻辑，全部通过事件总线。
"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.bus import bus
from life.idle_talks import pick
from life.mood import visible_text

from .animation import load_sets
from .bubble import Bubble
from .config import (
    BUBBLE_MS,
    FRAME_MS,
    IDLE_MAX_MS,
    IDLE_MIN_MS,
    SCALE_MAX,
    SCALE_MIN,
    SCALE_STEP,
    SELFTALK_MAX_MS,
    SELFTALK_MIN_MS,
    WALK_MAX_MS,
    WALK_MIN_MS,
    WALK_SPEED,
    WALK_TICK_MS,
)
from .states import CLICK, DRAG, IDLE, TALK, THINK, WALK, StateMachine


class PetWindow(QWidget):
    def __init__(self, scale: float = 1.0, walk_enabled: bool = True) -> None:
        super().__init__()
        self._sets = load_sets()
        self._machine = StateMachine()
        self._frame = 0
        self._dir = 1
        self._drag_offset = None
        self._dragged = False
        self._scale = max(SCALE_MIN, min(SCALE_MAX, scale))
        self.walk_enabled = walk_enabled
        self._mood_label = "平静"
        self._stream_raw = ""
        self.on_scale_changed = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setWindowTitle("桌宠")

        self._label = QLabel(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._bubble = Bubble()
        self._bubble.anchor = self._sync_bubble

        # 帧动画
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._tick_frame)

        # 游走位置刷新
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(self._tick_walk)

        # 状态切换：发呆 ↔ 游走
        self._mood_timer = QTimer(self)
        self._mood_timer.timeout.connect(self._switch_mood)

        # 放置太久会说点话
        self._selftalk_timer = QTimer(self)
        self._selftalk_timer.timeout.connect(self._maybe_selftalk)
        self._selftalk_timer.start(random.randint(SELFTALK_MIN_MS, SELFTALK_MAX_MS))

        self._apply_frame()
        self._place_bottom_center()
        self._frame_timer.start(self._interval())

        bus.thinking.connect(self._on_thinking)
        bus.reply_started.connect(self._on_reply_started)
        bus.reply_token.connect(self._on_token)
        bus.reply_finished.connect(self._on_reply_done)
        bus.reply_failed.connect(self._on_reply_failed)
        bus.mood_changed.connect(self._on_mood)

    # ---------- 渲染 ----------
    @property
    def mode(self) -> str:
        return self._machine.action

    def _interval(self) -> int:
        return FRAME_MS.get(self._machine.action, 150)

    def _base_size(self):
        return self._sets[self._machine.action].base_size

    def _apply_frame(self) -> None:
        action = self._machine.action
        frames = self._sets[action]
        pixmap = frames.frame(self._frame, flip=self._dir < 0)
        bw, bh = frames.base_size
        target_w, target_h = int(bw * self._scale), int(bh * self._scale)
        if self._label.width() != target_w or self._label.height() != target_h:
            self._label.setFixedSize(target_w, target_h)
            self.setFixedSize(target_w, target_h)
        scaled = pixmap.scaled(
            target_w,
            target_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._label.setPixmap(scaled)

    def _tick_frame(self) -> None:
        action = self._machine.action
        frames = self._sets[action]
        if action == CLICK and self._sets[CLICK] is not self._sets[IDLE]:
            if self._frame < len(frames) - 1:
                self._frame += 1
        else:
            self._frame = (self._frame + 1) % len(frames)
        self._apply_frame()

    # ---------- 行为 ----------
    def _switch_mood(self) -> None:
        if self._machine.is_busy() or not self.walk_enabled:
            return
        if self._machine.state == WALK:
            self._machine.set(IDLE)
            self._walk_timer.stop()
            self._mood_timer.start(random.randint(IDLE_MIN_MS, IDLE_MAX_MS))
        else:
            if not self._machine.set(WALK):
                return
            self._dir = random.choice((-1, 1))
            self._walk_timer.start(WALK_TICK_MS)
            self._mood_timer.start(random.randint(WALK_MIN_MS, WALK_MAX_MS))
        self._frame = 0
        self._frame_timer.setInterval(self._interval())
        self._apply_frame()

    def _tick_walk(self) -> None:
        area = self.screen().availableGeometry()
        x = self.x() + WALK_SPEED * self._dir
        if x <= area.left():
            x, self._dir = area.left(), 1
        elif x + self.width() >= area.right():
            x, self._dir = area.right() - self.width(), -1
        self.move(x, self.y())

    def _place_bottom_center(self) -> None:
        area = self.screen().availableGeometry()
        self.move(
            area.center().x() - self.width() // 2,
            area.bottom() - self.height() - 40,
        )

    def _maybe_selftalk(self) -> None:
        self._selftalk_timer.start(random.randint(SELFTALK_MIN_MS, SELFTALK_MAX_MS))
        if self._machine.is_busy() or self._bubble.isVisible() or not self.isVisible():
            return
        self.say(pick(self._mood_label))

    # ---------- 对外控制 ----------
    def set_walk_enabled(self, enabled: bool) -> None:
        self.walk_enabled = enabled
        if not enabled and self._machine.state == WALK:
            self._machine.set(IDLE)
            self._walk_timer.stop()
            self._mood_timer.start(random.randint(IDLE_MIN_MS, IDLE_MAX_MS))
            self._frame_timer.setInterval(self._interval())

    def set_topmost(self, enabled: bool) -> None:
        flags = Qt.FramelessWindowHint | Qt.Tool
        if enabled:
            flags |= Qt.WindowStaysOnTopHint
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        self._bubble.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowTransparentForInput
            | (Qt.WindowStaysOnTopHint if enabled else Qt.WindowType(0))
        )
        if was_visible:
            self.show()

    def set_scale(self, value: float) -> None:
        value = max(SCALE_MIN, min(SCALE_MAX, round(value, 2)))
        if abs(value - self._scale) < 1e-6:
            return
        self._scale = value
        self._apply_frame()
        self._sync_bubble()
        bus.pet_moved.emit(self.x(), self.y(), self.width(), self.height())
        if self.on_scale_changed:
            self.on_scale_changed(self._scale)

    @property
    def scale(self) -> float:
        return self._scale

    def geometry_tuple(self) -> tuple[int, int, int, int]:
        return self.x(), self.y(), self.width(), self.height()

    # ---------- 说话 ----------
    def say(self, text: str, label: str | None = None) -> None:
        if not text:
            return
        self._bubble.show_text(text, label=label or self._mood_label)
        self._sync_bubble()

    def _sync_bubble(self) -> None:
        if not self._bubble.isVisible():
            return
        x = self.x() + self.width() // 2 - self._bubble.width() // 2
        y = self.y() - self._bubble.height() - 8
        self._bubble.move(max(0, x), max(0, y))

    # ---------- 交互 ----------
    def interact(self) -> None:
        """被点一下：播开心动画 + 说句话。"""
        if self._machine.is_busy():
            return
        if self._machine.set(CLICK):
            self._frame = 0
            self._walk_timer.stop()
            self._mood_timer.stop()
            self._frame_timer.setInterval(self._interval())
            self._apply_frame()
            duration = FRAME_MS.get(CLICK, 85) * max(1, len(self._sets[CLICK])) + 350
            QTimer.singleShot(min(duration, 1600), self._back_to_idle)
        self.say(pick(self._mood_label))

    def _back_to_idle(self) -> None:
        if self._machine.state != CLICK:
            return
        self._machine.force(IDLE)
        self._frame = 0
        self._frame_timer.setInterval(self._interval())
        self._apply_frame()
        self._mood_timer.start(random.randint(IDLE_MIN_MS, IDLE_MAX_MS))

    # ---------- 事件总线回调 ----------
    @Slot(bool)
    def _on_thinking(self, active: bool) -> None:
        if active:
            self._stream_raw = ""
            if self._machine.state == WALK:
                self._walk_timer.stop()
            if self._machine.set(THINK):
                self._mood_timer.stop()
                self._frame = 0
                self._frame_timer.setInterval(self._interval())
                self._apply_frame()
            self._bubble.show_text("……", ms=BUBBLE_MS, label=self._mood_label)
        else:
            if self._machine.state in (THINK, TALK):
                self._machine.force(IDLE)
                self._frame_timer.setInterval(self._interval())
                self._mood_timer.start(random.randint(IDLE_MIN_MS, IDLE_MAX_MS))
                self._apply_frame()

    @Slot()
    def _on_reply_started(self) -> None:
        self._stream_raw = ""

    @Slot(str)
    def _on_token(self, chunk: str) -> None:
        self._stream_raw += chunk
        if self._machine.state == THINK and self._machine.set(TALK):
            self._frame_timer.setInterval(self._interval())
        self._bubble.live_text(visible_text(self._stream_raw)[:220], label=self._mood_label)
        self._sync_bubble()

    @Slot(str, str)
    def _on_reply_done(self, text: str, provider: str) -> None:
        self._stream_raw = ""
        self._machine.force(IDLE)
        self._frame_timer.setInterval(self._interval())
        self._apply_frame()
        self._mood_timer.start(random.randint(IDLE_MIN_MS, IDLE_MAX_MS))
        shown = (text or "").strip()
        if shown:
            self._bubble.live_text(shown, label=self._mood_label)
            self._bubble.settle()
            self._sync_bubble()

    @Slot(str)
    def _on_reply_failed(self, message: str) -> None:
        self._machine.force(IDLE)
        self._frame_timer.setInterval(self._interval())
        self.say(f"脑子好像断线了……（{message[:40]}）")

    @Slot(str)
    def _on_mood(self, label: str) -> None:
        self._mood_label = label or "平静"

    # ---------- 鼠标 / 键盘 ----------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragged = False
            self._machine.force(DRAG)
            self._walk_timer.stop()
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
            self._machine.force(IDLE)
            if not self._dragged:
                self.interact()
            self._mood_timer.start(random.randint(IDLE_MIN_MS, IDLE_MAX_MS))
            event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        bus.open_chat.emit()
        event.accept()

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = 1 if event.angleDelta().y() > 0 else -1
        self.set_scale(self._scale + delta * SCALE_STEP)
        event.accept()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.setCursor(QCursor(Qt.PointingHandCursor))
        super().enterEvent(event)

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        self._sync_bubble()
        bus.pet_moved.emit(self.x(), self.y(), self.width(), self.height())

    def closeEvent(self, event) -> None:  # noqa: N802
        self._bubble.close()
        super().closeEvent(event)
