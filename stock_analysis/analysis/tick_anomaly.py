import logging
from typing import Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


class TickAnomalyDetector:
    """基于 tick 窗口的异常检测（偏轻量）。"""

    def detect(self, df_tick: pd.DataFrame, window_df: pd.DataFrame) -> Dict:
        if df_tick is None or df_tick.empty or window_df is None or window_df.empty:
            return {"burst_windows": [], "anomaly_notes": []}

        burst_windows: List[Dict] = []
        anomaly_notes: List[str] = []

        trade_count = window_df["trade_count"].fillna(0)
        trade_threshold = float(trade_count.quantile(0.95))
        burst_rows = window_df[trade_count >= trade_threshold]
        for _, row in burst_rows.iterrows():
            burst_windows.append(
                {
                    "time_window": row["time_window"],
                    "trade_count": int(row["trade_count"]),
                    "net_inflow": float(row.get("net_inflow", 0)),
                }
            )

        if burst_windows:
            anomaly_notes.append(f"成交密度高峰出现在 {burst_windows[0]['time_window']}")

        net_inflow = window_df["net_inflow"].fillna(0)
        spike_threshold = float(net_inflow.abs().quantile(0.95))
        spike_rows = window_df[net_inflow.abs() >= spike_threshold]
        if not spike_rows.empty:
            spike_time = spike_rows.iloc[0]["time_window"]
            anomaly_notes.append(f"净流入突变发生于 {spike_time}")

        logger.info("Tick异常检测完成: bursts=%s", len(burst_windows))
        return {"burst_windows": burst_windows, "anomaly_notes": anomaly_notes}
