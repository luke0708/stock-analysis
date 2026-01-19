import logging
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TickFlowAnalyzer:
    """基于 tick 的资金流分析器。"""

    def __init__(self, large_order_percentile: int = 90, large_order_min: float = 200000):
        self.large_order_percentile = large_order_percentile
        self.large_order_min = large_order_min

    def analyze(self, df: pd.DataFrame) -> Dict:
        if df is None or df.empty:
            return {
                "summary": {},
                "large_orders": pd.DataFrame(),
                "processed_df": pd.DataFrame(),
                "quality_flags": ["empty_tick"],
            }

        df_anal = df.copy()
        quality_flags: List[str] = []

        if "性质" not in df_anal.columns:
            df_anal["性质"] = "中性盘"
            quality_flags.append("missing_nature")

        direction_map = {"买盘": 1, "卖盘": -1, "中性盘": 0}
        df_anal["方向"] = df_anal["性质"].map(direction_map)
        na_ratio = float(df_anal["方向"].isna().mean()) if len(df_anal) > 0 else 0.0
        if na_ratio > 0.1:
            quality_flags.append("direction_na_high")
            logger.warning("方向字段 NA 比例偏高: %.1f%%", na_ratio * 100)
        if na_ratio == 1.0:
            quality_flags.append("direction_all_na")
        df_anal["方向"] = df_anal["方向"].fillna(0).astype(int)
        if df_anal["方向"].abs().sum() == 0 and "成交价格" in df_anal.columns:
            price_change = df_anal["成交价格"].diff().fillna(0)
            df_anal.loc[price_change > 0, "方向"] = 1
            df_anal.loc[price_change < 0, "方向"] = -1
            quality_flags.append("direction_fallback_price_change")

        if "成交额(元)" not in df_anal.columns:
            quality_flags.append("missing_amount")
            df_anal["成交额(元)"] = 0.0
        else:
            df_anal["成交额(元)"] = pd.to_numeric(df_anal["成交额(元)"], errors="coerce").fillna(0)

        df_anal["净流入额"] = df_anal["成交额(元)"] * df_anal["方向"]

        buy_mask = df_anal["方向"] == 1
        sell_mask = df_anal["方向"] == -1
        neutral_mask = df_anal["方向"] == 0

        buy_amount = float(df_anal.loc[buy_mask, "成交额(元)"].sum())
        sell_amount = float(df_anal.loc[sell_mask, "成交额(元)"].sum())
        neutral_amount = float(df_anal.loc[neutral_mask, "成交额(元)"].sum())

        denom = buy_amount + sell_amount
        buy_ratio = buy_amount / denom if denom > 0 else 0.0
        sell_ratio = sell_amount / denom if denom > 0 else 0.0
        ofi = (buy_amount - sell_amount) / denom if denom > 0 else 0.0

        total_amount = float(df_anal["成交额(元)"].sum())
        if "成交量" in df_anal.columns and df_anal["成交量"].sum() > 0:
            vwap = float(total_amount / df_anal["成交量"].sum())
        else:
            vwap = 0.0
            quality_flags.append("missing_volume")

        amount_values = df_anal["成交额(元)"].dropna().values
        if amount_values.size > 0:
            percentile_val = float(np.percentile(amount_values, self.large_order_percentile))
            threshold = max(self.large_order_min, percentile_val)
        else:
            threshold = self.large_order_min

        threshold_series = None
        if "时间" in df_anal.columns:
            df_anal["minute"] = df_anal["时间"].dt.floor("min")
            minute_threshold = (
                df_anal.groupby("minute")["成交额(元)"]
                .quantile(self.large_order_percentile / 100.0)
                .clip(lower=self.large_order_min)
            )
            df_anal = df_anal.merge(
                minute_threshold.rename("minute_threshold"),
                left_on="minute",
                right_index=True,
                how="left",
            )
            time_str = df_anal["时间"].dt.strftime("%H:%M")
            early_mask = (time_str >= "09:30") & (time_str <= "10:30")
            threshold_series = df_anal["minute_threshold"] * np.where(early_mask, 1.2, 1.0)
            df_anal["is_large_order"] = df_anal["成交额(元)"] >= threshold_series
        else:
            df_anal["is_large_order"] = df_anal["成交额(元)"] >= threshold

        large_orders = df_anal[df_anal["is_large_order"]].copy()
        avg_turnover = float(df_anal["成交额(元)"].mean()) if len(df_anal) > 0 else 0.0
        if avg_turnover > 0:
            large_orders["ratio"] = large_orders["成交额(元)"] / avg_turnover
        else:
            large_orders["ratio"] = 0.0

        large_buy_amount = float(large_orders.loc[large_orders["方向"] == 1, "成交额(元)"].sum())
        large_sell_amount = float(large_orders.loc[large_orders["方向"] == -1, "成交额(元)"].sum())
        large_net_inflow = large_buy_amount - large_sell_amount

        retail_buy_amount = buy_amount - large_buy_amount
        retail_sell_amount = sell_amount - large_sell_amount
        retail_net_inflow = retail_buy_amount - retail_sell_amount

        summary = {
            "trade_count": len(df_anal),
            "buy_count": int(buy_mask.sum()),
            "sell_count": int(sell_mask.sum()),
            "neutral_count": int(neutral_mask.sum()),
            "buy_amount": buy_amount,
            "sell_amount": sell_amount,
            "neutral_amount": neutral_amount,
            "net_inflow": buy_amount - sell_amount,
            "buy_ratio": buy_ratio,
            "sell_ratio": sell_ratio,
            "ofi": ofi,
            "vwap": vwap,
            "total_turnover": total_amount,
            "large_order_threshold": threshold,
            "large_order_threshold_early": threshold * 1.2,
            "large_order_count": len(large_orders),
            "large_buy_amount": large_buy_amount,
            "large_sell_amount": large_sell_amount,
            "large_order_net_inflow": large_net_inflow,
            "retail_buy_amount": retail_buy_amount,
            "retail_sell_amount": retail_sell_amount,
            "retail_net_inflow": retail_net_inflow,
        }

        logger.info("Tick资金流分析完成: trades=%s", len(df_anal))
        return {
            "summary": summary,
            "large_orders": large_orders,
            "processed_df": df_anal,
            "quality_flags": quality_flags,
        }
