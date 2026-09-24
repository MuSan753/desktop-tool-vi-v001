"""全局事件总线。

各模块只跟总线打交道，不互相 import——
UI 层发请求，宠物层订阅，对话层推进度，彼此都不知道对方存在。
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class Bus(QObject):
    # 宠物想说话（被点了一下、放置自言自语）
    pet_say = Signal(str)
    # 用户点了"打开对话"
    open_chat = Signal()
    # 宠物位置变了，聊天面板要跟过去
    pet_moved = Signal(int, int, int, int)  # x, y, w, h
    # 一轮回答的生命周期
    reply_started = Signal()
    reply_token = Signal(str)
    reply_finished = Signal(str, str)  # 全文, 提供方名字
    reply_failed = Signal(str)
    # 正在生成，用来让宠物播思考动画
    thinking = Signal(bool)
    # 情绪变化，气泡配色跟着换
    mood_changed = Signal(str)
    # 人格切换 / 清空记忆
    persona_changed = Signal(str)
    history_cleared = Signal()
    # 生成控制
    cancel_requested = Signal()
    regenerate_requested = Signal()
    regenerate_done = Signal()  # 面板收到后撤掉最后一对气泡


bus = Bus()
