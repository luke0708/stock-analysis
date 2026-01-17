import akshare as ak
import pandas as pd

code = "300661"
date_str = "20260115"
d_fmt = "2026-01-15"
start_dt = f"{d_fmt} 09:00:00"
end_dt =   f"{d_fmt} 17:00:00"

print(f"Fetching {code} for {d_fmt}...")

# Try 1: With adjust='qfq'
try:
    print("--- Attempt 1: adjust='qfq' ---")
    df = ak.stock_zh_a_hist_min_em(symbol=code, start_date=start_dt, end_date=end_dt, period="1", adjust="qfq")
    if not df.empty:
        print("First row:", df.iloc[0].to_dict())
        print("Columns:", df.columns.tolist())
except Exception as e:
    print(f"Error: {e}")

# Try 2: Without adjust
try:
    print("\n--- Attempt 2: adjust='' ---")
    df2 = ak.stock_zh_a_hist_min_em(symbol=code, start_date=start_dt, end_date=end_dt, period="1", adjust="")
    if not df2.empty:
        print("First row:", df2.iloc[0].to_dict())
except Exception as e:
    print(f"Error: {e}")
