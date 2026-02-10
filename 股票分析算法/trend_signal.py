"""Trend signal engine v1.

Standalone implementation under `股票分析算法/` for staged delivery.
This module avoids touching existing production UI and provides a stable,
explainable rule-based output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class TrendSignalConfig:
    """Config for threshold and scoring parameters."""

    bias_threshold_pct: float = 5.0
    ma_support_tolerance: float = 0.02
    volume_shrink_ratio: float = 0.7
    volume_heavy_ratio: float = 1.5

    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    rsi_short: int = 6
    rsi_mid: int = 12
    rsi_long: int = 24
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    score_weights: Dict[str, int] = field(
        default_factory=lambda: {
            "trend": 30,
            "bias": 20,
            "volume": 15,
            "support": 10,
            "macd": 15,
            "rsi": 10,
        }
    )


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        val = float(value)
        if np.isnan(val):
            return None
        return val
    except Exception:
        return None


def _normalize_daily_df(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Normalize schema to date/open/high/low/close/volume/amount."""
    warnings: List[str] = []
    if df is None or df.empty:
        return pd.DataFrame(), ["daily_ohlcv empty"]

    normalized = df.copy()
    col_map = {
        "日期": "date",
        "时间": "date",
        "trade_date": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
        "pct_chg": "pct_chg",
    }
    normalized = normalized.rename(columns=col_map)

    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in normalized.columns]
    if missing:
        warnings.append(f"missing columns: {','.join(missing)}")

    if "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")

    for col in ["open", "high", "low", "close", "volume", "amount", "pct_chg"]:
        if col in normalized.columns:
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce")

    if {"high", "low"}.issubset(normalized.columns):
        bad_hl = (normalized["high"] < normalized["low"]).fillna(False)
        if bad_hl.any():
            warnings.append(f"found high<low rows: {int(bad_hl.sum())}")

    key_cols = [c for c in ["date", "close", "volume"] if c in normalized.columns]
    if key_cols:
        before = len(normalized)
        normalized = normalized.dropna(subset=key_cols)
        dropped = before - len(normalized)
        if dropped > 0:
            warnings.append(f"dropped invalid rows: {dropped}")

    if "close" in normalized.columns:
        non_positive_close = (normalized["close"] <= 0).fillna(False)
        if non_positive_close.any():
            warnings.append(f"non-positive close rows: {int(non_positive_close.sum())}")
            normalized = normalized.loc[~non_positive_close]

    if "volume" in normalized.columns:
        negative_volume = (normalized["volume"] < 0).fillna(False)
        if negative_volume.any():
            warnings.append(f"negative volume rows: {int(negative_volume.sum())}")
            normalized = normalized.loc[~negative_volume]

    if "date" in normalized.columns:
        normalized = normalized.sort_values("date").reset_index(drop=True)

    return normalized, warnings


def _data_sufficiency(length: int) -> str:
    if length >= 40:
        return "high"
    if length >= 20:
        return "medium"
    return "low"


def _calc_mas(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["ma5"] = work["close"].rolling(window=5, min_periods=1).mean()
    work["ma10"] = work["close"].rolling(window=10, min_periods=1).mean()
    work["ma20"] = work["close"].rolling(window=20, min_periods=1).mean()
    if len(work) >= 60:
        work["ma60"] = work["close"].rolling(window=60, min_periods=1).mean()
    else:
        work["ma60"] = work["ma20"]
    return work


def _calc_macd(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    work = df.copy()
    ema_fast = work["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = work["close"].ewm(span=slow, adjust=False).mean()
    work["macd_dif"] = ema_fast - ema_slow
    work["macd_dea"] = work["macd_dif"].ewm(span=signal, adjust=False).mean()
    work["macd_bar"] = (work["macd_dif"] - work["macd_dea"]) * 2
    return work


def _calc_rsi(df: pd.DataFrame, periods: Tuple[int, int, int]) -> pd.DataFrame:
    work = df.copy()
    delta = work["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    for p in periods:
        avg_gain = gain.rolling(window=p, min_periods=p).mean()
        avg_loss = loss.rolling(window=p, min_periods=p).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        work[f"rsi_{p}"] = rsi.fillna(50.0)
    return work


def _classify_ma_alignment(df: pd.DataFrame, ma5: float, ma10: float, ma20: float) -> Tuple[str, str, int]:
    if ma5 > ma10 > ma20:
        prev_idx = -5 if len(df) >= 5 else -1
        prev = df.iloc[prev_idx]
        prev_spread = ((prev["ma5"] - prev["ma20"]) / prev["ma20"] * 100) if prev["ma20"] else 0
        curr_spread = ((ma5 - ma20) / ma20 * 100) if ma20 else 0
        if curr_spread > prev_spread and curr_spread > 5:
            return "strong_bull", "强势多头排列，均线发散上行", 90
        return "bull", "多头排列 MA5>MA10>MA20", 75

    if ma5 > ma10 and ma10 <= ma20:
        return "weak_bull", "弱势多头，MA5>MA10 但 MA10≤MA20", 55

    if ma5 < ma10 < ma20:
        prev_idx = -5 if len(df) >= 5 else -1
        prev = df.iloc[prev_idx]
        prev_spread = ((prev["ma20"] - prev["ma5"]) / prev["ma5"] * 100) if prev["ma5"] else 0
        curr_spread = ((ma20 - ma5) / ma5 * 100) if ma5 else 0
        if curr_spread > prev_spread and curr_spread > 5:
            return "strong_bear", "强势空头排列，均线发散下行", 10
        return "bear", "空头排列 MA5<MA10<MA20", 25

    if ma5 < ma10 and ma10 >= ma20:
        return "weak_bear", "弱势空头，MA5<MA10 但 MA10≥MA20", 40

    return "consolidation", "均线缠绕，趋势不明", 50


def _classify_volume_status(
    volume_ratio_5d: Optional[float],
    price_change_pct_1d: Optional[float],
    cfg: TrendSignalConfig,
) -> Tuple[str, str]:
    if volume_ratio_5d is None or price_change_pct_1d is None:
        return "normal", "量能数据不足"

    if volume_ratio_5d >= cfg.volume_heavy_ratio:
        if price_change_pct_1d > 0:
            return "heavy_up", "放量上涨，多头力量强劲"
        return "heavy_down", "放量下跌，注意风险"

    if volume_ratio_5d <= cfg.volume_shrink_ratio:
        if price_change_pct_1d > 0:
            return "shrink_up", "缩量上涨，上攻动能不足"
        return "shrink_down", "缩量回调，洗盘特征明显"

    return "normal", "量能正常"


def _detect_support_resistance(
    df: pd.DataFrame,
    price: float,
    ma5: float,
    ma10: float,
    ma20: float,
    tolerance: float,
) -> Dict[str, Any]:
    support_ma5 = False
    support_ma10 = False
    support_levels: List[float] = []
    resistance_levels: List[float] = []

    if ma5 > 0:
        d5 = abs(price - ma5) / ma5
        if d5 <= tolerance and price >= ma5:
            support_ma5 = True
            support_levels.append(ma5)

    if ma10 > 0:
        d10 = abs(price - ma10) / ma10
        if d10 <= tolerance and price >= ma10:
            support_ma10 = True
            if ma10 not in support_levels:
                support_levels.append(ma10)

    if ma20 > 0 and price >= ma20 and ma20 not in support_levels:
        support_levels.append(ma20)

    if len(df) >= 20 and "high" in df.columns:
        recent_high = _safe_float(df["high"].tail(20).max())
        if recent_high is not None and recent_high > price:
            resistance_levels.append(recent_high)

    return {
        "support_ma5": support_ma5,
        "support_ma10": support_ma10,
        "support_levels": support_levels,
        "resistance_levels": resistance_levels,
    }


def _classify_macd_status(df: pd.DataFrame) -> Tuple[str, str]:
    if len(df) < 2 or not {"macd_dif", "macd_dea"}.issubset(df.columns):
        return "bullish", "MACD 数据不足"

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    prev_gap = prev["macd_dif"] - prev["macd_dea"]
    curr_gap = latest["macd_dif"] - latest["macd_dea"]

    is_golden_cross = prev_gap <= 0 < curr_gap
    is_death_cross = prev_gap >= 0 > curr_gap

    is_crossing_up = prev["macd_dif"] <= 0 < latest["macd_dif"]
    is_crossing_down = prev["macd_dif"] >= 0 > latest["macd_dif"]

    if is_golden_cross and latest["macd_dif"] > 0:
        return "golden_cross_zero", "零轴上金叉，趋势强化"
    if is_crossing_up:
        return "crossing_up", "DIF 上穿零轴，趋势转强"
    if is_golden_cross:
        return "golden_cross", "金叉，趋势向上"
    if is_death_cross:
        return "death_cross", "死叉，趋势向下"
    if is_crossing_down:
        return "crossing_down", "DIF 下穿零轴，趋势转弱"

    if latest["macd_dif"] > 0 and latest["macd_dea"] > 0:
        return "bullish", "MACD 多头结构"
    if latest["macd_dif"] < 0 and latest["macd_dea"] < 0:
        return "bearish", "MACD 空头结构"

    return "bullish", "MACD 中性"


def _classify_rsi_status(rsi12: Optional[float], cfg: TrendSignalConfig) -> Tuple[str, str]:
    if rsi12 is None:
        return "neutral", "RSI 数据不足"
    if rsi12 > cfg.rsi_overbought:
        return "overbought", f"RSI 超买({rsi12:.1f})"
    if rsi12 > 60:
        return "strong_buy_zone", f"RSI 强势({rsi12:.1f})"
    if rsi12 >= 40:
        return "neutral", f"RSI 中性({rsi12:.1f})"
    if rsi12 >= cfg.rsi_oversold:
        return "weak", f"RSI 偏弱({rsi12:.1f})"
    return "oversold", f"RSI 超卖({rsi12:.1f})"


def _score_components(
    trend_type: str,
    bias_ma5: Optional[float],
    volume_status: str,
    support_ma5: bool,
    support_ma10: bool,
    macd_status: str,
    rsi_status: str,
    cfg: TrendSignalConfig,
) -> Dict[str, int]:
    trend_scores = {
        "strong_bull": 30,
        "bull": 26,
        "weak_bull": 18,
        "consolidation": 12,
        "weak_bear": 8,
        "bear": 4,
        "strong_bear": 0,
    }
    bias_score = 10
    if bias_ma5 is not None:
        if bias_ma5 < 0:
            if bias_ma5 > -3:
                bias_score = 20
            elif bias_ma5 > -5:
                bias_score = 16
            else:
                bias_score = 8
        elif bias_ma5 < 2:
            bias_score = 18
        elif bias_ma5 < cfg.bias_threshold_pct:
            bias_score = 14
        else:
            bias_score = 4

    volume_scores = {
        "shrink_down": 15,
        "heavy_up": 12,
        "normal": 10,
        "shrink_up": 6,
        "heavy_down": 0,
    }

    support_score = (5 if support_ma5 else 0) + (5 if support_ma10 else 0)

    macd_scores = {
        "golden_cross_zero": 15,
        "golden_cross": 12,
        "crossing_up": 10,
        "bullish": 8,
        "bearish": 2,
        "crossing_down": 0,
        "death_cross": 0,
    }

    rsi_scores = {
        "oversold": 10,
        "strong_buy_zone": 8,
        "neutral": 5,
        "weak": 3,
        "overbought": 0,
    }

    return {
        "trend": trend_scores.get(trend_type, 12),
        "bias": bias_score,
        "volume": volume_scores.get(volume_status, 8),
        "support": support_score,
        "macd": macd_scores.get(macd_status, 5),
        "rsi": rsi_scores.get(rsi_status, 5),
    }


def _compose_signal(score: int, trend_type: str) -> str:
    if score >= 75 and trend_type in {"strong_bull", "bull"}:
        return "strong_buy"
    if score >= 60 and trend_type in {"strong_bull", "bull", "weak_bull"}:
        return "buy"
    if score >= 45:
        return "hold"
    if score >= 30:
        return "wait"
    if trend_type in {"bear", "strong_bear"}:
        return "strong_sell"
    return "sell"


def _build_reasons_and_risks(
    trend_type: str,
    bias_ma5: Optional[float],
    volume_status: str,
    support_ma5: bool,
    support_ma10: bool,
    macd_status: str,
    macd_text: str,
    rsi_status: str,
    rsi_text: str,
    cfg: TrendSignalConfig,
) -> Tuple[List[str], List[str]]:
    reasons: List[str] = []
    risks: List[str] = []

    if trend_type in {"strong_bull", "bull"}:
        reasons.append("趋势结构偏强，顺势条件具备")
    elif trend_type in {"bear", "strong_bear"}:
        risks.append("趋势结构偏弱，逆势风险较高")

    if bias_ma5 is not None:
        if bias_ma5 >= cfg.bias_threshold_pct:
            risks.append(f"乖离率过高({bias_ma5:.2f}%)，不宜追高")
        elif bias_ma5 >= 0:
            reasons.append(f"乖离率温和({bias_ma5:.2f}%)")
        else:
            reasons.append(f"价格处于回踩区({bias_ma5:.2f}%)")

    if volume_status == "shrink_down":
        reasons.append("缩量回调，抛压有限")
    elif volume_status == "heavy_up":
        reasons.append("放量上涨，量价配合")
    elif volume_status == "heavy_down":
        risks.append("放量下跌，抛压显著")

    if support_ma5:
        reasons.append("MA5 支撑有效")
    if support_ma10:
        reasons.append("MA10 支撑有效")

    if macd_status in {"golden_cross_zero", "golden_cross", "crossing_up"}:
        reasons.append(macd_text)
    elif macd_status in {"death_cross", "crossing_down", "bearish"}:
        risks.append(macd_text)

    if rsi_status in {"strong_buy_zone", "oversold"}:
        reasons.append(rsi_text)
    elif rsi_status == "overbought":
        risks.append(rsi_text)

    return reasons[:6], risks[:6]


def _merge_config(cfg_override: Optional[Mapping[str, Any]]) -> TrendSignalConfig:
    cfg = TrendSignalConfig()
    if not cfg_override:
        return cfg

    for key, value in dict(cfg_override).items():
        if key == "macd" and isinstance(value, Mapping):
            cfg.macd_fast = int(value.get("fast", cfg.macd_fast))
            cfg.macd_slow = int(value.get("slow", cfg.macd_slow))
            cfg.macd_signal = int(value.get("signal", cfg.macd_signal))
        elif key == "rsi" and isinstance(value, Mapping):
            cfg.rsi_short = int(value.get("short", cfg.rsi_short))
            cfg.rsi_mid = int(value.get("mid", cfg.rsi_mid))
            cfg.rsi_long = int(value.get("long", cfg.rsi_long))
            cfg.rsi_overbought = float(value.get("overbought", cfg.rsi_overbought))
            cfg.rsi_oversold = float(value.get("oversold", cfg.rsi_oversold))
        elif hasattr(cfg, key):
            setattr(cfg, key, value)

    return cfg


def analyze_trend_signal(
    daily_df: pd.DataFrame,
    stock_meta: Optional[Mapping[str, Any]] = None,
    as_of_date: Optional[str] = None,
    config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute trend signal output payload.

    Args:
        daily_df: Daily OHLCV data frame.
        stock_meta: Optional stock metadata, e.g. {"code": "601899", "name": "紫金矿业"}.
        as_of_date: Optional target date string.
        config: Optional config overrides.
    """
    cfg = _merge_config(config)
    meta = dict(stock_meta or {})

    normalized, warnings = _normalize_daily_df(daily_df)
    if normalized.empty:
        return {
            "schema_version": "trend_signal_output_v1",
            "stock": {"code": meta.get("code", ""), "name": meta.get("name", "")},
            "as_of": {"date": as_of_date, "window_days": 0},
            "trend_signal": {},
            "quality": {
                "data_sufficiency": "low",
                "warnings": warnings or ["no valid daily data"],
                "calc_flags": {
                    "used_fallback_ma60": True,
                    "macd_ready": False,
                    "rsi_ready": False,
                },
            },
        }

    length = len(normalized)
    sufficiency = _data_sufficiency(length)
    if length < 20:
        warnings.append("daily_ohlcv length < 20")

    work = _calc_mas(normalized)
    work = _calc_macd(work, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
    work = _calc_rsi(work, (cfg.rsi_short, cfg.rsi_mid, cfg.rsi_long))

    latest = work.iloc[-1]
    prev = work.iloc[-2] if len(work) >= 2 else None

    price = float(latest["close"])
    ma5 = float(latest["ma5"])
    ma10 = float(latest["ma10"])
    ma20 = float(latest["ma20"])

    bias_ma5 = ((price - ma5) / ma5 * 100) if ma5 else None
    bias_ma10 = ((price - ma10) / ma10 * 100) if ma10 else None
    bias_ma20 = ((price - ma20) / ma20 * 100) if ma20 else None
    no_chase = bool(bias_ma5 is not None and bias_ma5 >= cfg.bias_threshold_pct)

    trend_type, trend_text, trend_strength = _classify_ma_alignment(work, ma5, ma10, ma20)

    volume_ratio_5d: Optional[float] = None
    if len(work) >= 6:
        base = work["volume"].iloc[-6:-1].mean()
        if base and base > 0:
            volume_ratio_5d = float(latest["volume"] / base)

    price_change_pct_1d: Optional[float] = None
    if prev is not None and prev["close"]:
        price_change_pct_1d = float((latest["close"] - prev["close"]) / prev["close"] * 100)

    volume_status, volume_text = _classify_volume_status(volume_ratio_5d, price_change_pct_1d, cfg)

    sr = _detect_support_resistance(
        work,
        price=price,
        ma5=ma5,
        ma10=ma10,
        ma20=ma20,
        tolerance=cfg.ma_support_tolerance,
    )

    macd_status, macd_text = _classify_macd_status(work)
    macd_dif = _safe_float(latest.get("macd_dif"))
    macd_dea = _safe_float(latest.get("macd_dea"))
    macd_bar = _safe_float(latest.get("macd_bar"))

    rsi_6 = _safe_float(latest.get(f"rsi_{cfg.rsi_short}"))
    rsi_12 = _safe_float(latest.get(f"rsi_{cfg.rsi_mid}"))
    rsi_24 = _safe_float(latest.get(f"rsi_{cfg.rsi_long}"))
    rsi_status, rsi_text = _classify_rsi_status(rsi_12, cfg)

    comp_scores = _score_components(
        trend_type=trend_type,
        bias_ma5=bias_ma5,
        volume_status=volume_status,
        support_ma5=sr["support_ma5"],
        support_ma10=sr["support_ma10"],
        macd_status=macd_status,
        rsi_status=rsi_status,
        cfg=cfg,
    )
    signal_score = int(sum(comp_scores.values()))
    buy_signal = _compose_signal(signal_score, trend_type)

    reasons, risks = _build_reasons_and_risks(
        trend_type=trend_type,
        bias_ma5=bias_ma5,
        volume_status=volume_status,
        support_ma5=sr["support_ma5"],
        support_ma10=sr["support_ma10"],
        macd_status=macd_status,
        macd_text=macd_text,
        rsi_status=rsi_status,
        rsi_text=rsi_text,
        cfg=cfg,
    )

    as_of = as_of_date
    if not as_of and "date" in work.columns and pd.notna(latest.get("date")):
        as_of = pd.to_datetime(latest["date"]).strftime("%Y-%m-%d")

    return {
        "schema_version": "trend_signal_output_v1",
        "stock": {"code": meta.get("code", ""), "name": meta.get("name", "")},
        "as_of": {"date": as_of, "window_days": length},
        "trend_signal": {
            "current_price": round(price, 4),
            "ma5": round(ma5, 4),
            "ma10": round(ma10, 4),
            "ma20": round(ma20, 4),
            "bias_ma5_pct": round(bias_ma5, 4) if bias_ma5 is not None else None,
            "bias_ma10_pct": round(bias_ma10, 4) if bias_ma10 is not None else None,
            "bias_ma20_pct": round(bias_ma20, 4) if bias_ma20 is not None else None,
            "no_chase": no_chase,
            "ma_alignment_type": trend_type,
            "ma_alignment_text": trend_text,
            "trend_strength_score": trend_strength,
            "volume_ratio_5d": round(volume_ratio_5d, 4) if volume_ratio_5d is not None else None,
            "volume_status": volume_status,
            "volume_trend_text": volume_text,
            "support_ma5": sr["support_ma5"],
            "support_ma10": sr["support_ma10"],
            "support_levels": [round(x, 4) for x in sr["support_levels"]],
            "resistance_levels": [round(x, 4) for x in sr["resistance_levels"]],
            "macd_dif": round(macd_dif, 6) if macd_dif is not None else None,
            "macd_dea": round(macd_dea, 6) if macd_dea is not None else None,
            "macd_bar": round(macd_bar, 6) if macd_bar is not None else None,
            "macd_status": macd_status,
            "macd_signal_text": macd_text,
            "rsi_6": round(rsi_6, 4) if rsi_6 is not None else None,
            "rsi_12": round(rsi_12, 4) if rsi_12 is not None else None,
            "rsi_24": round(rsi_24, 4) if rsi_24 is not None else None,
            "rsi_status": rsi_status,
            "rsi_signal_text": rsi_text,
            "signal_score": signal_score,
            "buy_signal": buy_signal,
            "signal_reasons": reasons,
            "risk_factors": risks,
            "component_scores": comp_scores,
        },
        "quality": {
            "data_sufficiency": sufficiency,
            "warnings": warnings,
            "calc_flags": {
                "used_fallback_ma60": length < 60,
                "macd_ready": length >= cfg.macd_slow,
                "rsi_ready": length >= cfg.rsi_long,
            },
        },
    }


__all__ = ["TrendSignalConfig", "analyze_trend_signal"]
