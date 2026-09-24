"""入口：python main.py"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from pet.tray import build_tray
from pet.window import PetWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关掉窗口不等于退出，桌宠常驻托盘
    app.setApplicationName("桌宠")

    pet = PetWindow()
    pet.show()

    tray = build_tray(app, pet)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
