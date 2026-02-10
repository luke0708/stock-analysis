#!/bin/zsh
# 启动 A股资金流向智能分析系统 (Unified)

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

pause_and_exit() {
    local code="${1:-1}"
    echo ""
    echo "按回车键关闭窗口..."
    read -r
    exit "$code"
}

echo "========================================="
echo "   A股资金流向智能分析系统 v2.2"
echo "========================================="
echo "📁 项目目录: $SCRIPT_DIR"

# 1. 自动清理旧进程 (防止端口冲突)
# 这解决了"没办法关"的问题，每次启动都会先确保旧的被关掉
echo "🧹 正在检查并清理旧进程..."
pkill -9 -f "streamlit" >/dev/null 2>&1
# 双重保险：检查端口
if lsof -ti:8501 >/dev/null 2>&1; then
    echo "⚠️ 端口 8501 占用，正在释放..."
    kill -9 $(lsof -ti:8501) >/dev/null 2>&1
fi
sleep 1

# 2. 环境检查
VENV_DIR=""
if [ -d ".venv" ]; then
    VENV_DIR=".venv"
elif [ -d "venv" ]; then
    VENV_DIR="venv"
fi

if [ -z "$VENV_DIR" ]; then
    echo "❌ 未找到虚拟环境目录（支持 .venv 或 venv）"
    echo "请在项目目录执行："
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    pause_and_exit 1
fi

if ! "$VENV_DIR/bin/python" -c "import streamlit" >/dev/null 2>&1; then
    echo "❌ 找到虚拟环境: $VENV_DIR，但缺少 streamlit Python 模块"
    echo "请执行："
    echo "  source $VENV_DIR/bin/activate"
    echo "  pip install -r requirements.txt"
    pause_and_exit 1
fi

# 3. 启动应用
echo "🚀 正在启动系统..."
echo "👉 按下 Ctrl+C 或直接关闭此窗口即可完全退出程序"
echo "-----------------------------------------"

# 运行统一入口 (包含个股分析和市场热点，无需选择)
"$VENV_DIR/bin/python" -m streamlit run stock_analysis/ui/unified_app.py --server.address=0.0.0.0 --server.port=8501

echo ""
echo "ℹ️ 程序已退出。"
pause_and_exit 0
