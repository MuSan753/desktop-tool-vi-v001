"""托盘图标与右键菜单——桌宠没有标题栏，全靠这里控制。"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .config import ICON, LINES


def build_tray(app: QApplication, pet) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(QIcon(str(ICON)), app)
    tray.setToolTip("桌宠")

    menu = QMenu()

    act_toggle = QAction("显示 / 隐藏", menu)
    act_toggle.triggered.connect(lambda: pet.setVisible(not pet.isVisible()))

    act_say = QAction("说句话", menu)
    act_say.triggered.connect(lambda: pet.say(random.choice(LINES)))

    act_walk = QAction("随机游走", menu)
    act_walk.setCheckable(True)
    act_walk.setChecked(True)
    act_walk.triggered.connect(lambda checked: pet.set_walk_enabled(checked))

    act_top = QAction("窗口置顶", menu)
    act_top.setCheckable(True)
    act_top.setChecked(True)
    act_top.triggered.connect(lambda checked: _set_topmost(pet, checked))

    act_quit = QAction("退出", menu)
    act_quit.triggered.connect(app.quit)

    for action in (act_toggle, act_say, act_walk, act_top, act_quit):
        menu.addAction(action)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: pet.interact() if reason == QSystemTrayIcon.Trigger else None
    )
    return tray


def _set_topmost(pet, enabled: bool) -> None:
    flags = Qt.FramelessWindowHint | Qt.Tool
    if enabled:
        flags |= Qt.WindowStaysOnTopHint
    was_visible = pet.isVisible()
    pet.setWindowFlags(flags)
    if was_visible:
        pet.show()
