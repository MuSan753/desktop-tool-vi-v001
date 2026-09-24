"""托盘图标与右键菜单。

桌宠没有标题栏，所有控制入口都在这儿。
v2 补了：打开对话、人格切换、体型调节、清空记忆。
"""
from __future__ import annotations

from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from app.paths import ICON

from .config import SCALE_STEP


def build_tray(app: QApplication, pet, handlers: dict) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(QIcon(str(ICON)), app)
    tray.setToolTip("桌宠：双击小猫就能聊天")

    menu = QMenu()

    act_chat = QAction("打开对话", menu)
    act_chat.triggered.connect(handlers["open_chat"])

    act_toggle = QAction("显示 / 隐藏", menu)
    act_toggle.triggered.connect(lambda: pet.setVisible(not pet.isVisible()))

    act_walk = QAction("随机游走", menu)
    act_walk.setCheckable(True)
    act_walk.setChecked(bool(handlers.get("walk", True)))
    act_walk.triggered.connect(lambda checked: pet.set_walk_enabled(checked))

    act_top = QAction("窗口置顶", menu)
    act_top.setCheckable(True)
    act_top.setChecked(True)
    act_top.triggered.connect(lambda checked: pet.set_topmost(checked))

    # 体型：一组三个动作，点完保持菜单打开，方便连续调
    size_menu = QMenu("体型", menu)
    act_bigger = QAction("放大", size_menu)
    act_bigger.triggered.connect(lambda: pet.set_scale(pet.scale + SCALE_STEP))
    act_smaller = QAction("缩小", size_menu)
    act_smaller.triggered.connect(lambda: pet.set_scale(pet.scale - SCALE_STEP))
    act_reset = QAction("恢复原始大小", size_menu)
    act_reset.triggered.connect(lambda: pet.set_scale(1.0))
    for action in (act_bigger, act_smaller, act_reset):
        size_menu.addAction(action)

    # 人格：互斥单选
    persona_menu = QMenu("人格", menu)
    group = QActionGroup(persona_menu)
    group.setExclusive(True)
    current = handlers.get("persona", "")
    for name, desc in handlers.get("personas", []):
        action = QAction(name, persona_menu)
        action.setCheckable(True)
        action.setToolTip(desc)
        action.setChecked(name == current)
        action.triggered.connect(lambda checked, n=name: handlers["set_persona"](n))
        group.addAction(action)
        persona_menu.addAction(action)

    act_clear = QAction("清空对话记录", menu)
    act_clear.triggered.connect(handlers["clear_history"])

    act_quit = QAction("退出", menu)
    act_quit.triggered.connect(app.quit)

    menu.addAction(act_chat)
    menu.addAction(act_toggle)
    menu.addAction(act_walk)
    menu.addAction(act_top)
    menu.addMenu(size_menu)
    menu.addMenu(persona_menu)
    menu.addAction(act_clear)
    menu.addSeparator()
    menu.addAction(act_quit)

    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: handlers["open_chat"]() if reason == QSystemTrayIcon.Trigger else None)
    return tray
