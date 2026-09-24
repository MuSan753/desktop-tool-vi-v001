"""降级路由：大脑之间的调度。

顺序是「主在线模型 → 离线兜底」，
任何一步在吐第一个字之前就出错，立刻交给下一个，不让用户干等。
"""
from __future__ import annotations

from typing import Iterator

from app.settings import Settings

from .base import LLMProvider
from .openai_compat import OpenAICompatProvider
from .rule import RuleProvider


class Router:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.last_provider: str = ""
        self.last_error: str = ""

    def _hint(self) -> str:
        if not self.settings.api_key:
            return "先试着放空一会儿？或者去托盘菜单配个 API Key，我就能真聊了"
        return "网络好像不通，我先用自己的小脑袋答了"

    def providers(self) -> list[LLMProvider]:
        return [
            OpenAICompatProvider(self.settings),
            RuleProvider(self._hint()),
        ]

    def chat(self, messages: list[dict[str, str]]) -> Iterator[str]:
        providers = self.providers()
        self.last_error = ""

        for index, provider in enumerate(providers):
            last = index == len(providers) - 1
            if not provider.available():
                if last:
                    break
                continue
            got_token = False
            try:
                for chunk in provider.stream(messages):
                    got_token = True
                    self.last_provider = provider.label
                    yield chunk
                if got_token:
                    return
            except Exception as exc:  # 换下一个大脑
                self.last_error = str(exc) or exc.__class__.__name__
                if got_token:
                    # 已经说了半句就不再重来了，避免重复回答
                    return
                continue

        # 走到这儿说明在线模型全废了，兜底强制接管
        fallback = RuleProvider(self._hint())
        self.last_provider = fallback.label
        yield from fallback.stream(messages)
