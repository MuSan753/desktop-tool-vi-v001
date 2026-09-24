"""全局可调参数。改这里就能调手感，不用动逻辑代码。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICON = ASSETS / "tray.png"

# 动画
FRAME_MS = 130          # 每一帧停留时长（毫秒），越小越快
WALK_TICK_MS = 40       # 游走时位置刷新间隔
WALK_SPEED = 2          # 每次刷新移动的像素

# 行为节奏
IDLE_MIN_MS = 2500      # 发呆最短时长
IDLE_MAX_MS = 6000      # 发呆最长时长
WALK_MIN_MS = 900       # 一次游走最短时长
WALK_MAX_MS = 2600      # 一次游走最长时长

# 气泡
BUBBLE_MS = 2800        # 气泡停留时长
BUBBLE_MAX_WIDTH = 220

# 台词（点一下随机说一句）
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

# 动作名 → assets 下的目录名，按数字顺序播放
ACTIONS = ("idle", "walk", "click")
