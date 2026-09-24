"""入口：python main.py"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.bus import bus
from app.settings import Settings
from brain.router import Router
from chat.controller import ChatController
from chat.history import History
from chat.panel import ChatPanel
from chat.persona import PERSONAS
from chat.session import ChatSession
from life.mood import Mood
from pet.tray import build_tray
from pet.window import PetWindow

RESTORE_COUNT = 40  # 打开面板时回填多少条历史


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关掉面板不等于退出，桌宠常驻托盘
    app.setApplicationName("MiniCat")

    settings = Settings()
    history = History()
    mood = Mood()
    mood.if_idle_for()

    session = ChatSession(settings, history, mood)
    router = Router(settings)

    pet = PetWindow(
        scale=float(settings.get("pet", "scale", 1.0)),
        walk_enabled=bool(settings.get("pet", "walk", True)),
    )
    pet.on_scale_changed = lambda value: settings.set("pet", "scale", value)

    panel = ChatPanel()
    panel.set_persona(session.persona)

    controller = ChatController(settings, history, mood, session, router, app)
    panel.bind_submit(controller.ask)
    panel.persona_selected.connect(controller.switch_persona)
    panel.clear_requested.connect(controller.clear_history)
    controller.system_notice.connect(panel.notice)

    # 回填历史，切换人格 / 重启之后上下文还在
    def restore_history() -> None:
        for row in history.recent_since(0, RESTORE_COUNT):
            if row["role"] == "user":
                panel.append_user(row["content"])
            else:
                panel.append_cat(row["content"])

    restore_history()

    def clear_history() -> None:
        controller.clear_history()
        panel.clear_messages()

    bus.open_chat.connect(lambda: panel.show_near(*pet.geometry_tuple()))
    bus.history_cleared.connect(panel.clear_messages)

    tray = build_tray(
        app,
        pet,
        {
            "open_chat": lambda: panel.show_near(*pet.geometry_tuple()),
            "clear_history": clear_history,
            "walk": bool(settings.get("pet", "walk", True)),
            "persona": session.persona,
            "personas": [(name, conf["desc"]) for name, conf in PERSONAS.items()],
            "set_persona": controller.switch_persona,
        },
    )
    tray.show()

    pet.show()
    app.aboutToQuit.connect(mood.save)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
