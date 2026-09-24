"""OpenAI 协议的通用适配器。

DeepSeek / 通义 / 智谱 / Kimi / SiliconFlow 都走这套协议，
换服务商只需要改 base_url 和 model，代码一行不用动。
"""
from __future__ import annotations

from typing import Iterator

from app.settings import Settings

from .base import LLMProvider


class OpenAICompatProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.label = settings.get("brain", "provider", "custom") or "custom"

    def _config(self) -> dict:
        return self._settings.brain_config()

    def available(self) -> bool:
        cfg = self._config()
        return bool(self._settings.api_key and cfg.get("base_url") and cfg.get("model"))

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        try:
            from openai import OpenAI
        except ImportError as exc:  # 依赖没装，直接降级
            raise RuntimeError("未安装 openai 包：pip install openai") from exc

        cfg = self._config()
        client = OpenAI(
            api_key=self._settings.api_key,
            base_url=cfg.get("base_url"),
            timeout=float(cfg.get("timeout", 60)),
            max_retries=1,
        )
        response = client.chat.completions.create(
            model=cfg.get("model"),
            messages=messages,
            temperature=float(cfg.get("temperature", 0.85)),
            max_tokens=int(cfg.get("max_tokens", 600)),
            stream=True,
        )
        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                yield piece
