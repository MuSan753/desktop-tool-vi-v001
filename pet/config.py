"""全局可调参数。改这里就能调手感，不用动逻辑代码。"""
from __future__ import annotations

from app.paths import ASSETS, ICON

# 动画
# 每个动作的帧间隔（毫秒），越小越快
FRAME_MS: dict[str, int] = {
    "idle": 150,
    "walk": 110,
    "click": 85,
    "think": 240,
    "sit": 420,
    "sleep": 520,
}

# 游走
WALK_TICK_MS = 40       # 位置刷新间隔
WALK_SPEED = 2          # 每次刷新移动的像素

# 行为节奏
IDLE_MIN_MS = 2500      # 发呆最短时长
IDLE_MAX_MS = 6000      # 发呆最长时长
WALK_MIN_MS = 900       # 一次游走最短时长
WALK_MAX_MS = 2600      # 一次游走最长时长
SELFTALK_MIN_MS = 45000  # 放置时自言自语的最短间隔
SELFTALK_MAX_MS = 120000

# 气泡
BUBBLE_MS = 3600        # 气泡停留时长
BUBBLE_MAX_WIDTH = 240
TYPE_MS = 30            # 打字机每个字的间隔

# 缩放
SCALE_MIN = 0.6
SCALE_MAX = 2.4
SCALE_STEP = 0.1

# 动作名 → assets 下的目录名，缺素材会自动回落到 idle
ACTIONS = (
    "idle", "walk", "click", "think", "sit", "sleep",
    "happy", "angry", "sad", "surprised", "shy", "curious",
)

# 离线兜底台词（v1 遗留，作为最后的素材缺省时的保底）
LINES = [
    "你又来啦 (๑>ᴗ<๑)",
    "摸摸我呀～",
    "今天写代码了吗？",
    "我在这儿陪你呢",
    "要不要休息一会儿？",
    "喵？",
    "别盯屏幕太久哦",
    "你敲键盘的声音真好听",
]

__all__ = ["ASSETS", "ICON", "ACTIONS", "FRAME_MS", "LINES"]
