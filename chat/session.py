"""一轮对话的上下文管理。

借鉴了 yoji 的 summarization 中间件：满足「消息条数」或「预估 token」任一阈值就压缩。
区别在于它按 5 条触发（那边有 checkpointer 兜着），我们这边上下文窗口更薄，
放宽到 20 条 + 3000 token 才压，避免频繁触发摘要把对话搞碎。
"""
from __future__ import annotations

import datetime as dt

from app.settings import Settings
from brain.base import estimate_tokens
from life.mood import Mood

from .history import History
from .persona import DEFAULT_PERSONA, build_system_prompt

SUMMARY_PROMPT = (
    "把下面这段对话压缩成一段中文摘要，要求：\n"
    "1. 只保留会影响后续对话的事实、偏好、正在进行的事情和未完成的约定；\n"
    "2. 用第三人称写（用户、小猫），不要保留原文句子；\n"
    "3. 200 字以内，一段话，不要分点。\n\n"
    "对话内容：\n"
)


class ChatSession:
    def __init__(self, settings: Settings, history: History, mood: Mood) -> None:
        self.settings = settings
        self.history = history
        self.mood = mood

    @property
    def persona(self) -> str:
        return self.settings.get("chat", "persona", DEFAULT_PERSONA) or DEFAULT_PERSONA

    def set_persona(self, persona: str) -> None:
        self.settings.set("chat", "persona", persona)

    # ---------- 上下文构造 ----------
    def _time_context(self) -> str:
        now = dt.datetime.now()
        week = "一二三四五六日"[now.weekday()]
        return f"当前时间：{now.strftime('%Y-%m-%d %H:%M')} 星期{week}。"

    def build_messages(self) -> list[dict[str, str]]:
        """给模型的完整 messages。"""
        summary, upto = self.history.latest_summary()
        extra = self._time_context()
        if summary:
            extra += "\n更早对话的摘要：\n" + summary

        system = build_system_prompt(self.persona, self.mood.state.describe(), extra)

        turns = int(self.settings.get("chat", "history_turns", 16))
        rows = self.history.recent_since(upto, turns * 2)

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for row in rows:
            messages.append({"role": row["role"], "content": row["content"]})
        return messages

    # ---------- 摘要 ----------
    def should_summarize(self) -> bool:
        _, upto = self.history.latest_summary()
        count = self.history.count_since(upto)
        turns = int(self.settings.get("chat", "history_turns", 16))
        if count >= turns * 2:
            return True

        rows = self.history.recent_since(upto, count)
        total = sum(estimate_tokens(row["content"]) for row in rows)
        return total >= int(self.settings.get("chat", "summary_tokens", 3000))

    def summary_request(self) -> list[dict[str, str]]:
        """生成压缩请求用的 messages（走同一个大脑，不需要额外实现）。"""
        _, upto = self.history.latest_summary()
        count = self.history.count_since(upto)
        rows = self.history.recent_since(upto, count)
        body = "\n".join(f"{r['role']}: {r['content']}" for r in rows)
        return [
            {"role": "system", "content": "你是一个对话压缩助手。"},
            {"role": "user", "content": SUMMARY_PROMPT + body},
        ]

    def commit_summary(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self.history.replace_summary(text, self.history.max_id())
