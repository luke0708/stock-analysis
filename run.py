import os
import subprocess
import sys
from pathlib import Path

def main():
    """
    Helper script to run the streamlit app.
    Usage: python run.py
    """
    app_path = Path("stock_analysis/ui/unified_app.py").absolute()
    if not app_path.exists():
        print(f"Error: Could not find app at {app_path}")
        return

    print("=========================================")
    print("   A股资金流向智能分析系统 v2.2")
    print("=========================================")

    print("🧹 正在检查并清理旧进程...")
    subprocess.run(["pkill", "-9", "-f", "streamlit"], check=False)
    try:
        result = subprocess.run(
            ["lsof", "-ti:8501"],
            capture_output=True,
            text=True,
            check=False
        )
        pids = [pid for pid in result.stdout.strip().splitlines() if pid]
        if pids:
            subprocess.run(["kill", "-9", *pids], check=False)
    except FileNotFoundError:
        print("⚠️ 未找到 lsof，跳过端口占用检查。")

    venv_dir = Path("venv")
    streamlit_path = venv_dir / "bin" / "streamlit"
    if not venv_dir.exists() or not streamlit_path.exists():
        print("❌ 未找到虚拟环境 (venv) 或 streamlit")
        print("请先运行: pip install -r requirements.txt (在 venv 中)")
        return

    if sys.prefix == sys.base_prefix:
        print("⚠️ 当前未激活 venv，仍将使用 venv/bin/streamlit 启动。")

    print("🚀 正在启动系统...")
    print("👉 按下 Ctrl+C 或关闭窗口即可退出")
    print("-----------------------------------------")

    cmd = [
        str(streamlit_path),
        "run",
        str(app_path),
        "--server.address=127.0.0.1",
        "--server.port=8501",
    ]
    subprocess.run(cmd, check=False)

if __name__ == "__main__":
    main()
