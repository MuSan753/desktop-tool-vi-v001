"""把各方粘起来：用户一句话进来，到最后猫说出答案。

所有网络活儿都在 ChatWorker 线程里，控制器只负责中转信号，
所以生成过程中小猫照旧能动、能跳、能被拖走。
"""
from __future__ import annotations

import time

from PySide6.QtCore import QObject, Signal

from app.bus import bus
from app.settings import Settings
from brain.router import Router
from brain.worker import ChatWorker
from life.mood import Mood, parse_or_fallback, visible_text

from .history import History
from .persona import greeting
from .session import ChatSession


class ChatController(QObject):
    system_notice = Signal(str)

    def __init__(
        self,
        settings: Settings,
        history: History,
        mood: Mood,
        session: ChatSession,
        router: Router,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.history = history
        self.mood = mood
        self.session = session
        self.router = router
        self._worker: ChatWorker | None = None
        self._summary_worker: ChatWorker | None = None

    @property
    def busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    # ---------- 主流程 ----------
    def ask(self, text: str) -> None:
        text = (text or "").strip()
        if not text or self.busy:
            return

        self.history.add("user", text)
        messages = self.session.build_messages()

        bus.thinking.emit(True)
        bus.reply_started.emit()

        worker = ChatWorker(self.router, messages, self)
        worker.token.connect(self._on_token)
        worker.finished_ok.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._cleanup)
        self._worker = worker
        worker.start()

    def cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
        bus.thinking.emit(False)

    # ---------- 回调（都在主线程） ----------
    def _on_token(self, chunk: str) -> None:
        bus.reply_token.emit(chunk)

    def _on_finished(self, raw: str, provider: str) -> None:
        text = visible_text(raw)
        parsed = parse_or_fallback(raw)

        self.mood.state.apply_delta(parsed["delta"])
        label = parsed["label"] or self.mood.state.dominant()
        self.mood.state.label = label
        self.mood.state.updated = time.time()
        self.mood.save()

        if text:
            self.history.add("assistant", text)
        bus.thinking.emit(False)
        bus.reply_finished.emit(text, provider)
        bus.mood_changed.emit(label)

        if self.session.should_summarize():
            self._run_summary()

    def _on_failed(self, message: str) -> None:
        bus.thinking.emit(False)
        bus.reply_failed.emit(message)

    def _cleanup(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    # ---------- 摘要（后台悄悄做） ----------
    def _run_summary(self) -> None:
        if self._summary_worker and self._summary_worker.isRunning():
            return
        worker = ChatWorker(self.router, self.session.summary_request(), self)
        worker.finished_ok.connect(self._on_summary_done)
        worker.finished.connect(lambda: setattr(self, "_summary_worker", None))
        self._summary_worker = worker
        worker.start()

    def _on_summary_done(self, text: str, provider: str) -> None:
        self.session.commit_summary(text)

    # ---------- 其它 ----------
    def switch_persona(self, persona: str) -> None:
        self.session.set_persona(persona)
        line = greeting(persona)
        self.history.add("assistant", line)
        bus.persona_changed.emit(persona)
        bus.reply_finished.emit(line, "人格")

    def clear_history(self) -> None:
        self.history.clear()
        bus.history_cleared.emit()
        self.system_notice.emit("对话记录已清空")
