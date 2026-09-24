"""气泡对话：跟着小猫飘在头顶的小浮窗。

v2 的三个升级：
1. 打字机效果——文字一个一个冒出来，不像以前整段砸出来；
2. 多行排版——长回答能换行，不再被截成一坨；
3. 情绪配色——边框和底色跟着当前心情标签换。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .config import BUBBLE_MAX_WIDTH, BUBBLE_MS, TYPE_MS

# 情绪标签 → (底色, 边框, 文字色)
PALETTES: dict[str, tuple[str, str, str]] = {
    "开心": ("#fff6e0", "#f2b53d", "#5a4520"),
    "兴奋": ("#ffe9f0", "#ff6f91", "#5c2338"),
    "期待": ("#eef6ff", "#4c9be8", "#1f3b5c"),
    "好奇": ("#eefaf1", "#3fb27f", "#1d4a37"),
    "安心": ("#f2f7ef", "#88b573", "#2f4326"),
    "平静": ("#f7f7fb", "#8b8ba7", "#3a3a4a"),
    "害羞": ("#ffeef2", "#ef8ba8", "#5c2b3c"),
    "孤独": ("#eef0f8", "#6f7bb5", "#2c3055"),
    "烦躁": ("#fff1ea", "#f0803c", "#5c3218"),
    "疲惫": ("#f2f2f6", "#9a9ab5", "#3b3b4d"),
    "失落": ("#f0f2f6", "#7d8aa3", "#2f3547"),
    "委屈": ("#f3eefc", "#a287e0", "#3a2b5c"),
    "悲伤": ("#eaf1fb", "#5b82c4", "#22365c"),
    "愤怒": ("#ffeaea", "#e25555", "#5c2020"),
    "忧虑": ("#f6f3ea", "#c0a45c", "#4a3d18"),
}
DEFAULT_PALETTE = PALETTES["平静"]


def palette_for(label: str) -> tuple[str, str, str]:
    return PALETTES.get(label or "", DEFAULT_PALETTE)


class Bubble(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(BUBBLE_MAX_WIDTH)
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        # 打字机
        self._type_timer = QTimer(self)
        self._type_timer.timeout.connect(self._tick)
        self._pending = ""
        self._shown = ""

        # 自动隐藏
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        #: 位置变了要重新贴过去，由主窗口注入
        self.anchor = None
        self.set_palette("平静")

    # ---------- 外观 ----------
    def set_palette(self, label: str) -> None:
        bg, border, fg = palette_for(label)
        self._label.setStyleSheet(
            f"""
            QLabel {{
                background: {bg};
                border: 2px solid {border};
                border-radius: 12px;
                padding: 8px 12px;
                color: {fg};
                font: 13px "Microsoft YaHei";
                line-height: 145%;
            }}
            """
        )

    # ---------- 说话 ----------
    def show_text(self, text: str, ms: int | None = None, label: str | None = None) -> None:
        """打字机效果说出一段话。"""
        if label:
            self.set_palette(label)
        self._hide_timer.stop()
        self._shown = ""
        self._pending = text
        self._label.setText("")
        self.adjustSize()
        self.show()
        self.raise_()
        if self.anchor:
            self.anchor()
        self._ms = ms if ms is not None else self._auto_ms(text)
        self._type_timer.start(TYPE_MS)

    def live_text(self, text: str, label: str | None = None) -> None:
        """流式输出：整段直接刷新，不走打字机。"""
        if label:
            self.set_palette(label)
        self._hide_timer.stop()
        self._type_timer.stop()
        self._pending = ""
        self._shown = text
        self._label.setText(text)
        self.adjustSize()
        if not self.isVisible():
            self.show()
            self.raise_()
        if self.anchor:
            self.anchor()

    def settle(self, ms: int | None = None) -> None:
        """流式结束后开始计时隐藏。"""
        self._hide_timer.start(ms if ms is not None else self._auto_ms(self._shown))

    def _tick(self) -> None:
        if not self._pending:
            self._type_timer.stop()
            if self._ms:
                self._hide_timer.start(self._ms)
            return
        step = 2 if len(self._pending) > 24 else 1
        self._shown += self._pending[:step]
        self._pending = self._pending[step:]
        self._label.setText(self._shown)
        self.adjustSize()
        if self.anchor:
            self.anchor()
        if not self._pending:
            self._type_timer.stop()
            if self._ms:
                self._hide_timer.start(self._ms)

    @staticmethod
    def _auto_ms(text: str) -> int:
        # 字越多给越多时间读，但有上限
        return min(12000, BUBBLE_MS + len(text) * 55)
