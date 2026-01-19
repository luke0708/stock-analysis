import logging
from typing import Dict, Iterable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TickAggregator:
    """Tick 数据窗口聚合器。"""

    def aggregate(self, df: pd.DataFrame, windows: Iterable[int]) -> Dict[int, pd.DataFrame]:
        if df is None or df.empty or "时间" not in df.columns:
            return {}

        df_agg = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(df_agg["时间"]):
            df_agg["时间"] = pd.to_datetime(df_agg["时间"], errors="coerce")
        df_agg = df_agg.dropna(subset=["时间"]).sort_values("时间")

        if "成交额(元)" not in df_agg.columns:
            df_agg["成交额(元)"] = 0.0
        if "成交量" not in df_agg.columns:
            df_agg["成交量"] = 0.0
        if "成交价格" not in df_agg.columns:
            df_agg["成交价格"] = np.nan
        if "方向" not in df_agg.columns:
            df_agg["方向"] = 0
        if "净流入额" not in df_agg.columns:
            df_agg["净流入额"] = 0.0

        df_agg["买盘额"] = np.where(df_agg["方向"] == 1, df_agg["成交额(元)"], 0.0)
        df_agg["卖盘额"] = np.where(df_agg["方向"] == -1, df_agg["成交额(元)"], 0.0)

        results: Dict[int, pd.DataFrame] = {}
        df_agg = df_agg.set_index("时间")

        for window in windows:
            rule = f"{window}min"
            grouped = df_agg.resample(rule)

            agg_dict = {
                "成交额(元)": "sum",
                "成交量": "sum",
                "净流入额": "sum",
                "买盘额": "sum",
                "卖盘额": "sum",
                "成交价格": "ohlc",
            }
            if "is_large_order" in df_agg.columns:
                agg_dict["is_large_order"] = "sum"

            agg_df = grouped.agg(agg_dict)

            if isinstance(agg_df.columns, pd.MultiIndex):
                agg_df.columns = ["_".join(col).strip() for col in agg_df.columns.values]

            agg_df["trade_count"] = grouped.size()
            agg_df = agg_df[agg_df["trade_count"] > 0]

            if agg_df.empty:
                results[window] = pd.DataFrame()
                continue

            agg_df = agg_df.rename(
                columns={
                    "成交额(元)_sum": "turnover",
                    "成交额_sum": "turnover",
                    "成交量_sum": "volume",
                    "净流入额_sum": "net_inflow",
                    "买盘额_sum": "buy_amount",
                    "卖盘额_sum": "sell_amount",
                    "is_large_order_sum": "large_order_count",
                    "成交价格_open": "price_open",
                    "成交价格_high": "price_high",
                    "成交价格_low": "price_low",
                    "成交价格_close": "price_close",
                }
            )

            if "turnover" not in agg_df.columns:
                if "成交额(元)" in agg_df.columns:
                    agg_df["turnover"] = agg_df["成交额(元)"]
                elif "成交额" in agg_df.columns:
                    agg_df["turnover"] = agg_df["成交额"]
                else:
                    agg_df["turnover"] = 0.0

            if "volume" not in agg_df.columns:
                if "成交量" in agg_df.columns:
                    agg_df["volume"] = agg_df["成交量"]
                else:
                    agg_df["volume"] = 0.0

            if "net_inflow" not in agg_df.columns:
                if "净流入额" in agg_df.columns:
                    agg_df["net_inflow"] = agg_df["净流入额"]
                else:
                    agg_df["net_inflow"] = 0.0

            if "large_order_count" not in agg_df.columns:
                agg_df["large_order_count"] = 0

            if "buy_amount" not in agg_df.columns:
                agg_df["buy_amount"] = 0.0
            if "sell_amount" not in agg_df.columns:
                agg_df["sell_amount"] = 0.0

            agg_df["ofi"] = (agg_df["buy_amount"] - agg_df["sell_amount"]) / (
                agg_df["buy_amount"] + agg_df["sell_amount"]
            ).replace(0, np.nan)
            agg_df["ofi"] = agg_df["ofi"].fillna(0.0)

            agg_df["vwap"] = agg_df["turnover"] / agg_df["volume"].replace(0, np.nan)
            agg_df["vwap"] = agg_df["vwap"].fillna(0.0)

            if {"price_high", "price_low"}.issubset(agg_df.columns):
                agg_df["range_pct"] = (
                    (agg_df["price_high"] - agg_df["price_low"]) / agg_df["vwap"].replace(0, np.nan)
                )
                agg_df["range_pct"] = agg_df["range_pct"].fillna(0.0) * 100
            else:
                agg_df["range_pct"] = 0.0

            agg_df = agg_df.reset_index()
            agg_df["time_window"] = agg_df["时间"].dt.strftime("%H:%M")
            results[window] = agg_df

        logger.info("Tick窗口聚合完成: %s", list(results.keys()))
        return results
