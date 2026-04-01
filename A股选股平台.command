#!/bin/bash
# A股选股平台 — 双击启动脚本
# macOS 下双击此文件即可启动服务并自动打开浏览器

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================"
echo "  A股选股平台 v1.2"
echo "================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.10+"
    echo ""
    echo "下载地址: https://www.python.org/downloads/"
    echo ""
    echo "按回车键退出..."
    read
    exit 1
fi

# Install dependencies if needed
if [ ! -f ".deps_installed" ]; then
    echo "[1/3] 首次运行，正在安装依赖..."
    pip3 install -r requirements.txt -q
    touch .deps_installed
    echo "  -> 依赖安装完成"
else
    echo "[1/3] 依赖已就绪"
fi

echo "[2/3] 启动服务器..."

# Start server in background
python3 app.py &
SERVER_PID=$!

# Wait for server to be ready
echo "[3/3] 等待服务启动..."
for i in $(seq 1 15); do
    if curl -s http://localhost:8080/ > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Open browser
echo ""
echo "  正在打开浏览器..."
open http://localhost:8080

echo ""
echo "  ✓ 服务已启动"
echo "  ✓ 浏览器已打开 http://localhost:8080"
echo ""
echo "  关闭此窗口即可停止服务"
echo ""

# Wait for server process (keeps Terminal window alive)
wait $SERVER_PID
