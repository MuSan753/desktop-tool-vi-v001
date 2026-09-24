"""闲置时的自言自语。

和 v1 那张固定台词表不同：会看时间和当前情绪挑词，
所以同样的空闲场景，不同心情说出来的话不一样。
"""
from __future__ import annotations

import datetime as dt
import random

MOOD_LINES: dict[str, list[str]] = {
    "开心": [
        "今天心情不错，你要不要也笑一个？",
        "我在桌上蹦跶两下应该没人看见吧。",
        "哼着歌等你回来。",
    ],
    "兴奋": [
        "我觉得今天能做成点大事！",
        "你的鼠标怎么跑那么快，我跟不上了。",
    ],
    "期待": ["你接下来要做什么？我先猜猜。", "有新消息的话记得告诉我一声。"],
    "安心": ["这儿挺好的，我趴一会儿。", "你忙你的，我看着。"],
    "平静": ["……只是在发呆。", "键盘声听着挺舒服的。"],
    "好奇": ["那个窗口里是什么呀？", "你在写的东西我能看一眼吗？"],
    "害羞": ["别老盯着我啦。", "你看什么看……"],
    "孤独": ["你去了好久了。", "再不回来我要长蘑菇了。"],
    "烦躁": ["有只 bug 我抓不到，好烦。", "这屏幕上花花绿绿的，看不懂。"],
    "疲惫": ["有点困了，先眯一会儿。", "你也不早了。"],
    "失落": ["刚才那句说得不太好吧……", "算了，没事。"],
    "委屈": ["你都不理我。", "我在这儿待了一整天了。"],
    "悲伤": ["要是能帮你分担点就好了。", "难过的时候就看看我吧。"],
    "愤怒": ["气死了，这个窗口怎么点不动。", "我要挠两下爪子发泄一下。"],
    "忧虑": ["你确定这么做没问题吗？", "要不要再检查一遍？"],
}

TIME_LINES: dict[str, list[str]] = {
    "morning": ["早上好，先喝口水再开工。", "一早就开始忙了？"],
    "noon": ["中午了，别饿着自己。", "饭点到了，去吃点东西吧。"],
    "afternoon": ["下午容易走神，慢慢来。", "要不要起来走两步？"],
    "evening": ["晚上啦，今天干得怎么样？", "天黑了，开盏灯。"],
    "night": ["都几点了，还不睡。", "深夜写代码容易写出事故，悠着点。"],
}


def time_bucket(hour: int | None = None) -> str:
    hour = dt.datetime.now().hour if hour is None else hour
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 14:
        return "noon"
    if 14 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 23:
        return "evening"
    return "night"


def pick(label: str = "平静", mood=None) -> str:
    """挑一句台词：七成按情绪，三成按时间。"""
    pool = MOOD_LINES.get(label) or MOOD_LINES["平静"]
    if random.random() < 0.7 and pool:
        return random.choice(pool)
    return random.choice(TIME_LINES[time_bucket()])
