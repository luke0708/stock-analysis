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

    venv_candidates = [Path(".venv"), Path("venv")]
    venv_dir = next((p for p in venv_candidates if p.exists()), None)
    if not venv_dir:
        print("❌ 未找到虚拟环境目录（支持 .venv 或 venv）")
        print("请先运行:")
        print("  python3 -m venv .venv")
        print("  source .venv/bin/activate")
        print("  pip install -r requirements.txt")
        return

    venv_python = venv_dir / "bin" / "python"
    if not venv_python.exists():
        print(f"❌ 找到虚拟环境 {venv_dir}，但缺少 python 可执行文件")
        return

    check_streamlit = subprocess.run(
        [str(venv_python), "-c", "import streamlit"],
        capture_output=True,
        text=True,
        check=False,
    )
    if check_streamlit.returncode != 0:
        print(f"❌ 找到虚拟环境 {venv_dir}，但缺少 streamlit Python 模块")
        print("请先运行: pip install -r requirements.txt")
        return

    if sys.prefix == sys.base_prefix:
        print(f"⚠️ 当前未激活虚拟环境，仍将使用 {venv_python} 启动。")

    print("🚀 正在启动系统...")
    print("👉 按下 Ctrl+C 或关闭窗口即可退出")
    print("-----------------------------------------")

    cmd = [
        str(venv_python),
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address=127.0.0.1",
        "--server.port=8501",
    ]
    subprocess.run(cmd, check=False)

if __name__ == "__main__":
    main()
