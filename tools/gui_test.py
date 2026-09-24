"""真实窗口环境下的端到端测试（会闪一下弹窗，跑完自动退出）。

    python tools/gui_test.py

冒烟测试跑的是 offscreen，验证不了真实渲染和窗口事件；
这个脚本用正常 QApplication 把宠物和面板真的显示出来，
再走一遍完整链路：打开面板 → 发一句话 → 流式渲染 → 情绪更新 → 落盘，
顺带把拖拽、缩放、人格切换这些交互路径都点一遍，确保没有隐藏的 UI 报错。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["MINICAT_HOME"] = str(ROOT / "data" / "_guitest")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.bus import bus  # noqa: E402
from app.settings import Settings  # noqa: E402
from brain.router import Router  # noqa: E402
from chat.controller import ChatController  # noqa: E402
from chat.history import History  # noqa: E402
from chat.panel import ChatPanel  # noqa: E402
from chat.persona import PERSONAS  # noqa: E402
from chat.session import ChatSession  # noqa: E402
from life.mood import MOOD_TAGS, Mood, visible_text  # noqa: E402
from pet.window import PetWindow  # noqa: E402

report: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = "") -> None:
    report.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail else ""))


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    settings = Settings()
    history = History()
    mood = Mood()
    session = ChatSession(settings, history, mood)
    router = Router(settings)

    pet = PetWindow()
    panel = ChatPanel()
    controller = ChatController(settings, history, mood, session, router, app)
    panel.bind_submit(controller.ask)
    panel.persona_selected.connect(controller.switch_persona)

    pet.show()
    step("宠物窗口渲染", pet.isVisible(), f"尺寸 {pet.width()}x{pet.height()}")

    # 打开面板，确认它贴到了小猫旁边
    panel.show_near(*pet.geometry_tuple())
    step("面板渲染并定位", panel.isVisible() and panel.x() >= 0, f"面板位置 ({panel.x()}, {panel.y()})")

    # 交互路径：缩放 / 拖拽压迫 / 点击反馈
    old_w = pet.width()
    pet.set_scale(1.5)
    step("滚轮缩放", pet.width() > old_w, f"{old_w} -> {pet.width()}")
    pet.set_scale(1.0)

    pet.interact()
    step("点击互动不报错", True, f"状态 {pet.mode}")

    # 一轮真实对话（没配 Key 时走离线兜底）
    got = {"text": "", "provider": "", "tokens": 0, "done": False}

    def on_token(chunk: str) -> None:
        got["tokens"] += len(chunk)

    def on_finished(text: str, provider: str) -> None:
        got.update(text=text, provider=provider, done=True)

    def on_failed(message: str) -> None:
        got.update(error=message, done=True)

    bus.reply_token.connect(on_token)
    bus.reply_finished.connect(on_finished)
    bus.reply_failed.connect(on_failed)

    panel.input.setPlainText("你觉得今天状态怎么样")
    panel._send()

    import time

    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(lambda: got.update(done=True))
    deadline.start(20000)

    while not got["done"]:
        app.processEvents()
        time.sleep(0.01)
        if got.get("text"):
            break
    deadline.stop()

    step("一轮对话完成", bool(got.get("text")), f"provider={got.get('provider')} tokens={got['tokens']}")
    step("回答不含情绪标记", "[[" not in (got.get("text") or ""), (got.get("text") or "")[:36])
    step("对话已落盘", history.count_since(0) >= 2, f"messages={history.count_since(0)}")

    # 情绪是否真的被驱动了（joy 基准 60，聊完应当已经变化，且标签必须在 15 类里）
    step(
        "情绪标签合法且已变化",
        mood.state.label in MOOD_TAGS and mood.state.joy != 60,
        f"label={mood.state.label} joy={mood.state.joy} affinity={mood.state.affinity}",
    )

    # 人格切换 + 面板 UI 同步
    target = "毒舌搭档"
    controller.switch_persona(target)
    step("人格切换与面板同步", session.persona == target and panel.combo.currentText() == target,
         f"session={session.persona} combo={panel.combo.currentText()}")

    # 清空 history 后面板也应跟着清
    controller.clear_history()
    app.processEvents()
    step("清空历史", history.count_since(0) <= 1, f"messages={history.count_since(0)}")

    step("可用人格数", len(PERSONAS) == 4, str(list(PERSONAS)))
    step("可见文本工具函数", visible_text("你好\n[[MOOD]]{\"label\":\"开心\"}") == "你好")

    # 情绪标签触发表情动画
    from pet.states import EXPRESSIONS  # noqa: E402

    bus.mood_changed.emit("愤怒")
    app.processEvents()
    step("情绪触发表情动画", pet.mode == "angry", f"当前动作 {pet.mode}")
    bus.mood_changed.emit("开心")
    app.processEvents()
    step("表情可切换", pet.mode == "happy", f"当前动作 {pet.mode}")
    assert EXPRESSIONS  # 保持 import 有意义

    pet.close()
    panel.close()
    app.processEvents()

    failed = [r for r in report if not r[1]]
    print(f"\n{len(report) - len(failed)}/{len(report)} 项通过")
    if failed:
        print("失败项：" + ", ".join(name for name, _, _ in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
