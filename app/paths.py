"""运行时路径。

打包后程序根目录是临时的 _MEIPASS，数据不能写那里；
所以素材走打包目录，用户数据（配置 / 数据库 / 记忆）走独立的数据目录。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICON = ASSETS / "tray.png"
ICO = ASSETS / "tray.ico"

FROZEN = bool(getattr(sys, "frozen", False))

# 素材目录：开发时是仓库里的 assets，打包后 PyInstaller 会把 assets 解到 sys._MEIPASS
if FROZEN:
    ASSETS = Path(sys._MEIPASS) / "assets"  # type: ignore[attr-defined]
    ICON = ASSETS / "tray.png"
    ICO = ASSETS / "tray.ico"
    ROOT = Path(sys.executable).resolve().parent


def data_dir() -> Path:
    """用户数据目录。可用环境变量 MINICAT_HOME 覆盖。"""
    override = os.environ.get("MINICAT_HOME")
    if override:
        base = Path(override)
    elif FROZEN:
        appdata = os.environ.get("APPDATA") or str(Path.home())
        base = Path(appdata) / "MiniCat"
    else:
        base = ROOT / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    return data_dir() / "chat.sqlite3"


def settings_path() -> Path:
    return data_dir() / "settings.json"


def mood_path() -> Path:
    return data_dir() / "mood.json"
