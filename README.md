# desktop-tool

一只跑在桌面上的小桌宠。Python + PySide6，无边框透明置顶窗口，能拖、能自己溜达、点了会说话。

## 跑起来

```bash
pip install -r requirements.txt
python main.py
```

第一次跑如果提示缺素材，先生成占位角色：

```bash
python tools/make_placeholder_assets.py
```

桌宠没有标题栏，退出请右键托盘图标选「退出」。

## 能干什么

- 透明置顶，不挡任务栏
- 鼠标拖动换位置
- 点一下：播放开心动效 + 随机说句话
- 没人理它的时候会自己左右溜达，撞到屏幕边缘会掉头
- 托盘右键菜单：显示/隐藏、说句话、随机游走开关、窗口置顶开关、退出

## 目录

```
main.py                        入口
pet/
├── config.py                  所有可调参数（帧速、步长、节奏、台词）
├── animation.py               序列帧加载
├── window.py                  主窗口：动画 / 拖拽 / 游走 / 交互
├── bubble.py                  气泡对话
└── tray.py                    托盘图标与菜单
assets/
├── idle/ walk/ click/         三个动作的 PNG 序列帧
└── tray.png                   托盘图标
tools/make_placeholder_assets.py   占位素材生成器
scripts/build_exe.py               打包脚本（转 ico + 调 PyInstaller）
```

## 换成自己的角色

`assets/<动作>/` 下的 PNG 按文件名数字顺序播放，透明通道会保留。
直接把图片丢进去、文件名排好序就行，不用改代码。想加新动作，把目录名写进 `pet/config.py` 的 `ACTIONS`。

## 打包成 exe

```bash
pip install pyinstaller
python scripts/build_exe.py
```

脚本会自动把 `tray.png` 转成 Windows 要的 `.ico`，再打成单文件、无控制台的 exe，产物在 `dist/小桌宠.exe`（约 44 MB）。双击即可运行，不依赖 Python 环境。

`dist/`、`build/`、`*.spec` 都在 `.gitignore` 里，exe 不进版本库。
