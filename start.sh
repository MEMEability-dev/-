#!/bin/bash
# A股选股平台 启动脚本

set -e

echo "================================"
echo "  A股选股平台 v1.2"
echo "================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Install dependencies if needed
if [ ! -f ".deps_installed" ]; then
    echo "[1/2] 安装依赖..."
    pip3 install -r requirements.txt -q
    touch .deps_installed
    echo "  -> 依赖安装完成"
else
    echo "[1/2] 依赖已安装，跳过"
fi

echo "[2/2] 启动服务器..."
echo ""
echo "  浏览器访问: http://localhost:8080"
echo "  按 Ctrl+C 停止服务"
echo ""

python3 app.py
