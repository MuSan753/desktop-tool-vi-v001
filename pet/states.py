"""宠物状态机。

v1 的状态切换散在几个 QTimer 回调里，加一个状态就得改三处；
v2 抽出一张转移表，谁往哪儿走能走全部写死在一处。
"""
from __future__ import annotations

# 全部状态
IDLE = "idle"
WALK = "walk"
DRAG = "drag"
CLICK = "click"
THINK = "think"
TALK = "talk"
SLEEP = "sleep"

# 表情动作（由情绪标签触发，播完自动回 idle）
EXPRESSIONS = ("happy", "angry", "sad", "surprised", "shy", "curious")

#: 状态 → 播放哪个动作素材；没有对应素材时会回落 idle
ACTION_OF: dict[str, str] = {
    IDLE: "idle",
    WALK: "walk",
    DRAG: "idle",
    CLICK: "click",
    THINK: "think",
    TALK: "idle",
    SLEEP: "sleep",
}
for _expr in EXPRESSIONS:
    ACTION_OF[_expr] = _expr

_ALL = (IDLE, WALK, DRAG, CLICK, THINK, TALK, SLEEP) + EXPRESSIONS

#: 允许的状态转移（同名转移视为无操作）
ALLOWED: dict[str, set[str]] = {state: set(_ALL) - {state} for state in _ALL}
# 忙碌状态不被表情打断（窗口层还会再挡一层）
ALLOWED[THINK] -= set(EXPRESSIONS)
ALLOWED[TALK] -= set(EXPRESSIONS)


class StateMachine:
    def __init__(self, initial: str = IDLE) -> None:
        self._state = initial

    @property
    def state(self) -> str:
        return self._state

    def can(self, target: str) -> bool:
        if target == self._state:
            return False
        return target in ALLOWED.get(self._state, set())

    def set(self, target: str) -> bool:
        """切换状态，成功返回 True。非法转移静默拒绝。"""
        if not self.can(target):
            return False
        self._state = target
        return True

    def force(self, target: str) -> None:
        self._state = target

    @property
    def action(self) -> str:
        return ACTION_OF.get(self._state, "idle")

    def is_busy(self) -> bool:
        """正在思考 / 说话时不该自己跑。"""
        return self._state in (THINK, TALK)
