"""把流式生成塞进后台线程。

关键：网络请求绝不能落在主线程。PySide6 的主线程一旦被 IO 卡住，
整只猫会当场冻成一张静态贴图——这是 v1 结构上最大的坑。
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from .router import Router


class ChatWorker(QThread):
    token = Signal(str)
    finished_ok = Signal(str, str)  # 全文, 提供方
    failed = Signal(str)

    def __init__(self, router: Router, messages: list[dict[str, str]], parent=None) -> None:
        super().__init__(parent)
        self._router = router
        self._messages = messages

    def run(self) -> None:  # noqa: D102
        pieces: list[str] = []
        try:
            for chunk in self._router.chat(self._messages):
                if self.isInterruptionRequested():
                    break
                pieces.append(chunk)
                self.token.emit(chunk)
            text = "".join(pieces)
            self.finished_ok.emit(text, self._router.last_provider or "离线兜底")
        except Exception as exc:  # 兜到底：线程里不能抛，会直接崩进程
            self.failed.emit(str(exc) or exc.__class__.__name__)
