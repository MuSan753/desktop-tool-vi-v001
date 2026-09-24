"""打包成 exe。

    python scripts/build_exe.py

做的事：
1. 把 assets/tray.png 转成 Windows 要的 .ico（PyInstaller 不认 png 图标）
2. 调 PyInstaller 打成单文件、无控制台的 exe
产物在 dist/小桌宠.exe
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
NAME = "小桌宠"


def make_ico() -> Path:
    ico = ASSETS / "tray.ico"
    img = Image.open(ASSETS / "tray.png").convert("RGBA")
    img.save(
        ico,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"图标 -> {ico}")
    return ico


def main() -> None:
    ico = make_ico()
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noconsole",
        f"--name={NAME}",
        f"--icon={ico}",
        "--add-data",
        f"{ASSETS}{os.pathsep}assets",
        "main.py",
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)
    print(f"\n完成：{ROOT / 'dist' / (NAME + '.exe')}")


if __name__ == "__main__":
    main()
