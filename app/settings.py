"""用户配置读写。

配置落在数据目录的 settings.json（打包后是 %APPDATA%\\MiniCat），
缺失的键自动用默认值补齐，所以升级加字段不怕旧文件。
敏感信息（API Key）支持用环境变量 MINICAT_API_KEY / OPENAI_API_KEY 覆盖。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .paths import settings_path

# 常见 OpenAI 协议兼容服务，选一个就自动填好地址和模型
PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-7B-Instruct",
    },
    "custom": {"base_url": "", "model": ""},
}

DEFAULTS: dict[str, Any] = {
    "pet": {
        "scale": 1.0,
        "walk": True,
        "topmost": True,
    },
    "brain": {
        "provider": "deepseek",
        "api_key": "",
        "base_url": PRESETS["deepseek"]["base_url"],
        "model": PRESETS["deepseek"]["model"],
        "temperature": 0.85,
        "max_tokens": 600,
        "timeout": 60,
    },
    "chat": {
        "persona": "傲娇猫娘",
        "history_turns": 16,   # 上下文保留多少条最新消息
        "summary_tokens": 3000,  # 超过这个估算 token 量就压缩旧对话
    },
    "mood": {
        "enabled": True,
    },
}


def _merge(base: dict, incoming: dict) -> dict:
    out = dict(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


class Settings:
    def __init__(self) -> None:
        self._path: Path = settings_path()
        self._data: dict[str, Any] = json.loads(json.dumps(DEFAULTS))
        self.load()

    def load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._data = _merge(DEFAULTS, raw)
            except Exception:
                # 配置文件坏了就退回默认值，别让程序起不来
                self._data = json.loads(json.dumps(DEFAULTS))

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, section: str, key: str, default: Any = None) -> Any:
        value = self._data.get(section, {}).get(key, None)
        if value is None:
            value = DEFAULTS.get(section, {}).get(key, default)
        return value

    def set(self, section: str, key: str, value: Any, autosave: bool = True) -> None:
        self._data.setdefault(section, {})[key] = value
        if autosave:
            self.save()

    @property
    def path(self) -> Path:
        return self._path

    # ---- 便捷属性 ----
    @property
    def api_key(self) -> str:
        env = os.environ.get("MINICAT_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        return (self.get("brain", "api_key") or env).strip()

    def apply_preset(self, provider: str) -> None:
        """切换服务商时自动套用它的地址和默认模型。"""
        preset = PRESETS.get(provider)
        if not preset:
            return
        self.set("brain", "provider", provider, autosave=False)
        self.set("brain", "base_url", preset["base_url"], autosave=False)
        self.set("brain", "model", preset["model"], autosave=False)
        self.save()

    def brain_config(self) -> dict[str, Any]:
        return dict(self._data.get("brain", {}))
