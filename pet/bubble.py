"""气泡对话：一个不吃鼠标事件的小窗，跟着桌宠飘在头顶。"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .config import BUBBLE_MAX_WIDTH, BUBBLE_MS

STYLE = """
QLabel {
    background: rgba(255, 255, 255, 235);
    border: 2px solid #6b5b73;
    border-radius: 12px;
    padding: 8px 12px;
    color: #3a3240;
    font: 13px "Microsoft YaHei";
}
"""


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
        self._label.setStyleSheet(STYLE)
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(BUBBLE_MAX_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text: str, ms: int = BUBBLE_MS) -> None:
        self._label.setText(text)
        self.adjustSize()
        self.show()
        self.raise_()
        self._hide_timer.start(ms)
