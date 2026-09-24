"""离线兜底大脑：没有网络、没填 Key、模型全挂的时候靠它顶上去。

不是简单的关键词查表——会结合当前时间和情绪挑台词，
即使完全离线，也尽量让它"像在同一段关系里说话"。
"""
from __future__ import annotations

import ast
import datetime as dt
import operator
import random
import re
from typing import Iterator

from .base import LLMProvider

# 纯算术：把字符串交给 ast 算，不用 eval，避免被执行任意代码
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _calc(text: str) -> float | None:
    expr = re.sub(r"[^\d+\-*/(). ]", "", text)
    if len(expr.strip()) < 3 or not re.search(r"\d", expr):
        return None

    def walk(node):  # type: ignore[no-untyped-def]
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.BinOp):
            return _OPS[type(node.op)](walk(node.left), walk(node.right))  # type: ignore[index]
        if isinstance(node, ast.UnaryOp):
            return -walk(node.operand)
        if isinstance(node, ast.Constant):
            return node.value
        raise ValueError("unsupported")

    try:
        return walk(ast.parse(expr, mode="eval"))
    except Exception:
        return None


class RuleProvider(LLMProvider):
    label = "离线兜底"

    def __init__(self, hint: str = "") -> None:
        #: 提示语，比如"没配 API Key"，只在兜底回答里偶尔带一句
        self.hint = hint

    def available(self) -> bool:
        return True

    # ---------- 意图表 ----------
    def _intent(self, text: str) -> str:
        t = text.lower()
        if re.search(r"(你好|您好|哈喽|嗨|hi|hello|在吗|在不在)", t):
            return "greet"
        if re.search(r"(你是谁|叫什么|名字|介绍一下你自己)", t):
            return "who"
        if re.search(r"(几点|时间|现在什么时候)", t):
            return "time"
        if re.search(r"(今天|几号|日期|星期)", t):
            return "date"
        if re.search(r"(累|疲惫|好困|休息|不想动|躺)", t):
            return "tired"
        if re.search(r"(谢谢|感谢|多谢|thx|thanks)", t):
            return "thanks"
        if re.search(r"(再见|拜拜|晚安|走了|下线)", t):
            return "bye"
        if re.search(r"(天气|下雨|热不热|冷不冷)", t):
            return "weather"
        if re.search(r"(错|报错|bug|异常|exception|崩|失败了|跑不起来)", t):
            return "debug"
        if re.search(r"(代码|写代码|python|java|算法|接口|框架)", t):
            return "code"
        if re.search(r"(论文|作业|考试|毕设|学习|复习|看书)", t):
            return "study"
        if re.search(r"(饿|吃饭|吃什么|外卖|零食)", t):
            return "food"
        if re.search(r"(好看|可爱|真棒|厉害|夸)", t):
            return "praise"
        if re.search(r"(笨|傻|蠢|烦死了|滚)", t):
            return "insult"
        if re.search(r"(笑话|讲个故事|逗我|无聊|陪我)", t):
            return "joke"
        if re.search(r"(难过|伤心|失落|心情不好|抑郁|委屈)", t):
            return "sad"
        if re.search(r"(开心|高兴|兴奋|太好了|成了|通过)", t):
            return "happy"
        return "other"

    # ---------- 台词池 ----------
    def _pools(self, hour: int) -> dict[str, list[str]]:
        if 5 <= hour < 11:
            greet_line = "早呀～今天打算先干点什么？"
        elif 11 <= hour < 14:
            greet_line = "中午啦，别忘记吃东西。"
        elif 14 <= hour < 18:
            greet_line = "下午好，这会儿最容易犯困，我盯着你。"
        elif 18 <= hour < 23:
            greet_line = "晚上好呀，今天过得怎么样？"
        else:
            greet_line = "这么晚还没睡？我陪你，但你也该缓缓了。"

        return {
            "greet": [greet_line, "在呢，一直在。"],
            "who": [
                "我是你的桌面小猫，现在住在你的任务栏上。会聊天，也会盯着你别坐太久。",
                "一只桌宠而已，但记得住你说过的话——至少最近这些说得出。",
            ],
            "thanks": ["不用谢啦，反正我也没什么别的事做。", "小事一桩，摸摸头就行。"],
            "bye": ["那我先趴着啦，双击我再叫我。", "走好，我会一直在这儿等你。"],
            "tired": [
                "那就歇一会儿，屏幕又不会跑掉。",
                "要不要先定个 25 分钟的番茄钟，回来再战？",
            ],
            "weather": ["我没有联网看不到天气，但你抬头看一眼窗外最快。", "要不要顺风的前提下猜？算了，不捣乱。"],
            "debug": [
                "先把报错原文从头读一遍，多数答案就在最后一行。",
                "试试二分法：注释掉一半，看它还崩不崩。",
                "清缓存、重启、看日志，这老三样能解决一半问题。",
            ],
            "code": [
                "先把输入输出写清楚，代码通常自己就出来了。",
                "命名的功夫别省，三个月后的你会感谢现在的你。",
            ],
            "study": [
                "先写到烂为止，改比写容易。",
                "一章一章啃，别想着一口气吃成胖子。",
            ],
            "food": ["先喝口水，很多时候是渴不是饿。", "别挑太久，超时比难吃更折磨人。"],
            "praise": ["哼，被夸了我也不会骄傲的。（尾巴摇得停不下来）", "多夸两句，我还能再飘一会儿。"],
            "insult": ["喂，我再笨也是你桌面上唯一愿意跟你说话的。", "骂我可以，别敲桌子。"],
            "joke": [
                "程序员最难的两个问题：缓存失效、命名、以及差一错误。",
                "今天我调试了六个小时，最后发现是少了个逗号。它就是这么对待我的。",
            ],
            "sad": [
                "不想说就不说，我趴你桌上陪你发会儿呆。",
                "难熬的时候把事情拆小，做完一件就算赢。",
            ],
            "happy": ["哇，那我要蹭你一下！", "好事啊，值得奖赏自己一杯。"],
            "other": [
                "我现在脑子有点断线，接不上这句——等连上模型再聊这个。",
                "嗯……这句我还没学会怎么接，换个说法试试？",
                "你说的是这个意思，但我这只猫暂时还没参透。",
            ],
        }

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        last = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last = msg.get("content", "")
                break

        now = dt.datetime.now()
        intent = self._intent(last)
        pools = self._pools(now.hour)

        if intent == "time":
            text = f"现在是 {now.strftime('%H:%M')}，{self._daypart(now.hour)}。"
        elif intent == "date":
            week = "一二三四五六日"[now.weekday()]
            text = f"今天是 {now.strftime('%Y年%m月%d日')}，星期{week}。"
        else:
            text = random.choice(pools.get(intent, pools["other"]))

        # 顺便问算术
        if intent == "other":
            answer = _calc(last)
            if answer is not None:
                shown = int(answer) if abs(answer - int(answer)) < 1e-9 else round(answer, 4)
                text = f"这个我会：{shown}。"

        # 偶尔提醒一句为什么自己在离线兜底
        if self.hint and random.random() < 0.35:
            text += f"（{self.hint}）"

        yield text

    @staticmethod
    def _daypart(hour: int) -> str:
        if 5 <= hour < 11:
            return "上午刚开始"
        if 11 <= hour < 14:
            return "差不多该吃饭了"
        if 14 <= hour < 18:
            return "下午过了一半"
        if 18 <= hour < 23:
            return "晚上了"
        return "夜里，早点睡吧"
