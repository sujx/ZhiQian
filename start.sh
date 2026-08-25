#!/usr/bin/env bash
# 知迁 — 为知笔记导出工具（macOS / Linux 启动脚本）
#
# 用法:
#   ./start.sh --help            CLI 帮助
#   ./start.sh --gui             GUI 模式
#   ./start.sh --find            CLI: 自动查找数据目录
#   ./start.sh --source local --input <数据目录> --output <输出目录>
#
# 环境: 优先 .venv / .gui-venv，否则使用系统 python3
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="python3"
if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -x ".gui-venv/bin/python" ]; then
    PYTHON=".gui-venv/bin/python"
fi

export PYTHONIOENCODING=utf-8

if [ "${1:-}" = "--gui" ]; then
    shift
    # GUI 模式: 检查 tkinter
    if ! "$PYTHON" -c "import tkinter" 2>/dev/null; then
        echo "[错误] 缺少 tkinter，请安装后重试:"
        echo "  macOS (Homebrew python):  brew install python-tk"
        echo "  Ubuntu/Debian:            sudo apt install python3-tk"
        echo "  或使用 python.org 官方版 Python（自带 tkinter）"
        exit 1
    fi
    exec "$PYTHON" -m exporter.gui "$@"
else
    exec "$PYTHON" -m exporter "$@"
fi
