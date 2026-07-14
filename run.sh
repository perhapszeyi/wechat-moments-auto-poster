#!/bin/bash
# 使用 Homebrew Python 启动 GUI，避开 Command Line Tools Python 的 Tk 崩溃问题。

cd "$(dirname "$0")"

PYTHON_BIN="/opt/homebrew/opt/python@3.11/bin/python3.11"
VENV_DIR=".venv_gui"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "未找到 Homebrew Python 3.11: $PYTHON_BIN"
    echo "请先安装：brew install python@3.11"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "首次运行，正在创建虚拟环境..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install -r requirements.txt -q
    echo "依赖安装完成"
else
    source "$VENV_DIR/bin/activate"
fi

# 验证 Tk 能正常初始化，否则 GUI 启动会崩溃。
python - <<'PY'
import tkinter as tk
root = tk.Tk()
root.withdraw()
root.destroy()
PY

# 启动 GUI
python test.py
