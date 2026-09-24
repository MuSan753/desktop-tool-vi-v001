# MiniCat

一只跑在桌面上的小猫，而且**能聊天**。

Python + PySide6。无边框透明置顶窗口，能拖、能自己溜达、会打字聊天、有情绪、记得住你说过的话。

## 跑起来

```bash
pip install -r requirements.txt
python main.py
```

第一次跑如果提示缺素材：

```bash
python tools/make_placeholder_assets.py
```

退出：右键托盘图标 → 退出。

## 能干什么

**对话**
- 双击小猫（或点托盘）打开聊天面板，Enter 发送、Shift+Enter 换行
- 流式输出：答案一个字一个字冒出来，等待时小猫进入"思考"状态
- 4 套人格可切：傲娇猫娘 / 毒舌搭档 / 沉稳前辈 / 安静陪伴，语气完全不同
- 多轮上下文 + 自动摘要压缩，聊得再久也不会爆 token，重启后历史还在

**情绪**
- 回答末尾附带的情绪标签会实时反映到气泡配色和小猫状态上
- 四维情绪（开心 / 精力 / 亲密度 / 压力），摸它会开心，晾它会闹脾气

**桌面行为**
- 无人理时自己左右溜达，撞屏幕边缘会掉头；放置久了会按当前心情自言自语
- 点一下：开心动效 + 按心情挑的台词；滚轮缩放体型；拖拽换位置
- 托盘菜单：打开对话、人格切换、体型调节、清空记忆、游走/置顶开关

**离线兜底**
- 没网、没配 Key、模型全挂时自动降级到内置规则引擎，永远有回应
- 兜底回答会看时间和意图（问时间、问日期、算个加减乘除都行）

## 配置大脑

配置文件在数据目录 `settings.json`（开发时在 `data/`，打包后在 `%APPDATA%\MiniCat`）：

```json
{
  "brain": {
    "provider": "deepseek",
    "api_key": "sk-...",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat"
  }
}
```

任何 OpenAI 协议兼容的服务都能接（DeepSeek / 通义 / 智谱 / Kimi / SiliconFlow / OpenAI 本尊），改 `base_url` 和 `model` 就行。
API Key 也可以用环境变量 `MINICAT_API_KEY` 提供。不配置的话就用离线兜底模式。

## 目录

```
main.py                        入口
app/
├── paths.py                   路径（开发 / 打包两种环境都兼容）
├── settings.py                配置读写 + 服务商预设
└── bus.py                     事件总线（模块间不互相 import）
pet/
├── window.py                  主窗口：动画 / 拖拽 / 游走 / 流式气泡
├── states.py                  状态机：idle / walk / drag / click / think / talk / sleep
├── animation.py               序列帧加载（缺素材自动回落）
├── bubble.py                  气泡：打字机 + 情绪配色
├── tray.py                    托盘菜单
└── config.py                  手感参数
chat/
├── panel.py                   聊天面板（贴着小猫的浮层）
├── controller.py              对话编排：发问 → 流式 → 落盘 → 摘要
├── session.py                 上下文窗口 + 阈值触发压缩
├── history.py                 SQLite 持久化
└── persona.py                 人格模板
brain/
├── worker.py                  QThread：网络请求绝不上主线程
├── router.py                  降级路由：在线模型 → 离线兜底
├── openai_compat.py           OpenAI 协议适配
├── rule.py                    离线规则引擎
└── base.py                    Provider 抽象
life/
├── mood.py                    四维情绪 + 15 类情绪标签
└── idle_talks.py              按心情和时间段自言自语
assets/                        各动作的 PNG 序列帧
tools/
├── make_placeholder_assets.py 素材生成器
├── smoke_test.py              无头冒烟测试
└── build_exe.py               打包脚本（转 ico + 调 PyInstaller）
```

## 换成自己的角色

`assets/<动作>/` 下的 PNG 按文件名数字顺序播放，透明通道保留。
动作支持：`idle / walk / click / think / sit / sleep`——缺哪个自动回落到 idle，不会崩。

## 测试与打包

```bash
QT_QPA_PLATFORM=offscreen python tools/smoke_test.py   # 冒烟测试
python scripts/build_exe.py                            # 打包单文件 exe
```

打包脚本会自动把 `tray.png` 转成 Windows 要的 `.ico`，再打成单文件、无控制台的 exe，产物在 `dist/小桌宠.exe`。双击即可运行，不依赖 Python 环境。`dist/`、`build/`、`*.spec` 都在 `.gitignore` 里，exe 不进版本库。

## 设计说明

- 情绪系统与摘要机制借鉴了开源桌宠 [yoji](https://github.com/wangxijie001/yoji)（MIT）的思路，按桌宠规模做了简化
- 所有网络请求走 QThread，主线程只管渲染——这是桌宠能一边聊天一边蹦跶的前提
