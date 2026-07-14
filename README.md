# 微信自动发送朋友圈

这是一个 macOS 微信自动化 GUI 工具，用于管理朋友圈发布、视频号转发朋友圈、删除朋友圈、模板截图、封面和头像识别配置。

## 功能 

- [x] GUI 管理文案、媒体路径、发送模式和定时设置
- [x] 发视频朋友圈
- [x] 支持视频号封面识别并转发到朋友圈
- [x] 支持删除朋友圈
- [x] 可替换模板截图
- [x] 可配置“不给谁看”隐私标签
- [x] 支持 PyInstaller 打包成 macOS `.app`

## 待完善功能

- [ ] 暂时还不能发图文

## 目录结构

```text
.
├── main.py
├── pyq_post.py
├── pyq_sph_post.py
├── del_pyq.py
├── requirements.txt
├── run.sh
├── app.icns
├── config.json
├── templates/
│   ├── profile_avatar.png
│   ├── target_video_cover.png
│   ├── pyq_btn.png
│   ├── sph_btn.png
│   ├── camera_icon.png
│   ├── check_pyq_btn.png
│   ├── publish_btn.png
│   ├── del_icon.png
│   ├── del_text.png
│   ├── sph_share_btn1.png
│   ├── sph_share_btn2.png
│   └── privacy/
│       ├── privacy_entry.png
│       ├── hide_from_option.png
│       ├── done_btn.png
│       ├── confirm_btn.png
│       └── tags/
│           └── .gitkeep
└── .github/workflows/build-macos-dmg.yml
```

## 模板说明

模板目录固定为：

```text
templates/
```

隐私权限模板固定为：

```text
templates/privacy/
templates/privacy/tags/
```

`templates/privacy/tags/` 下放需要勾选的标签截图，例如：

```text
01.png
02.png
03.png
```

注意：标签截图通常涉及账号隐私，仓库默认忽略 `templates/privacy/tags/*.png`，只保留 `.gitkeep` 目录占位。

完整模板说明见：

```text
templates/README.md
```

## 本地运行

建议使用 Homebrew Python，避免 pyenv Python 缺少 `_tkinter`。

```bash
cd 项目目录
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv_gui
source .venv_gui/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

也可以使用：

```bash
./run.sh
```

## 打包 macOS App

```bash
source .venv_gui/bin/activate

python -m PyInstaller \
  -y \
  --windowed \
  --name "微信自动发送朋友圈" \
  --icon app.icns \
  --add-data "pyq_post.py:." \
  --add-data "pyq_sph_post.py:." \
  --add-data "del_pyq.py:." \
  --hidden-import cv2 \
  --hidden-import PIL.ImageTk \
  main.py
```

生成位置：

```text
dist/微信自动发送朋友圈.app
```

发布时建议结构：

```text
微信自动发送朋友圈/
├── 微信自动发送朋友圈.app
├── templates/
└── config.json
```

## macOS 权限

首次运行需要在系统设置中给 `.app` 授权：

```text
系统设置 -> 隐私与安全性 -> 辅助功能
系统设置 -> 隐私与安全性 -> 屏幕录制
系统设置 -> 隐私与安全性 -> 自动化
```

如果 macOS 提示无法验证开发者，可以对发布目录执行：

```bash
xattr -cr "微信自动发送朋友圈"
```

## GitHub Actions 打包

仓库包含 `.github/workflows/build-macos-dmg.yml`。在 GitHub 页面手动运行 workflow 后，会生成 DMG artifact。

## 风险说明

本项目通过截图识别和模拟鼠标键盘操作微信客户端。微信界面变化、窗口大小、显示器缩放、权限设置、模板截图不匹配，都可能导致识别失败。请先使用测试账号验证。
