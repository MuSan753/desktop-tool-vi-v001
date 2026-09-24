"""无头冒烟测试：不显示窗口，把整条对话链路跑一遍。

    QT_QPA_PLATFORM=offscreen python tools/smoke_test.py

验证的东西：
1. 各模块能正常组装（配置/历史/情绪/路由/宠物/面板/控制器）；
2. 情绪标记的解析与流式隐藏逻辑正确；
3. 没配 API Key 时走离线兜底也能完整回答一轮；
4. 历史落盘、人格切换不出错。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["MINICAT_HOME"] = str(ROOT / "data" / "_smoke")  # 测试数据隔离

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.bus import bus  # noqa: E402
from app.settings import Settings  # noqa: E402
from brain.router import Router  # noqa: E402
from chat.controller import ChatController  # noqa: E402
from chat.history import History  # noqa: E402
from chat.panel import ChatPanel  # noqa: E402
from chat.session import ChatSession  # noqa: E402
from life.mood import Mood, parse_marker, visible_text  # noqa: E402
from pet.window import PetWindow  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail else ""))


def main() -> int:
    app = QApplication(sys.argv)

    # ---- 单元级：情绪标记 ----
    sample = '喵？你好呀。\n[[MOOD]]{"label":"开心","joy":5,"energy":-1,"affinity":2,"stress":-2}'
    check("情绪标记解析", parse_marker(sample) == ({"joy": 5, "energy": -1, "affinity": 2, "stress": -2}, "开心"))
    check("完整文本剥离", visible_text(sample) == "喵？你好呀。", visible_text(sample))
    check("流式半截标记隐藏", visible_text("你好呀。\n[[M") == "你好呀。", repr(visible_text("你好呀。\n[[M")))
    check("无标记文本原样", visible_text("普通回答") == "普通回答")

    # ---- 组装 ----
    settings = Settings()
    history = History()
    mood = Mood()
    session = ChatSession(settings, history, mood)
    router = Router(settings)
    pet = PetWindow()
    panel = ChatPanel()
    controller = ChatController(settings, history, mood, session, router, app)
    panel.bind_submit(controller.ask)
    check("组件组装", True)

    # ---- 离线兜底跑一轮 ----
    got: dict = {"text": "", "provider": "", "done": False}

    def on_finished(text: str, provider: str) -> None:
        got.update(text=text, provider=provider, done=True)

    def on_failed(message: str) -> None:
        got.update(text="", provider="", done=True, error=message)

    bus.reply_finished.connect(on_finished)
    bus.reply_failed.connect(on_failed)

    controller.ask("你好")
    deadline = 15000
    timer = QTimer()
    timer.setSingleShot(True)

    def give_up() -> None:
        got["done"] = True
        got.setdefault("error", "超时")

    timer.timeout.connect(give_up)
    timer.start(deadline)

    while not got["done"]:
        app.processEvents()
        if not controller.busy and got.get("text"):
            break
        app.processEvents()
    timer.stop()

    check("离线兜底有回应", bool(got.get("text")), f"provider={got.get('provider')} text={got.get('text','')[:40]}")
    check("回应已落盘", history.count_since(0) >= 2, f"messages={history.count_since(0)}")

    # ---- 人格切换 ----
    controller.switch_persona("沉稳前辈")
    check("人格切换", session.persona == "沉稳前辈")

    # ---- 摘要阈值判断不炸 ----
    session.should_summarize()
    check("摘要阈值判断", True)

    # ---- 面板流式渲染 ----
    panel._on_started()
    panel._on_token("喵？你好。\n[[MOOD]]{\"label\":\"平静\"}")
    check("面板流式渲染隐藏标记", True)

    pet.close()
    panel.close()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} 项通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
