"""对话大脑的可插拔接口。

所有模型提供方统一一个形状：给 messages，吐一段段文本。
router 不关心底层是 OpenAI、Ollama 还是纯规则。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator


class LLMProvider(ABC):
    """一个"大脑"。"""

    #: 显示用名字，回答结束后会标在面板上
    label: str = "unknown"

    def available(self) -> bool:
        """缺 key、缺依赖、地址没填就该返回 False，让 router 往下走。"""
        return True

    @abstractmethod
    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        """流式返回文本片段。抛异常由 router 负责降级。"""
        raise NotImplementedError


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数。

    中文大约 1 字 1 token，英文大约 4 字符 1 token。
    够用来判断"要不要压缩上下文"了，不需要精确。
    """
    if not text:
        return 0
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    others = len(text) - ascii_chars
    return ascii_chars // 4 + others
