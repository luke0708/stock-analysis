import logging
from typing import Dict, Optional, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _safe_number(value) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, float) and np.isnan(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return None


class PriceRangeAnalyzer:
    """价格区间分析：Pivot、ATR 通道与 Donchian 通道。"""

    def __init__(
        self,
        pivot_window: int = 1,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        donchian_window: int = 20,
        ema_window: int = 20,
    ):
        self.pivot_window = pivot_window
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.donchian_window = donchian_window
        self.ema_window = ema_window

    def _normalize_daily(self, df: pd.DataFrame) -> pd.DataFrame:
        df_copy = df.copy()
        col_map = {
            "date": "日期",
            "trade_date": "日期",
            "时间": "日期",
            "open": "开盘",
            "high": "最高",
            "low": "最低",
            "close": "收盘",
            "volume": "成交量",
            "amount": "成交额",
        }
        df_copy = df_copy.rename(columns=col_map)
        if "日期" in df_copy.columns:
            df_copy["日期"] = pd.to_datetime(df_copy["日期"], errors="coerce")
            df_copy = df_copy.dropna(subset=["日期"]).sort_values("日期")

        for col in ["开盘", "最高", "最低", "收盘"]:
            if col in df_copy.columns:
                df_copy[col] = pd.to_numeric(df_copy[col], errors="coerce")
        return df_copy

    def _calc_pivot(self, df: pd.DataFrame) -> Dict:
        if df.empty or not {"最高", "最低", "收盘"}.issubset(df.columns):
            return {}

        window_df = df.tail(self.pivot_window)
        if window_df.empty:
            return {}
        last = window_df.iloc[-1]
        high = last.get("最高")
        low = last.get("最低")
        close = last.get("收盘")
        if pd.isna(high) or pd.isna(low) or pd.isna(close):
            return {}

        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        s1 = 2 * pivot - high
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)

        return {
            "method": "Pivot Points (Classic)",
            "window_days": int(self.pivot_window),
            "formula": "P=(H+L+C)/3; R1=2P-L; S1=2P-H; R2=P+(H-L); S2=P-(H-L)",
            "pivot": _safe_number(pivot),
            "resistance_1": _safe_number(r1),
            "support_1": _safe_number(s1),
            "resistance_2": _safe_number(r2),
            "support_2": _safe_number(s2),
        }

    def _calc_atr_channel(self, df: pd.DataFrame) -> Dict:
        if df.empty or not {"最高", "最低", "收盘"}.issubset(df.columns):
            return {}

        df_tail = df.tail(max(self.atr_period + 2, self.ema_window + 2))
        if df_tail.empty:
            return {}

        prev_close = df_tail["收盘"].shift(1)
        tr = pd.concat(
            [
                (df_tail["最高"] - df_tail["最低"]).abs(),
                (df_tail["最高"] - prev_close).abs(),
                (df_tail["最低"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr_series = tr.rolling(self.atr_period).mean()
        atr_val = atr_series.iloc[-1]

        ema_mid = df_tail["收盘"].ewm(span=self.ema_window, adjust=False).mean().iloc[-1]
        if pd.isna(atr_val) or pd.isna(ema_mid):
            return {}

        upper = ema_mid + self.atr_multiplier * atr_val
        lower = ema_mid - self.atr_multiplier * atr_val

        return {
            "method": "ATR Volatility Channel",
            "atr_period": int(self.atr_period),
            "ema_window": int(self.ema_window),
            "multiplier": float(self.atr_multiplier),
            "formula": "Mid=EMA(close); Upper=Mid+k*ATR; Lower=Mid-k*ATR",
            "mid": _safe_number(ema_mid),
            "upper_band": _safe_number(upper),
            "lower_band": _safe_number(lower),
            "atr_value": _safe_number(atr_val),
        }

    def _calc_donchian(self, df: pd.DataFrame) -> Dict:
        if df.empty or not {"最高", "最低"}.issubset(df.columns):
            return {}

        window_df = df.tail(self.donchian_window)
        if window_df.empty:
            return {}

        upper = window_df["最高"].max()
        lower = window_df["最低"].min()
        if pd.isna(upper) or pd.isna(lower):
            return {}

        width = upper - lower
        return {
            "method": "Donchian Channel",
            "window_days": int(self.donchian_window),
            "formula": "Upper=Max(High,N); Lower=Min(Low,N)",
            "upper_band": _safe_number(upper),
            "lower_band": _safe_number(lower),
            "channel_width": _safe_number(width),
        }

    def _build_consensus(self, supports: List[float], resistances: List[float]) -> Dict:
        if not supports or not resistances:
            return {}
        overlap_low = max(supports)
        overlap_high = min(resistances)
        if overlap_low <= overlap_high:
            agreement = "high"
            consensus = {
                "support_zone": _safe_number(overlap_low),
                "resistance_zone": _safe_number(overlap_high),
            }
        else:
            agreement = "low"
            consensus = {}

        support_spread = max(supports) - min(supports)
        resistance_spread = max(resistances) - min(resistances)

        result = {
            "agreement_level": agreement,
            "support_spread": _safe_number(support_spread),
            "resistance_spread": _safe_number(resistance_spread),
        }
        result.update(consensus)
        return result

    def analyze(self, df: pd.DataFrame) -> Dict:
        if df is None or df.empty:
            return {}

        daily = self._normalize_daily(df)
        if daily.empty:
            return {}

        pivot = self._calc_pivot(daily)
        atr = self._calc_atr_channel(daily)
        donchian = self._calc_donchian(daily)

        supports = []
        resistances = []
        if pivot.get("support_1") is not None and pivot.get("resistance_1") is not None:
            supports.append(pivot["support_1"])
            resistances.append(pivot["resistance_1"])
        if atr.get("lower_band") is not None and atr.get("upper_band") is not None:
            supports.append(atr["lower_band"])
            resistances.append(atr["upper_band"])
        if donchian.get("lower_band") is not None and donchian.get("upper_band") is not None:
            supports.append(donchian["lower_band"])
            resistances.append(donchian["upper_band"])

        methods_applied = [
            name
            for name, payload in [
                ("pivot_classic", pivot),
                ("atr_channel", atr),
                ("donchian_channel", donchian),
            ]
            if payload
        ]

        consensus = self._build_consensus(supports, resistances)

        return {
            "methods_applied": methods_applied,
            "disclaimer": "区间基于历史价格计算，为技术分析参考，非投资建议。",
            "pivot_classic": pivot,
            "atr_channel": atr,
            "donchian_channel": donchian,
            "consensus_view": consensus,
        }
