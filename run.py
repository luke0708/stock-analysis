import os
import sys
from pathlib import Path

def main():
    """
    Helper script to run the streamlit app.
    Usage: python run.py
    """
    app_path = Path("stock_analysis/ui/app.py").absolute()
    if not app_path.exists():
        print(f"Error: Could not find app at {app_path}")
        return
        
    print(f"Starting Stock Analysis App...")
    # Using os.system or subprocess to call streamlit
    cmd = f"streamlit run {app_path}"
    os.system(cmd)

if __name__ == "__main__":
    main()
