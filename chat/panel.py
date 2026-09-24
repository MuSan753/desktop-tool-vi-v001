"""聊天面板：贴在小猫身边的浮层。

不做成独立大窗口——桌宠的价值是"触手可及"，点一下就出来，
失焦收起，位置跟着猫走。所以面板自己也允许拖动。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.bus import bus
from life.mood import visible_text

from .persona import names

CARD_BG = "rgba(28, 28, 36, 0.94)"
BORDER = "rgba(255, 255, 255, 0.10)"
TEXT = "#e8e6f0"
SUBTEXT = "#9d97b0"
ACCENT = "#ff92a8"

USER_BUBBLE = f"""
QLabel {{
    background: {ACCENT};
    color: #2a2030;
    border-radius: 14px;
    padding: 8px 12px;
    font: 13px "Microsoft YaHei";
}}
"""

CAT_BUBBLE = f"""
QLabel {{
    background: rgba(255, 255, 255, 0.08);
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 8px 12px;
    font: 13px "Microsoft YaHei";
    line-height: 140%;
}}
"""

PANEL_STYLE = f"""
#card {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
#title {{ color: {TEXT}; font: bold 13px "Microsoft YaHei"; }}
#status {{ color: {SUBTEXT}; font: 11px "Microsoft YaHei"; }}
QLabel {{ color: {SUBTEXT}; font: 12px "Microsoft YaHei"; }}
QComboBox {{
    background: rgba(255,255,255,0.06);
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 3px 8px;
    font: 12px "Microsoft YaHei";
}}
QComboBox QAbstractItemView {{
    background: #23232e; color: {TEXT};
    selection-background-color: rgba(255,146,168,0.25);
    border: 1px solid {BORDER};
}}
QTextEdit {{
    background: rgba(255,255,255,0.05);
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px 8px;
    font: 13px "Microsoft YaHei";
}}
QPushButton {{
    background: rgba(255,255,255,0.06);
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px 10px;
    font: 12px "Microsoft YaHei";
}}
QPushButton:hover {{ background: rgba(255,255,255,0.12); }}
QPushButton:checked {{ background: rgba(255,146,168,0.22); border-color: {ACCENT}; }}
#send {{
    background: {ACCENT}; color: #2a2030; border: none; padding: 6px 14px;
    font: bold 12px "Microsoft YaHei";
}}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.14); border-radius: 4px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


class InputBox(QTextEdit):
    """Enter 发送，Shift+Enter 换行。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("说点什么…（Enter 发送 / Shift+Enter 换行）")
        self.setFixedHeight(72)
        self.setAcceptRichText(False)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                return super().keyPressEvent(event)
            self.parent()._send() if hasattr(self.parent(), "_send") else None
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            window = self.window()
            window.hide()
            event.accept()
            return
        super().keyPressEvent(event)


class ChatPanel(QWidget):
    persona_selected = Signal(str)
    clear_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("和小猫说话")
        self.setFixedWidth(340)
        self.setMinimumHeight(360)

        self._drag_offset: QPoint | None = None
        self._stream_label: QLabel | None = None
        self._raw = ""
        self._follow_enabled = True

        card = QWidget(self)
        card.setObjectName("card")
        self.setStyleSheet(PANEL_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        # ---- 顶部 ----
        header = QWidget()
        hrow = QHBoxLayout(header)
        hrow.setContentsMargins(0, 0, 0, 0)
        hrow.setSpacing(6)

        title = QLabel("和小猫说话")
        title.setObjectName("title")
        self.combo = QComboBox()
        self.combo.addItems(names())
        self.combo.setToolTip("切换人格")
        self.combo.currentTextChanged.connect(self.persona_selected)

        self.btn_pin = QPushButton("置顶")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setChecked(True)
        self.btn_pin.clicked.connect(self._toggle_pin)
        self.btn_follow = QPushButton("跟随")
        self.btn_follow.setCheckable(True)
        self.btn_follow.setChecked(True)
        self.btn_follow.setToolTip("面板是否跟着小猫移动")
        self.btn_follow.clicked.connect(lambda c: setattr(self, "_follow_enabled", c))
        self.btn_clear = QPushButton("清空")
        self.btn_clear.clicked.connect(self.clear_requested)
        self.btn_close = QPushButton("×")
        self.btn_close.setFixedWidth(28)
        self.btn_close.clicked.connect(self.hide)

        hrow.addWidget(title)
        hrow.addStretch()
        for w in (self.combo, self.btn_pin, self.btn_follow, self.btn_clear, self.btn_close):
            hrow.addWidget(w)

        # ---- 消息区 ----
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        self.messages = QVBoxLayout(self.content)
        self.messages.setContentsMargins(2, 2, 2, 2)
        self.messages.setSpacing(6)
        self.messages.addStretch()
        self.scroll.setWidget(self.content)

        # ---- 输入区 ----
        footer = QWidget()
        frow = QVBoxLayout(footer)
        frow.setContentsMargins(0, 0, 0, 0)
        frow.setSpacing(4)

        send_row = QHBoxLayout()
        self.input = InputBox(self)
        self.btn_send = QPushButton("发送")
        self.btn_send.setObjectName("send")
        self.btn_send.setFixedHeight(72)
        self.btn_send.clicked.connect(self._send)
        send_row.addWidget(self.input, 1)
        send_row.addWidget(self.btn_send)

        self.status = QLabel("")
        self.status.setObjectName("status")

        frow.addLayout(send_row)
        frow.addWidget(self.status)

        root.addWidget(header)
        root.addWidget(self.scroll, 1)
        root.addWidget(footer)

        bus.reply_token.connect(self._on_token)
        bus.reply_started.connect(self._on_started)
        bus.reply_finished.connect(self._on_finished)
        bus.reply_failed.connect(self._on_failed)
        bus.pet_moved.connect(self._follow)
        bus.persona_changed.connect(self._sync_combo)

    # ---------- 对外 ----------
    def set_persona(self, persona: str) -> None:
        self._sync_combo(persona)

    def show_near(self, x: int, y: int, w: int, h: int) -> None:
        self._follow(x, y, w, h)
        if self.isHidden():
            self.setWindowOpacity(0.0)
            self.show()
            self.raise_()
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(160)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.start()
        self.input.setFocus()

    def append_user(self, text: str) -> None:
        self._bubble("user", text)

    def append_cat(self, text: str, provider: str = "") -> None:
        self._bubble("cat", text)
        if provider:
            self.status.setText(f"来自：{provider}")

    def notice(self, text: str) -> None:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color: {SUBTEXT}; font: 11px 'Microsoft YaHei'; padding: 2px;")
        self._insert(label)

    # ---------- 内部 ----------
    def _bubble(self, role: str, text: str) -> QLabel:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 2, 0, 2)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setMaximumWidth(250)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        label.setStyleSheet(USER_BUBBLE if role == "user" else CAT_BUBBLE)
        if role == "user":
            lay.addStretch()
            lay.addWidget(label)
        else:
            lay.addWidget(label)
            lay.addStretch()
        self._insert(row)
        return label

    def _insert(self, widget: QWidget) -> None:
        # stretch 始终排在最后，新消息插到它前面
        self.messages.insertWidget(self.messages.count() - 1, widget)
        QApplication.processEvents()
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def bind_submit(self, handler) -> None:
        """注入真正的发送函数（由 main 接到控制器上）。"""
        self._submit = handler

    def _send(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.append_user(text)
        handler = getattr(self, "_submit", None)
        if handler:
            handler(text)

    # ---------- 流式槽 ----------
    @Slot()
    def _on_started(self) -> None:
        self._raw = ""
        self.status.setText("思考中…")
        self._stream_label = self._bubble("cat", "")

    @Slot(str)
    def _on_token(self, chunk: str) -> None:
        self._raw += chunk
        if self._stream_label is not None:
            self._stream_label.setText(visible_text(self._raw))

    @Slot(str, str)
    def _on_finished(self, text: str, provider: str) -> None:
        if self._stream_label is not None:
            final = text or visible_text(self._raw)
            self._stream_label.setText(final or "……")
            self._stream_label = None
        self.status.setText(f"来自：{provider}" if provider else "")
        self._raw = ""

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        if self._stream_label is not None:
            self._stream_label.setText(f"（网络断了：{message}）")
            self._stream_label = None
        self.status.setText("请求失败")

    # ---------- 位置 / 外观 ----------
    @Slot(int, int, int, int)
    def _follow(self, x: int, y: int, w: int, h: int) -> None:
        if not self._follow_enabled or self.isHidden():
            return
        screen = QApplication.screenAt(QPoint(x, y)) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        px = x + w + 12
        if px + self.width() > area.right():
            px = max(area.left(), x - self.width() - 12)
        py = min(max(area.top(), y + h - self.height()), area.bottom() - self.height())
        self.move(px, py)

    def _toggle_pin(self, checked: bool) -> None:
        flags = Qt.FramelessWindowHint | Qt.Tool
        if checked:
            flags |= Qt.WindowStaysOnTopHint
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    @Slot(str)
    def _sync_combo(self, persona: str) -> None:
        index = self.combo.findText(persona)
        if index >= 0 and self.combo.currentIndex() != index:
            self.combo.blockSignals(True)
            self.combo.setCurrentIndex(index)
            self.combo.blockSignals(False)

    def clear_messages(self) -> None:
        while self.messages.count() > 1:
            item = self.messages.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # ---------- 拖动 ----------
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and event.position().y() < 44:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._follow_enabled = False
            self.btn_follow.setChecked(False)
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_offset = None
        event.accept()
