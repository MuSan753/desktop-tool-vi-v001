"""情绪系统。

借鉴了开源桌宠 yoji（MIT）的思路：让模型在回答末尾附带一行结构化情绪状态，
UI 拿它来换动画和配色。那边是 8 种激素，这里砍到 4 维——
维度再多用户感知不到差别，只会让参数越来越难调。

四维：
  joy       开心程度
  energy    精力    （聊久了会掉）
  affinity  亲密度  （互动越多越高）
  stress    压力    （长时间放置会涨）
"""
from __future__ import annotations

import json
import random
import re
import time
from dataclasses import asdict, dataclass, field

from app.paths import mood_path

# 15 个情绪标签，模型只能从里面挑
MOOD_TAGS = [
    "开心", "期待", "安心", "平静", "好奇", "害羞", "孤独",
    "烦躁", "疲惫", "失落", "委屈", "悲伤", "愤怒", "忧虑", "兴奋",
]

#: 情绪标签 → 表情动作（pet 层按这个触发对应动画）
LABEL_ACTION: dict[str, str] = {
    "开心": "happy", "兴奋": "happy",
    "期待": "curious", "好奇": "curious",
    "害羞": "shy",
    "烦躁": "angry", "愤怒": "angry",
    "悲伤": "sad", "失落": "sad", "委屈": "sad", "孤独": "sad", "忧虑": "sad",
    "疲惫": "sleep",
    "安心": "idle", "平静": "idle",
}

DIMS = ("joy", "energy", "affinity", "stress")

# 文案里的情绪标记：[[MOOD]]{"label":"开心","joy":5,...}
MARKER = "\n[[MOOD]]"
_FULL_KEY = "[[MOOD]]"
_FULL = re.compile(r"\[\[MOOD\]\]\s*(\{[^{}]*\})", re.S)


@dataclass
class MoodState:
    joy: int = 60
    energy: int = 70
    affinity: int = 45
    stress: int = 20
    label: str = "平静"
    updated: float = field(default_factory=time.time)

    def clamp(self) -> None:
        for name in DIMS:
            value = getattr(self, name)
            setattr(self, name, max(0, min(100, int(value))))

    def apply_delta(self, delta: dict) -> None:
        for name in DIMS:
            if name in delta:
                try:
                    setattr(self, name, getattr(self, name) + int(delta[name]))
                except (TypeError, ValueError):
                    continue
        self.clamp()

    def decay(self, minutes: float) -> None:
        """长时间没人理它：精力回升，孤独感（压力）上涨，亲密度缓慢回落。"""
        step = max(0.0, minutes) / 10.0
        self.energy = min(100, self.energy + int(step * 3))
        self.stress = min(100, self.stress + int(step * 4))
        self.affinity = max(0, self.affinity - int(step * 2))
        self.joy = max(0, self.joy - int(step))
        self.clamp()

    def dominant(self) -> str:
        """四维直接推一个标签，模型没给标记时用它兜底。"""
        if self.stress >= 65:
            return "烦躁"
        if self.energy <= 25:
            return "疲惫"
        if self.affinity >= 75 and self.joy >= 65:
            return "开心"
        if self.joy >= 70:
            return "兴奋"
        return "平静"

    def describe(self) -> str:
        """塞进 system prompt 的当前状态描述。"""
        return (
            f"- 开心 joy: {self.joy}/100\n"
            f"- 精力 energy: {self.energy}/100\n"
            f"- 亲密度 affinity: {self.affinity}/100\n"
            f"- 压力 stress: {self.stress}/100\n"
            f"- 当前情绪标签: {self.label}"
        )


class Mood:
    """带持久化的情绪状态。"""

    def __init__(self) -> None:
        self.state = MoodState()
        self.load()

    # ---- 持久化 ----
    def load(self) -> None:
        path = mood_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {k: v for k, v in data.items() if k in asdict(self.state)}
            self.state = MoodState(**known)
        except Exception:
            self.state = MoodState()

    def save(self) -> None:
        try:
            mood_path().write_text(
                json.dumps(asdict(self.state), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ---- 行为 ----
    def touch(self) -> None:
        """被摸了一下：开心涨、压力掉、慢慢跟你熟起来。"""
        self.state.apply_delta({"joy": +4, "stress": -3, "affinity": +1})

    def after_reply(self, label: str | None = None) -> None:
        self.state.apply_delta({"energy": -1, "joy": +1})
        self.state.label = label or self.state.dominant()
        self.state.clamp()
        self.save()

    def if_idle_for(self) -> None:
        minutes = (time.time() - self.state.updated) / 60.0
        if minutes < 5:
            return
        self.state.decay(minutes)
        self.state.updated = time.time()
        self.state.label = self.state.dominant()
        self.save()


# ---------- 文本里的情绪标记处理 ----------

def visible_text(raw: str) -> str:
    """给用户看的部分：去掉情绪标记，流式过程中也别漏半个标记出来。"""
    if "[[" not in raw:
        return raw.rstrip()
    text = _FULL.sub("", raw)
    idx = text.rfind("[[")
    if idx != -1:
        tail = text[idx:].lstrip("\n")
        # 尾巴是 [[MOOD]] 的前缀（流式时标记可能只到了一半）
        if tail.startswith("[[MOOD]]") or _FULL_KEY.startswith(tail):
            text = text[:idx]
    return text.rstrip()


def parse_marker(raw: str) -> tuple[dict, str] | None:
    """从回答里解析情绪标记，返回 (数值变化, 标签)。"""
    match = _FULL.search(raw)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except Exception:
        return None

    delta = {}
    for key in DIMS:
        if key in data:
            try:
                delta[key] = int(data[key])
            except (TypeError, ValueError):
                continue
    label = str(data.get("label", "")).strip()
    if label and label not in MOOD_TAGS:
        # 模型偶尔自造词，贴一个最接近的
        label = _closest(label)
    return delta, label


def _closest(label: str) -> str:
    for tag in MOOD_TAGS:
        if tag in label:
            return tag
    return random.choice(MOOD_TAGS)


def parse_or_fallback(raw: str) -> dict:
    """拿不到标记时给一组默认值，别因为模型不守规矩就没了情绪变化。"""
    parsed = parse_marker(raw)
    if parsed:
        delta, label = parsed
        return {"delta": delta or {"joy": +1}, "label": label or "平静"}
    return {"delta": {"joy": +1, "affinity": +1}, "label": ""}
