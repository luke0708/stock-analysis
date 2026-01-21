"""
未来功能占位页 (Mockups)
展示即将推出的功能预览图，让用户更有实感
"""
import streamlit as st
import pandas as pd
import numpy as np
import json
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Tuple, Optional

from stock_analysis.data.stock_list import get_stock_provider
from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.analysis.ai_client import get_deepseek_key, call_deepseek
from stock_analysis.data.news_provider import StockNewsProvider
from stock_analysis.analysis.price_range import PriceRangeAnalyzer


@st.cache_data(ttl=300)
def _load_stock_news(stock_code: str, limit: int) -> pd.DataFrame:
    return StockNewsProvider.get_stock_news(stock_code, limit=limit)


@st.cache_data(ttl=600)
def _load_daily_history(stock_code: str, end_date: date, window: int) -> pd.DataFrame:
    if not stock_code:
        return pd.DataFrame()
    provider = AkShareProvider()
    start_date = end_date - timedelta(days=window * 3)
    return provider.get_history_data(stock_code, start_date=start_date, end_date=end_date)


def _build_news_payload(news_df: Optional[pd.DataFrame], stock_name: str) -> Dict:
    if news_df is None or news_df.empty:
        return {
            "has_news": False,
            "source": "AkShare",
            "stock_name": stock_name,
            "items": [],
        }

    items = []
    for _, row in news_df.head(6).iterrows():
        items.append({
            "time": row.get("发布时间", ""),
            "title": row.get("新闻标题", ""),
            "summary": row.get("新闻内容", ""),
        })

    return {
        "has_news": True,
        "source": "AkShare",
        "stock_name": stock_name,
        "items": items,
        "latest_time": items[0]["time"] if items else None,
    }


def _drop_partial_daily(daily_df: pd.DataFrame, target_date: date) -> pd.DataFrame:
    if daily_df is None or daily_df.empty:
        return daily_df
    df = daily_df.copy()
    date_col = None
    for col in ["日期", "date", "时间", "trade_date"]:
        if col in df.columns:
            date_col = col
            break
    if not date_col:
        return daily_df
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    return df[df[date_col].dt.date != target_date]


def _parse_date_value(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(date_str, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


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


def _build_daily_series(daily_df: pd.DataFrame, limit: int) -> List[Dict]:
    if daily_df is None or daily_df.empty:
        return []

    df = daily_df.copy()
    date_col = None
    for col in ["日期", "date", "时间", "trade_date"]:
        if col in df.columns:
            date_col = col
            break
    if not date_col:
        return []

    col_map = {
        "open": "开盘",
        "high": "最高",
        "low": "最低",
        "close": "收盘",
        "volume": "成交量",
        "amount": "成交额",
    }
    df = df.rename(columns=col_map)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col)

    for col in ["收盘", "最高", "最低", "成交量", "成交额"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "收盘" not in df.columns:
        return []

    df["return_pct"] = df["收盘"].pct_change() * 100
    for ma in [5, 10, 20]:
        df[f"ma{ma}"] = df["收盘"].rolling(ma).mean()

    df_tail = df.tail(limit)
    series = []
    for _, row in df_tail.iterrows():
        date_val = row.get(date_col)
        date_str = date_val.strftime("%Y-%m-%d") if pd.notna(date_val) else ""
        series.append(
            {
                "date": date_str,
                "high": _safe_number(row.get("最高")),
                "low": _safe_number(row.get("最低")),
                "close": _safe_number(row.get("收盘")),
                "return_pct": _safe_number(row.get("return_pct")),
                "volume": _safe_number(row.get("成交量")),
                "ma5": _safe_number(row.get("ma5")),
                "ma10": _safe_number(row.get("ma10")),
                "ma20": _safe_number(row.get("ma20")),
            }
        )
    return series


def _build_daily_trend(daily_df: pd.DataFrame, limit: int) -> Dict:
    if daily_df is None or daily_df.empty:
        return {}

    df = daily_df.copy()
    date_col = None
    for col in ["日期", "date", "时间", "trade_date"]:
        if col in df.columns:
            date_col = col
            break
    if not date_col:
        return {}

    col_map = {
        "open": "开盘",
        "high": "最高",
        "low": "最低",
        "close": "收盘",
        "volume": "成交量",
        "amount": "成交额",
    }
    df = df.rename(columns=col_map)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col)

    if "收盘" not in df.columns:
        return {}

    df["收盘"] = pd.to_numeric(df["收盘"], errors="coerce")
    if "最高" in df.columns:
        df["最高"] = pd.to_numeric(df["最高"], errors="coerce")
    if "最低" in df.columns:
        df["最低"] = pd.to_numeric(df["最低"], errors="coerce")
    if "成交量" in df.columns:
        df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce")
    if "成交额" in df.columns:
        df["成交额"] = pd.to_numeric(df["成交额"], errors="coerce")

    df_tail = df.tail(limit).copy()
    available_days = len(df_tail)
    if available_days < 2:
        return {}

    df_tail["return_pct"] = df_tail["收盘"].pct_change() * 100
    for ma in [5, 10, 20]:
        df_tail[f"ma{ma}"] = df_tail["收盘"].rolling(ma).mean()

    close_first = df_tail["收盘"].iloc[0]
    close_last = df_tail["收盘"].iloc[-1]
    last_date = df_tail[date_col].iloc[-1]
    last_date_str = last_date.strftime("%Y-%m-%d") if pd.notna(last_date) else None
    return_pct = (
        (close_last / close_first - 1) * 100
        if pd.notna(close_first) and close_first != 0
        else None
    )

    daily_volatility = df_tail["return_pct"].std()

    ma5_last = df_tail["ma5"].iloc[-1]
    ma10_last = df_tail["ma10"].iloc[-1]
    ma20_last = df_tail["ma20"].iloc[-1]

    close_vs_ma5_pct = None
    close_vs_ma10_pct = None
    is_above_ma5 = None
    is_above_ma10 = None
    is_above_ma20 = None
    if pd.notna(close_last) and close_last != 0:
        if pd.notna(ma5_last) and ma5_last != 0:
            close_vs_ma5_pct = (close_last - ma5_last) / ma5_last * 100
            is_above_ma5 = close_last > ma5_last
        if pd.notna(ma10_last) and ma10_last != 0:
            close_vs_ma10_pct = (close_last - ma10_last) / ma10_last * 100
            is_above_ma10 = close_last > ma10_last
        if pd.notna(ma20_last) and ma20_last != 0:
            is_above_ma20 = close_last > ma20_last

    if pd.notna(ma5_last) and pd.notna(ma10_last) and pd.notna(ma20_last):
        if ma5_last > ma10_last > ma20_last:
            ma_alignment = "bullish"
        elif ma5_last < ma10_last < ma20_last:
            ma_alignment = "bearish"
        else:
            ma_alignment = "mixed"
    else:
        ma_alignment = "unknown"

    close_vs_ma20_pct = (
        (close_last - ma20_last) / ma20_last * 100
        if pd.notna(ma20_last) and ma20_last != 0
        else None
    )

    ma20_series = df_tail["ma20"].dropna()
    if len(ma20_series) >= 2 and ma20_series.iloc[0] != 0:
        ma20_slope_pct = (ma20_series.iloc[-1] / ma20_series.iloc[0] - 1) * 100
    else:
        ma20_slope_pct = None

    rolling_max = df_tail["收盘"].cummax()
    drawdown = (df_tail["收盘"] - rolling_max) / rolling_max.replace(0, np.nan)
    max_drawdown = drawdown.min() * 100 if not drawdown.empty else None

    volume_change_pct = None
    if "成交量" in df_tail.columns and df_tail["成交量"].notna().sum() >= 6:
        recent = df_tail["成交量"].tail(5).mean()
        prev = df_tail["成交量"].iloc[-10:-5].mean() if available_days >= 10 else df_tail["成交量"].head(5).mean()
        if pd.notna(prev) and prev != 0:
            volume_change_pct = (recent / prev - 1) * 100

    trend_label = "range"
    if return_pct is not None:
        if return_pct > 5 and ma_alignment == "bullish":
            trend_label = "up"
        elif return_pct < -5 and ma_alignment == "bearish":
            trend_label = "down"

    strength = "weak"
    if return_pct is not None and abs(return_pct) >= 8:
        strength = "strong"
    elif return_pct is not None and abs(return_pct) >= 3:
        strength = "medium"

    return {
        "window_days": available_days,
        "last_date": last_date_str,
        "close_last": _safe_number(close_last),
        "return_pct": _safe_number(return_pct),
        "volatility_pct": _safe_number(daily_volatility),
        "max_drawdown_pct": _safe_number(max_drawdown),
        "ma5": _safe_number(ma5_last),
        "ma10": _safe_number(ma10_last),
        "ma20": _safe_number(ma20_last),
        "ma_alignment": ma_alignment,
        "ma20_slope_pct": _safe_number(ma20_slope_pct),
        "close_vs_ma20_pct": _safe_number(close_vs_ma20_pct),
        "close_vs_ma5_pct": _safe_number(close_vs_ma5_pct),
        "close_vs_ma10_pct": _safe_number(close_vs_ma10_pct),
        "is_above_ma5": is_above_ma5,
        "is_above_ma10": is_above_ma10,
        "is_above_ma20": is_above_ma20,
        "volume_change_pct": _safe_number(volume_change_pct),
        "trend_label": trend_label,
        "trend_strength": strength,
    }


def _build_tick_window_series(tick_context: Dict, limit: int) -> Tuple[List[Dict], Optional[int]]:
    if not tick_context:
        return [], None

    window_df = None
    window_minutes = None
    for minutes, key in [(5, "window_5m"), (1, "window_1m"), (10, "window_10m")]:
        candidate = tick_context.get(key)
        if candidate is not None and not candidate.empty:
            window_df = candidate
            window_minutes = minutes
            break

    if window_df is None or window_df.empty:
        return [], window_minutes

    df_tail = window_df.tail(limit)
    series = []
    for _, row in df_tail.iterrows():
        time_window = row.get("time_window")
        if not time_window and "时间" in df_tail.columns:
            time_window = row.get("时间")
        series.append(
            {
                "time_window": str(time_window) if time_window is not None else "",
                "buy_amount": _safe_number(row.get("buy_amount")),
                "sell_amount": _safe_number(row.get("sell_amount")),
                "net_inflow": _safe_number(row.get("net_inflow")),
                "turnover": _safe_number(row.get("turnover")),
                "ofi": _safe_number(row.get("ofi")),
                "trade_count": _safe_number(row.get("trade_count")),
                "large_order_count": _safe_number(row.get("large_order_count")),
                "range_pct": _safe_number(row.get("range_pct")),
            }
        )
    return series, window_minutes


def _calc_limit_lock(timeseries: Dict) -> bool:
    close = timeseries.get("close_price")
    high = timeseries.get("high_price")
    low = timeseries.get("low_price")
    change_pct = timeseries.get("price_change_pct")
    if close in (None, 0) or high is None or low is None or change_pct is None:
        return False
    try:
        range_pct = (high - low) / close * 100
    except Exception:
        return False
    if abs(change_pct) >= 9.5 and range_pct <= 0.3:
        return True
    return False


def _calc_direction_reliability(tick_context: Optional[Dict], limit_lock: bool) -> str:
    if limit_lock:
        return "low"
    if not tick_context:
        return "low"
    inferred_ratio = tick_context.get("inferred_ratio")
    quality_flags = tick_context.get("quality_flags", [])
    if "direction_all_na" in quality_flags or "direction_fallback_price_change" in quality_flags:
        return "low"
    if inferred_ratio is None:
        return "medium"
    if inferred_ratio >= 0.5:
        return "low"
    if inferred_ratio >= 0.2:
        return "medium"
    return "high"


def _format_num(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "未知"
    try:
        if np.isnan(value):
            return "未知"
    except Exception:
        pass
    fmt = f"{{:.{digits}f}}"
    return fmt.format(value)


def _format_pct(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "未知"
    try:
        if np.isnan(value):
            return "未知"
    except Exception:
        pass
    fmt = f"{{:+.{digits}f}}%"
    return fmt.format(value)


def _bool_to_cn(value: Optional[bool]) -> str:
    if value is None:
        return "未知"
    return "上方" if value else "下方"


def _map_label(value: str, mapping: Dict[str, str]) -> str:
    return mapping.get(value, value or "未知")


def _extract_latest_time(df: pd.DataFrame) -> Optional[datetime]:
    if df is None or df.empty:
        return None
    for col in ["时间", "datetime", "time", "成交时间"]:
        if col in df.columns:
            value = pd.to_datetime(df[col], errors="coerce")
            value = value.dropna()
            if not value.empty:
                return value.iloc[-1].to_pydatetime()
    return None


def _calc_trading_progress(as_of: datetime) -> Dict:
    sessions = [(time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))]
    total_minutes = 240
    elapsed = 0
    for start, end in sessions:
        if as_of.time() <= start:
            continue
        session_end = end if as_of.time() >= end else as_of.time()
        if session_end <= start:
            continue
        elapsed += int(
            (datetime.combine(as_of.date(), session_end) - datetime.combine(as_of.date(), start)).total_seconds() / 60
        )
    progress = min(max(elapsed / total_minutes, 0.0), 1.0)
    return {
        "elapsed_minutes": elapsed,
        "total_minutes": total_minutes,
        "progress": round(progress, 4),
    }


def _build_today_partial(
    df: pd.DataFrame,
    timeseries: Dict,
    indicators: Dict,
    tick_context: Optional[Dict],
    analysis_day: date,
) -> Dict:
    latest_dt = _extract_latest_time(df)
    if latest_dt is None:
        latest_dt = datetime.combine(analysis_day, datetime.now().time())

    is_today = analysis_day == datetime.now().date()
    is_partial = is_today and latest_dt.time() < time(15, 0)

    data_scope = {
        "as_of": latest_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "is_partial": is_partial,
        "source_granularity": tick_context.get("flow_summary", {}).get("flow_quality", {}).get("data_granularity")
        if tick_context
        else "minute",
    }
    if is_today:
        data_scope.update(_calc_trading_progress(latest_dt))

    return {
        "scope": data_scope,
        "price": {
            "open": timeseries.get("open_price"),
            "close": timeseries.get("close_price"),
            "high": timeseries.get("high_price"),
            "low": timeseries.get("low_price"),
            "change_pct": timeseries.get("price_change_pct"),
        },
        "liquidity": {
            "turnover_total": timeseries.get("turnover_total"),
            "volume_total": timeseries.get("volume_total"),
            "vwap": indicators.get("vwap"),
        },
    }


def _build_readable_summary(
    daily_trend: Dict,
    price_range_analysis: Dict,
    flow_block: Dict,
    anomaly_highlights: List[Dict],
    largest_trades_raw: List[Dict],
    today_partial: Optional[Dict],
) -> Dict:
    intraday_texts = []
    if today_partial:
        scope = today_partial.get("scope", {})
        price = today_partial.get("price", {})
        liquidity = today_partial.get("liquidity", {})
        as_of = scope.get("as_of")
        close_now = _format_num(price.get("close"))
        high = _format_num(price.get("high"))
        low = _format_num(price.get("low"))
        change_pct = _format_pct(price.get("change_pct"))
        if close_now != "未知":
            time_label = f"截至{as_of}" if as_of else "盘中快照"
            intraday_texts.append(
                f"{time_label} 盘中最新价 {close_now}，最高 {high}，最低 {low}，涨跌幅 {change_pct}"
            )
        vwap = _format_num(liquidity.get("vwap"))
        if vwap != "未知":
            intraday_texts.append(f"VWAP {vwap}")

    trend_texts = []
    if daily_trend:
        trend_label = _map_label(daily_trend.get("trend_label", ""), {"up": "上行", "down": "下行", "range": "震荡"})
        strength = _map_label(daily_trend.get("trend_strength", ""), {"strong": "强", "medium": "中", "weak": "弱"})
        trend_texts.append(f"趋势状态: {trend_label}，强度: {strength}")
        close_last = _format_num(daily_trend.get("close_last"))
        ma5 = _format_num(daily_trend.get("ma5"))
        ma10 = _format_num(daily_trend.get("ma10"))
        ma20 = _format_num(daily_trend.get("ma20"))
        rel_ma5 = _bool_to_cn(daily_trend.get("is_above_ma5"))
        rel_ma10 = _bool_to_cn(daily_trend.get("is_above_ma10"))
        rel_ma20 = _bool_to_cn(daily_trend.get("is_above_ma20"))
        last_date = daily_trend.get("last_date")
        date_label = f"{last_date}日线收盘" if last_date else "日线收盘"
        trend_texts.append(
            f"{date_label} {close_last}，位于 MA5({ma5}){rel_ma5}、MA10({ma10}){rel_ma10}、MA20({ma20}){rel_ma20}"
        )
        ma5_dev = _format_pct(daily_trend.get("close_vs_ma5_pct"))
        ma10_dev = _format_pct(daily_trend.get("close_vs_ma10_pct"))
        ma20_dev = _format_pct(daily_trend.get("close_vs_ma20_pct"))
        trend_texts.append(
            f"相对均线偏离: MA5 {ma5_dev}，MA10 {ma10_dev}，MA20 {ma20_dev}"
        )
        alignment = _map_label(daily_trend.get("ma_alignment", ""), {"bullish": "多头", "bearish": "空头", "mixed": "混合"})
        trend_texts.append(f"均线排列: {alignment}")

    range_texts = []
    if price_range_analysis:
        consensus = price_range_analysis.get("consensus_view", {})
        support_zone = consensus.get("support_zone")
        resistance_zone = consensus.get("resistance_zone")
        if support_zone is not None or resistance_zone is not None:
            range_texts.append(
                f"共识区间: 支撑 {_format_num(support_zone)}，压力 {_format_num(resistance_zone)}"
            )
        pivot = price_range_analysis.get("pivot_classic", {})
        if pivot:
            range_texts.append(
                f"Pivot 支撑/压力: S1 {_format_num(pivot.get('support_1'))} / R1 {_format_num(pivot.get('resistance_1'))}"
            )
        atr = price_range_analysis.get("atr_channel", {})
        if atr:
            range_texts.append(
                f"ATR 通道: 下轨 {_format_num(atr.get('lower_band'))}，上轨 {_format_num(atr.get('upper_band'))}"
            )

    flow_texts = []
    if flow_block:
        net_inflow = flow_block.get("net_inflow")
        ofi = flow_block.get("ofi")
        if net_inflow is not None:
            flow_texts.append(f"净流入 {net_inflow / 1e8:+.2f} 亿")
        if ofi is not None:
            flow_texts.append(f"OFI {ofi:+.4f}")
        buy_amount = flow_block.get("buy_amount")
        sell_amount = flow_block.get("sell_amount")
        if buy_amount is not None or sell_amount is not None:
            flow_texts.append(
                f"买盘 {_format_num((buy_amount or 0) / 1e8)} 亿 / 卖盘 {_format_num((sell_amount or 0) / 1e8)} 亿"
            )
        buy_count = flow_block.get("buy_count")
        sell_count = flow_block.get("sell_count")
        if buy_count is not None or sell_count is not None:
            flow_texts.append(f"买盘笔数 {buy_count or 0} / 卖盘笔数 {sell_count or 0}")
        buy_count_ratio = flow_block.get("buy_count_ratio")
        sell_count_ratio = flow_block.get("sell_count_ratio")
        if buy_count_ratio is not None or sell_count_ratio is not None:
            flow_texts.append(
                f"笔数占比: 买盘 {_format_pct((buy_count_ratio or 0) * 100)} / 卖盘 {_format_pct((sell_count_ratio or 0) * 100)}"
            )
        avg_buy_amount = flow_block.get("avg_buy_amount")
        avg_sell_amount = flow_block.get("avg_sell_amount")
        if avg_buy_amount is not None or avg_sell_amount is not None:
            flow_texts.append(
                f"单笔均额: 买盘 {_format_num((avg_buy_amount or 0) / 1e4)} 万 / 卖盘 {_format_num((avg_sell_amount or 0) / 1e4)} 万"
            )
        neutral_amount = flow_block.get("neutral_amount")
        if neutral_amount:
            flow_texts.append(f"中性盘 {_format_num(neutral_amount / 1e8)} 亿")
        neutral_ratio = flow_block.get("neutral_ratio")
        direction_coverage = flow_block.get("direction_coverage")
        if neutral_ratio is not None:
            flow_texts.append(f"中性盘占比 {_format_pct(neutral_ratio * 100)}")
        if direction_coverage is not None:
            flow_texts.append(f"方向覆盖率 {_format_pct(direction_coverage * 100)}")

    anomaly_texts = []
    if anomaly_highlights:
        for item in anomaly_highlights:
            item_type = item.get("type", "")
            if item_type == "significant_sell":
                anomaly_texts.append(
                    f"显著卖盘 {item.get('time', '')} 金额 {_format_num(item.get('amount', 0) / 1e8)} 亿"
                )
            elif item_type == "significant_buy":
                anomaly_texts.append(
                    f"显著买盘 {item.get('time', '')} 金额 {_format_num(item.get('amount', 0) / 1e8)} 亿"
                )
            elif item_type == "window_outflow":
                anomaly_texts.append(
                    f"窗口净流出 {item.get('time_window', '')} 净流入 {_format_num((item.get('net_inflow') or 0) / 1e8)} 亿"
                )
            elif item_type == "window_inflow":
                anomaly_texts.append(
                    f"窗口净流入 {item.get('time_window', '')} 净流入 {_format_num((item.get('net_inflow') or 0) / 1e8)} 亿"
                )
            elif item_type == "summary_counts":
                anomaly_texts.append(
                    f"异常统计: 大额成交 {item.get('large_order_count', 0)}，价格跳跃 {item.get('price_spike_count', 0)}，量能放大 {item.get('volume_surge_count', 0)}"
                )

    if largest_trades_raw:
        for item in largest_trades_raw:
            anomaly_texts.append(
                f"原始最大成交 {item.get('time', '')} 金额 {_format_num(item.get('amount_1e8', 0))} 亿 方向 {item.get('direction', '中性盘')}"
            )

    return {
        "intraday": intraday_texts,
        "trend": trend_texts,
        "price_range": range_texts,
        "flow": flow_texts,
        "anomalies": anomaly_texts,
    }


def _build_anomaly_highlights(
    tick_context: Optional[Dict],
    tick_window_series: List[Dict],
    anomalies: Dict,
) -> List[Dict]:
    highlights: List[Dict] = []
    if tick_context and tick_context.get("large_orders_top5"):
        large_orders = tick_context["large_orders_top5"]
        sells = [o for o in large_orders if "卖" in str(o.get("type", ""))]
        buys = [o for o in large_orders if "买" in str(o.get("type", ""))]
        for item in sells[:2]:
            highlights.append(
                {
                    "type": "significant_sell",
                    "time": str(item.get("time", "")),
                    "amount": _safe_number(item.get("amount")),
                    "price": _safe_number(item.get("price")),
                }
            )
        for item in buys[:2]:
            highlights.append(
                {
                    "type": "significant_buy",
                    "time": str(item.get("time", "")),
                    "amount": _safe_number(item.get("amount")),
                    "price": _safe_number(item.get("price")),
                }
            )

    if tick_window_series:
        sorted_series = sorted(
            [w for w in tick_window_series if w.get("net_inflow") is not None],
            key=lambda x: x.get("net_inflow"),
        )
        if sorted_series:
            worst = sorted_series[0]
            best = sorted_series[-1]
            highlights.append(
                {
                    "type": "window_outflow",
                    "time_window": str(worst.get("time_window", "")),
                    "net_inflow": _safe_number(worst.get("net_inflow")),
                    "turnover": _safe_number(worst.get("turnover")),
                }
            )
            highlights.append(
                {
                    "type": "window_inflow",
                    "time_window": str(best.get("time_window", "")),
                    "net_inflow": _safe_number(best.get("net_inflow")),
                    "turnover": _safe_number(best.get("turnover")),
                }
            )

    summary = anomalies.get("summary", {}) if anomalies else {}
    if summary:
        highlights.append(
            {
                "type": "summary_counts",
                "large_order_count": summary.get("large_order_count", 0),
                "price_spike_count": summary.get("price_spike_count", 0),
                "volume_surge_count": summary.get("volume_surge_count", 0),
            }
        )

    return highlights

def show_multi_stock_compare():
    st.header("⚖️ 多股票对比分析 (Coming Soon)")
    st.info("🚧 此功能将在 v1.2 版本上线")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("功能预览")
        st.markdown("""
        - **多维叠加**: 同时查看最多 5 只股票的走势
        - **相对收益**: 以某日为基准查看相对涨跌幅
        - **资金流对比**: 横向比较谁的主力介入更深
        """)
        
    with col2:
        # Mock chart
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100)
        # Generate trend data (cumulative sum) + ensure no infinities
        np.random.seed(42)  # Fixed seed for stability
        data = pd.DataFrame(
            np.random.randn(100, 3).cumsum(0),
            index=dates,
            columns=['贵州茅台 (Mock)', '宁德时代 (Mock)', '招商银行 (Mock)']
        )
        # Add offset to avoid 0/negative if using log scale (though line_chart defaults to linear)
        data = data + 100 
        
        st.line_chart(data)

def show_backtesting():
    st.header("🧪 策略回测实验室 (Coming Soon)")
    st.warning("🚧 此功能将在 v1.3 版本上线")
    
    st.markdown("### 预设策略配置")
    c1, c2, c3 = st.columns(3)
    c1.selectbox("交易策略", ["双均线交叉", "RSI超买超卖", "网格交易"])
    c2.date_input("回测开始", value=pd.to_datetime("2023-01-01"))
    c3.number_input("初始资金", value=100000)
    
    st.button("开始回测 (演示按钮)", disabled=True)
    
    st.markdown("### 预期回测报告")
    st.write("📈 年化收益率: 15.2% | 📉 最大回撤: -8.5% | 🎯 胜率: 58%")
    
def show_global_markets():
    st.header("🌍 全球市场概览 (Coming Soon)")
    st.success("🚧 长期规划功能 (v2.2)")
    
    cols = st.columns(4)
    cols[0].metric("纳斯达克", "14,890.30", "+1.2%")
    cols[1].metric("恒生指数", "16,500.00", "-0.5%")
    cols[2].metric("日经225", "35,000.00", "+0.8%")
    cols[3].metric("标普500", "4,780.00", "+0.9%")
    
    st.caption("*以上数据仅为静态演示*")

def show_ai_analysis():
    st.header("🤖 AI 智能投顾")
    st.caption("专注于A股资金流向、日内异动与短期趋势解读，输出为结构化结论")

    api_key, api_key_name = get_deepseek_key()
    if not api_key:
        st.warning("未检测到 DeepSeek API Key，请在 .env 中配置后再使用。")
        st.code("DEEPSEEK_API_KEY=你的key", language="bash")
        return

    st.caption(f"当前使用环境变量: {api_key_name}")

    if "df" not in st.session_state or st.session_state.df is None:
        st.info("请先在“个股资金流向”页面完成一次分析，以便生成更准确的 AI 解读。")
        return

    if "ai_history" not in st.session_state:
        st.session_state.ai_history = []
    if "ai_last" not in st.session_state:
        st.session_state.ai_last = None
    if "ai_news_df" not in st.session_state:
        st.session_state.ai_news_df = None
    if "ai_news_stock" not in st.session_state:
        st.session_state.ai_news_stock = ""
    if "ai_news_limit" not in st.session_state:
        st.session_state.ai_news_limit = 0

    with st.expander("ℹ️ 输入数据说明", expanded=False):
        st.write(
            "模型输入来自最近一次个股分析结果，包含价格、资金流、技术指标与异动统计。"
            "原始数据已经过 DataCleaner 清洗（修复缺失值/异常值、标准化类型）。"
            "模型输出高度依赖这些结构化数据，因此切换日期或股票会显著影响解读。"
        )

    st.markdown("### 🎛️ 预设档位")
    preset = st.radio(
        "选择档位",
        ["自定义", "价格区间建议(趋势)", "资金流风险提示(当日)"],
        horizontal=True,
        help="预设档位会锁定分析侧重点与输出方式，避免配置冲突。"
    )

    preset_config = {
        "价格区间建议(趋势)": {
            "mode": "range",
            "focus": "盘中趋势与节奏",
            "style": "专业",
            "advice_mode": "行动模式",
            "only_data": True,
            "highlight_numbers": True,
            "add_watchlist": True,
            "include_news": False,
        },
        "资金流风险提示(当日)": {
            "mode": "risk",
            "focus": "风险与异动",
            "style": "交易员风格",
            "advice_mode": "结论模式",
            "only_data": True,
            "highlight_numbers": True,
            "add_watchlist": True,
            "include_news": False,
        },
    }

    preset_mode = "custom"
    if preset != "自定义":
        config = preset_config[preset]
        preset_mode = config["mode"]
        focus = config["focus"]
        style = config["style"]
        advice_mode = config["advice_mode"]
        only_data = config["only_data"]
        highlight_numbers = config["highlight_numbers"]
        add_watchlist = config["add_watchlist"]
        include_news = config["include_news"]

        st.info(
            f"已锁定配置：侧重点={focus}，风格={style}，模式={advice_mode}，"
            f"只基于数据={only_data}，突出数值={highlight_numbers}，观察清单={add_watchlist}，新闻={include_news}"
        )
    else:
        st.markdown("### 🎯 分析目标")
        focus = st.radio(
            "请选择分析侧重点",
            ["资金流向解读", "盘中趋势与节奏", "风险与异动", "主力行为复盘"],
            horizontal=True,
            help="切换侧重点会改变提示词，但需要点击“生成解读”才会更新结果。"
        )

        style = st.radio(
            "输出风格",
            ["简洁", "专业", "交易员风格"],
            horizontal=True,
            help="简洁=要点短句；专业=分小标题；交易员=更强调盘中节奏。"
        )

        advice_mode = st.radio(
            "输出模式",
            ["分析模式", "结论模式", "行动模式"],
            horizontal=True,
            help="行动模式会给出条件触发建议，不做收益承诺。"
        )

        col1, col2 = st.columns(2)
        with col1:
            only_data = st.checkbox(
                "只基于给定数据",
                value=True,
                help="只使用当前分析结果，不引入外部信息。"
            )
        with col2:
            highlight_numbers = st.checkbox(
                "突出关键数值",
                value=True,
                help="必须引用关键数据作为论据。"
            )
            add_watchlist = st.checkbox(
                "给出观察清单",
                value=True,
                help="列出后续关注的触发条件或关键变量。"
            )

    temperature = st.slider(
        "输出多样性 (temperature)",
        min_value=0.0,
        max_value=0.8,
        value=0.2,
        step=0.1,
        help="数值越低越稳定、越接近确定输出；数值越高越多样化。"
    )

    user_question = st.text_area(
        "补充问题（可选）",
        placeholder="例如：今天主力吸筹是否明显？短线有哪些风险点？",
        help="补充具体问题会改变解读重点；若涉及新闻，请开启下方“包含最新相关新闻”。"
    )

    st.markdown("### 📰 新闻补充（可选）")
    if preset == "自定义":
        include_news = st.checkbox(
            "包含最新相关新闻",
            value=False,
            help="从 AkShare 拉取相关新闻，可能有延迟或缺失。"
        )
    else:
        st.caption("预设档位默认不包含新闻，避免干扰趋势/资金流判断。")
    news_limit = st.slider(
        "新闻条数",
        min_value=3,
        max_value=12,
        value=6,
        step=1,
        disabled=not include_news
    )
    news_df = None
    stock_code = st.session_state.get("last_stock_code", "")
    if not stock_code or stock_code == "导入数据":
        fallback_code = st.session_state.get("stock_code", "")
        if isinstance(fallback_code, str) and fallback_code.isdigit() and len(fallback_code) == 6:
            stock_code = fallback_code
    if include_news:
        col_n1, col_n2 = st.columns([1, 3])
        with col_n1:
            fetch_news = st.button("拉取新闻")
        with col_n2:
            st.caption("提示：仅供分析参考，新闻覆盖可能不完整。")

        if fetch_news:
            with st.spinner("正在拉取相关新闻..."):
                news_df = _load_stock_news(stock_code, limit=news_limit)
                st.session_state.ai_news_df = news_df
                st.session_state.ai_news_stock = stock_code
                st.session_state.ai_news_limit = news_limit

        if (
            st.session_state.ai_news_df is not None
            and st.session_state.ai_news_stock == stock_code
            and st.session_state.ai_news_limit == news_limit
        ):
            news_df = st.session_state.ai_news_df

        if news_df is not None:
            if news_df.empty:
                st.info("暂未获取到相关新闻。")
            else:
                for _, row in news_df.head(5).iterrows():
                    title = row.get("新闻标题", "")
                    time = row.get("发布时间", "")
                    st.markdown(f"- [{time}] {title}")

    if user_question:
        news_keywords = ["新闻", "公告", "消息", "政策", "事件", "报道"]
        if any(k in user_question for k in news_keywords) and not include_news:
            st.warning("检测到新闻类问题，建议勾选“包含最新相关新闻”并拉取新闻。")

    with st.expander("📌 输入给模型的数据预览", expanded=False):
        context = _build_context(news_df=news_df, include_news=include_news)
        st.json(_json_safe(context))

    col_g1, col_g2 = st.columns([1, 3])
    with col_g1:
        generate_btn = st.button("生成解读", type="primary")
    with col_g2:
        st.caption("提示：生成会调用外部API，速度取决于网络。")

    if generate_btn:
        if include_news and news_df is None:
            with st.spinner("正在拉取相关新闻..."):
                news_df = _load_stock_news(stock_code, limit=news_limit)
                st.session_state.ai_news_df = news_df
                st.session_state.ai_news_stock = stock_code
                st.session_state.ai_news_limit = news_limit

        context = _build_context(news_df=news_df, include_news=include_news)
        stock_info = context.get("stock", {})
        session_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{stock_info.get('code', '')}"
        system_prompt, user_prompt = _build_prompts(
            context=context,
            focus=focus,
            style=style,
            advice_mode=advice_mode,
            preset_mode=preset_mode,
            only_data=only_data,
            highlight_numbers=highlight_numbers,
            add_watchlist=add_watchlist,
            user_question=user_question
        )
        params_summary = _summarize_settings(
            focus=focus,
            style=style,
            advice_mode=advice_mode,
            preset_mode=preset_mode,
            only_data=only_data,
            highlight_numbers=highlight_numbers,
            add_watchlist=add_watchlist,
            user_question=user_question
        )
        with st.spinner("正在生成AI解读..."):
            try:
                response = call_deepseek(
                    api_key=api_key,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=1200,
                )
                entry = {
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "focus": focus,
                    "style": style,
                    "advice_mode": advice_mode,
                    "preset_mode": preset_mode,
                    "constraints": params_summary,
                    "user_question": user_question,
                    "temperature": temperature,
                    "response": response,
                    "system_prompt": system_prompt,
                    "context": _json_safe(context),
                    "stock_code": stock_info.get("code", ""),
                    "stock_name": stock_info.get("name", ""),
                    "requested_date": stock_info.get("requested_date"),
                    "actual_date": stock_info.get("actual_date"),
                    "session_id": session_id,
                    "followups": []
                }
                st.session_state.ai_history.append(entry)
                st.session_state.ai_last = entry
            except Exception as exc:
                st.error(f"请求失败: {exc}")
                return

    if st.session_state.ai_last:
        st.markdown("### ✅ 最新解读")
        stock_label = f"{st.session_state.ai_last.get('stock_code', '')} {st.session_state.ai_last.get('stock_name', '')}".strip()
        date_label = st.session_state.ai_last.get("actual_date") or st.session_state.ai_last.get("requested_date") or "未知日期"
        st.caption(
            f"{st.session_state.ai_last['ts']} | "
            f"{st.session_state.ai_last['focus']} | "
            f"{st.session_state.ai_last['style']} | "
            f"{st.session_state.ai_last.get('advice_mode', '')} | "
            f"{st.session_state.ai_last.get('preset_mode', '')} | "
            f"temp {st.session_state.ai_last['temperature']:.1f} | "
            f"标的: {stock_label or '未知'} | "
            f"日期: {date_label} | "
            f"会话: {st.session_state.ai_last.get('session_id', '--')}"
        )
        st.write(st.session_state.ai_last["response"])

        st.markdown("### 💬 继续追问")
        st.caption("追问会基于“最新解读”的同一份数据快照与提示词继续回答。")
        st.caption(f"当前会话: {st.session_state.ai_last.get('session_id', '--')}")
        followup_mode = st.radio(
            "追问模式",
            ["严格", "平衡", "开放"],
            horizontal=True,
            help="严格=仅用已有数据；平衡=允许有限推断；开放=完全开放对话，不受数据与格式限制。",
        )
        followup = st.text_input("基于当前解读继续提问", key="ai_followup")
        followup_btn = st.button("发送追问")
        if followup_btn:
            if not followup.strip():
                st.warning("请输入追问内容。")
            else:
                with st.spinner("正在追问..."):
                    try:
                        follow_prompt = _build_followup_prompt(
                            context=st.session_state.ai_last["context"],
                            focus=st.session_state.ai_last["focus"],
                            constraints=st.session_state.ai_last["constraints"],
                            previous_answer=st.session_state.ai_last["response"],
                            followup=followup,
                            followup_mode=followup_mode,
                            advice_mode=st.session_state.ai_last.get("advice_mode", ""),
                        )
                        follow_response = call_deepseek(
                            api_key=api_key,
                            system_prompt=st.session_state.ai_last["system_prompt"],
                            user_prompt=follow_prompt,
                            temperature=st.session_state.ai_last.get("temperature", 0.2),
                            max_tokens=1200,
                        )
                        st.session_state.ai_last["followups"].append(
                            {
                                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "q": followup,
                                "a": follow_response,
                                "mode": followup_mode,
                            }
                        )
                    except Exception as exc:
                        st.error(f"追问失败: {exc}")
                        return

        if st.session_state.ai_last["followups"]:
            st.markdown("#### 🧵 追问记录")
            recent_followups = st.session_state.ai_last["followups"][-5:]
            recent_followups = sorted(recent_followups, key=lambda x: x.get("ts", ""), reverse=True)
            for item in recent_followups:
                mode_note = f" ({item.get('mode', '严格')})" if item.get("mode") else ""
                ts_note = f"{item.get('ts', '')} | " if item.get("ts") else ""
                st.markdown(f"**Q**: {ts_note}{item['q']}{mode_note}")
                st.markdown(f"**A**: {item['a']}")

    if st.session_state.ai_history:
        with st.expander("🗂️ 历史解读", expanded=False):
            for item in reversed(st.session_state.ai_history[-5:]):
                stock_label = f"{item.get('stock_code', '')} {item.get('stock_name', '')}".strip()
                date_label = item.get("actual_date") or item.get("requested_date") or "未知日期"
                st.markdown(
                    f"**{item['ts']} | {item['focus']} | {item['style']} | "
                    f"{item.get('advice_mode', '')} | {item.get('preset_mode', '')} | "
                    f"{stock_label or '未知标的'} | "
                    f"{date_label} | 会话 {item.get('session_id', '--')}**"
                )
                if item.get("user_question"):
                    st.caption(f"补充问题: {item['user_question']}")
                st.write(item["response"])


def _build_context(
    news_df: Optional[pd.DataFrame] = None,
    include_news: bool = False
) -> Dict:
    df = st.session_state.df
    analysis = st.session_state.all_analysis
    quality = st.session_state.quality_report
    stock_code = st.session_state.get("last_stock_code", "")

    stock_provider = get_stock_provider()
    stock_name = stock_code
    try:
        res = stock_provider.search(stock_code, limit=1)
        if not res.empty:
            stock_name = res.iloc[0]["名称"]
    except Exception:
        pass

    actual_date = df.attrs.get("actual_date")
    requested_date = df.attrs.get("requested_date")

    tick_context = st.session_state.get("tick_context")
    daily_window = 20
    analysis_day = _parse_date_value(actual_date or requested_date) or datetime.now().date()
    daily_df = _load_daily_history(stock_code, analysis_day, daily_window)
    exclude_partial_daily = (
        analysis_day == datetime.now().date() and datetime.now().time() < time(15, 5)
    )
    if exclude_partial_daily:
        daily_df = _drop_partial_daily(daily_df, analysis_day)
    daily_series = _build_daily_series(daily_df, daily_window)
    daily_trend = _build_daily_trend(daily_df, daily_window)
    if daily_trend:
        daily_trend["partial_excluded"] = exclude_partial_daily
    price_range_analysis = PriceRangeAnalyzer(
        pivot_window=1,
        atr_period=14,
        atr_multiplier=2.0,
        donchian_window=daily_window,
        ema_window=20,
    ).analyze(daily_df)
    today_partial = _build_today_partial(
        df=st.session_state.df,
        timeseries=analysis.get("timeseries", {}),
        indicators=analysis.get("indicators", {}),
        tick_context=tick_context,
        analysis_day=analysis_day,
    )

    flows = analysis.get("flows", {})
    timeseries = analysis.get("timeseries", {})
    indicators = analysis.get("indicators", {})
    anomalies = analysis.get("anomalies", {})
    tick_available = bool(tick_context and tick_context.get("flow_summary"))
    if tick_available:
        flows = tick_context["flow_summary"]

    large_order_count = anomalies.get("summary", {}).get("large_order_count", 0)
    if tick_available:
        large_order_count = flows.get("large_order_count", large_order_count)

    top_orders = []
    if tick_context and tick_context.get("large_orders_top5"):
        for o in tick_context["large_orders_top5"]:
            top_orders.append(
                {
                    "time": str(o.get("time", "")),
                    "amount": float(o.get("amount", 0)),
                    "price": float(o.get("price", 0)),
                    "type": o.get("type", "未知"),
                    "ratio": float(o.get("ratio", 0)),
                }
            )
    else:
        large_orders = anomalies.get("large_orders", [])
        large_orders_sorted = sorted(large_orders, key=lambda x: x.get("amount", 0), reverse=True)
        top_orders = [
            {
                "time": str(o.get("time", "")),
                "amount": float(o.get("amount", 0)),
                "price": float(o.get("price", 0)),
                "type": o.get("type", "未知"),
                "ratio": float(o.get("ratio", 0)),
            }
            for o in large_orders_sorted[:3]
        ]

    limit_lock = _calc_limit_lock(timeseries)
    direction_reliability = _calc_direction_reliability(tick_context, limit_lock)

    buy_amount = None
    sell_amount = None
    neutral_amount = None
    net_inflow = None
    trade_count = None
    buy_count = None
    sell_count = None
    neutral_count = None
    ofi = None
    if tick_available:
        buy_amount = flows.get("buy_amount")
        sell_amount = flows.get("sell_amount")
        neutral_amount = flows.get("neutral_amount")
        net_inflow = flows.get("net_inflow")
        neutral_ratio = flows.get("neutral_ratio")
        direction_coverage = flows.get("direction_coverage")
        trade_count = flows.get("trade_count")
        buy_count = flows.get("buy_count")
        sell_count = flows.get("sell_count")
        neutral_count = flows.get("neutral_count")
        buy_count_ratio = flows.get("buy_count_ratio")
        sell_count_ratio = flows.get("sell_count_ratio")
        avg_buy_amount = flows.get("avg_buy_amount")
        avg_sell_amount = flows.get("avg_sell_amount")
        ofi = flows.get("ofi")
    else:
        large_buy = flows.get("large_buy_amount", 0) or 0
        retail_buy = flows.get("retail_buy_amount", 0) or 0
        large_sell = flows.get("large_sell_amount", 0) or 0
        retail_sell = flows.get("retail_sell_amount", 0) or 0
        buy_amount = large_buy + retail_buy
        sell_amount = large_sell + retail_sell
        net_inflow = flows.get("large_order_net_inflow", 0) + flows.get("retail_net_inflow", 0)
        denom = buy_amount + sell_amount
        ofi = (buy_amount - sell_amount) / denom if denom > 0 else None
        neutral_ratio = None
        direction_coverage = None
        buy_count_ratio = None
        sell_count_ratio = None
        avg_buy_amount = None
        avg_sell_amount = None

    flow_quality = flows.get("flow_quality", {})
    flow_quality = {
        **flow_quality,
        "direction_reliability": direction_reliability,
        "limit_lock": limit_lock,
        "inferred_ratio": tick_context.get("inferred_ratio") if tick_available else None,
        "neutral_note": "中性盘=方向无法判定的成交",
    }

    flow_block = {
        "buy_amount": buy_amount,
        "sell_amount": sell_amount,
        "neutral_amount": neutral_amount,
        "neutral_ratio": neutral_ratio,
        "direction_coverage": direction_coverage,
        "buy_count_ratio": buy_count_ratio,
        "sell_count_ratio": sell_count_ratio,
        "avg_buy_amount": avg_buy_amount,
        "avg_sell_amount": avg_sell_amount,
        "net_inflow": net_inflow,
        "ofi": ofi,
        "trade_count": trade_count,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "neutral_count": neutral_count,
        "quality": flow_quality,
    }

    tick_window_series = []
    window_minutes = None
    if tick_available:
        tick_window_series, window_minutes = _build_tick_window_series(tick_context, limit=40)
    anomaly_highlights = _build_anomaly_highlights(tick_context, tick_window_series, anomalies)
    largest_trades_raw = tick_context.get("largest_trades_raw", []) if tick_context else []
    readable_summary = _build_readable_summary(
        daily_trend,
        price_range_analysis,
        flow_block,
        anomaly_highlights,
        largest_trades_raw,
        today_partial,
    )

    data_scope = {
        "date": actual_date or requested_date,
        "source": "tick" if tick_available else "minute",
        "tick_available": tick_available,
        "window_minutes": window_minutes,
        "market_hours_only": True if tick_available else None,
        "quality_flags": tick_context.get("quality_flags", []) if tick_available else [],
        "daily_window_days": daily_window,
        "daily_partial_excluded": exclude_partial_daily,
        "price_range_methods": price_range_analysis.get("methods_applied", [])
        if price_range_analysis
        else [],
    }

    context = {
        "data_scope": data_scope,
        "stock": {
            "code": stock_code,
            "name": stock_name,
            "requested_date": requested_date,
            "actual_date": actual_date,
            "data_quality_score": quality.get("quality_score", 0),
        },
        "price": {
            "open": timeseries.get("open_price"),
            "close": timeseries.get("close_price"),
            "high": timeseries.get("high_price"),
            "low": timeseries.get("low_price"),
            "change": timeseries.get("price_change"),
            "change_pct": timeseries.get("price_change_pct"),
            "amplitude": timeseries.get("amplitude"),
        },
        "liquidity": {
            "turnover_total": timeseries.get("turnover_total"),
            "volume_total": timeseries.get("volume_total"),
            "avg_price": timeseries.get("avg_price"),
        },
        "flow": flow_block,
        "indicators": {
            "vwap": indicators.get("vwap"),
            "price_vs_vwap": indicators.get("price_vs_vwap"),
            "minute_ma5": indicators.get("ma5"),
            "minute_ma10": indicators.get("ma10"),
            "is_above_vwap": indicators.get("is_above_vwap"),
            "is_above_minute_ma5": indicators.get("is_above_ma5"),
            "is_above_minute_ma10": indicators.get("is_above_ma10"),
        },
        "anomalies": {
            "large_order_count": large_order_count,
            "price_spike_count": anomalies.get("summary", {}).get("price_spike_count", 0),
            "volume_surge_count": anomalies.get("summary", {}).get("volume_surge_count", 0),
            "top_large_orders": top_orders,
        },
        "daily_series": daily_series,
        "daily_trend": daily_trend,
        "price_range_analysis": price_range_analysis,
        "today_partial": today_partial,
        "readable_summary": readable_summary,
        "anomaly_highlights": anomaly_highlights,
    }
    if tick_context:
        tick_summary = tick_context.get("tick_ai_summary", {})
        if tick_summary:
            context["tick_summary"] = tick_summary
        if tick_window_series:
            context["tick_window_series"] = tick_window_series
        context["tick_meta"] = {
            "quality_flags": tick_context.get("quality_flags", []),
            "burst_windows": tick_context.get("burst_windows", []),
            "anomaly_notes": tick_context.get("anomaly_notes", []),
            "auction_summary": tick_context.get("auction_summary", {}),
            "auction_trades": tick_context.get("auction_trades", []),
            "close_auction_summary": tick_context.get("close_auction_summary", {}),
            "close_auction_trades": tick_context.get("close_auction_trades", []),
            "volume_unit": tick_context.get("volume_unit"),
            "inferred_ratio": tick_context.get("inferred_ratio"),
        }
        if largest_trades_raw:
            context["largest_trades_raw"] = largest_trades_raw
    if include_news:
        context["news"] = _build_news_payload(news_df, stock_name)
    return context


def _build_prompts(
    context: Dict,
    focus: str,
    style: str,
    advice_mode: str,
    preset_mode: str,
    only_data: bool,
    highlight_numbers: bool,
    add_watchlist: bool,
    user_question: str
) -> Tuple[str, str]:
    constraints = []
    if advice_mode == "分析模式":
        constraints.append("操作建议：仅做分析，不输出具体操作指令")
    elif advice_mode == "结论模式":
        constraints.append("操作建议：可给出方向性结论，但不给直接操作指令")
    else:
        constraints.append("操作建议：允许给出条件触发建议，不做收益承诺")
    constraints.append("输出分两块：事实描述(按规则，不推断) + 自由分析(可跨日推演，不受事实规则限制)")
    if only_data:
        constraints.append("事实描述：仅基于提供的数据，不要编造")
    if highlight_numbers:
        constraints.append("事实描述：必须引用关键数值作为依据")
    if add_watchlist:
        constraints.append("自由分析：给出可观察的触发条件或关键变量")
    constraints.append("事实描述：引用数值时不要输出字段名或 JSON 路径，改用自然语言表述")
    if context.get("readable_summary"):
        constraints.append("事实描述：优先使用 readable_summary 的表述与数值")
    constraints.append("事实描述：若为盘中快照，价格表述用“盘中最新价/截至时间”，不要称“当日收盘”")
    constraints.append("事实描述：均线高低关系基于日线收盘口径，不与盘中价格混用")
    constraints.append("事实描述：若 daily_trend.last_date 存在，日线口径需标注该日期")
    constraints.append("事实描述：盘中均线需明确为“分钟MA”，否则默认指日线MA")
    constraints.append("事实描述：提到 MA/VWAP/ATR/区间时需带上数值（如 MA5(71.89)）")
    constraints.append("自由分析：可结合 daily_trend/daily_series 与当日资金变化做短期推演")
    constraints.append("自由分析：涉及操作建议需说明A股T+1，新开仓当天不可卖出")
    if not context.get("daily_series"):
        constraints.append("事实描述：若日线数据为空，需明确说明趋势依据不足")
    if context.get("today_partial", {}).get("scope", {}).get("is_partial"):
        constraints.append("事实描述：today_partial 为盘中快照，不能与日线量能直接对比")
    flow_quality = context.get("flow", {}).get("quality", {})
    if flow_quality.get("direction_reliability") == "low" or flow_quality.get("limit_lock"):
        constraints.append("事实描述：买卖盘方向可靠性偏低，优先描述成交节奏与量能")
    if context.get("daily_trend"):
        constraints.append(
            "事实描述：均线高低关系必须使用 daily_trend 中已计算的高低关系与偏离百分比，"
            "不要自行比较均线数值"
        )
    if context.get("flow", {}).get("direction_coverage") is not None:
        constraints.append("事实描述：若方向覆盖率偏低，需说明买卖盘无法覆盖全部成交额")
    if context.get("readable_summary", {}).get("anomalies"):
        constraints.append("事实描述：关键异动需逐条引用 readable_summary.anomalies 中的条目")
    if context.get("largest_trades_raw"):
        constraints.append("事实描述：largest_trades_raw 为全天原始成交额最大榜单，包含中性盘，不代表方向强弱")
    if preset_mode == "range":
        constraints.append("事实描述：价格区间必须使用 price_range_analysis 给出，并注明方法")
        constraints.append("事实描述：若方法区间不一致，需说明分歧与共识区间")
        constraints.append("事实描述：如有 consensus_view，优先给出共识区间，再说明方法差异")
        if not context.get("price_range_analysis"):
            constraints.append("事实描述：价格区间数据缺失时，明确说明无法给出区间")
    news_payload = context.get("news")
    if news_payload is not None:
        if news_payload.get("has_news"):
            constraints.append("事实描述：如有新闻条目，仅基于新闻内容描述潜在影响")
        else:
            constraints.append("事实描述：若未提供新闻数据需明确说明无法判断新闻影响")

    style_map = {
        "简洁": "4-6条要点，句子短",
        "专业": "分小标题+要点",
        "交易员风格": "强调盘中节奏、资金方向，语气紧凑"
    }

    focus_map = {
        "资金流向解读": [
            "主力/散户净流入方向与强度",
            "大单占比与主力买卖额差异",
            "累计净流入是否持续"
        ],
        "盘中趋势与节奏": [
            "开收/高低位置与振幅",
            "VWAP/均线偏离与盘中节奏",
            "上涨分钟占比"
        ],
        "风险与异动": [
            "价格跳跃次数与方向",
            "成交量异常放大",
            "大单异常集中时段"
        ],
        "主力行为复盘": [
            "主力净流入与价格走势是否一致",
            "主力买卖额差异",
            "主力占比与关键时段"
        ],
    }

    system_prompt = (
        "你是专注于A股资金流与趋势判断的助手，只能围绕交易与金融话题回答。"
        "回复必须结构化，语言简洁，避免发散。"
    )

    output_format = [
        "事实描述(行情与数据，按规则，不推断)",
        "自由分析(可跨日推演，结合短期/中期节奏给出框架)",
    ]

    user_prompt = {
        "分析目标": focus,
        "输出风格": style_map.get(style, style),
        "输出模式": advice_mode,
        "约束": constraints,
        "重点关注": focus_map.get(focus, []),
        "补充问题": user_question or "无",
        "数据快照": _json_safe(context),
        "输出格式": output_format,
    }

    return system_prompt, json.dumps(user_prompt, ensure_ascii=False, indent=2)


def _summarize_settings(
    focus: str,
    style: str,
    advice_mode: str,
    preset_mode: str,
    only_data: bool,
    highlight_numbers: bool,
    add_watchlist: bool,
    user_question: str
) -> List[str]:
    tags = [focus, style, advice_mode, preset_mode]
    if only_data:
        tags.append("仅基于数据")
    if highlight_numbers:
        tags.append("强调数值")
    if add_watchlist:
        tags.append("给观察清单")
    if user_question:
        tags.append("含补充问题")
    return tags


def _build_followup_prompt(
    context: Dict,
    focus: str,
    constraints: List[str],
    previous_answer: str,
    followup: str,
    followup_mode: str,
    advice_mode: str
) -> str:
    focus_map = {
        "资金流向解读": ["主力/散户净流入", "累计净流入", "大单占比"],
        "盘中趋势与节奏": ["盘中节奏", "VWAP/均线偏离", "振幅"],
        "风险与异动": ["价格跳跃", "成交量激增", "大单异常"],
        "主力行为复盘": ["主力净流入与价格一致性", "主力买卖额差异"],
    }

    mode_rules = {
        "严格": [
            "仅基于已有数据快照回答，不引入新信息",
            "必须引用关键数据或指标作为依据",
            "无法判断时明确说明原因",
        ],
        "平衡": [
            "以已有数据为主，可做有限推断并明确为推断",
            "尽量引用关键数据，必要时给出合理假设",
            "不扩展到无关话题",
        ],
        "开放": [
            "完全开放对话，不受已有数据或格式约束",
            "可自由发挥观点与推演，可忽略或仅参考数据快照",
        ],
    }

    payload = {
        "任务": "基于已有解读继续回答追问，保持金融交易语境",
        "分析目标": focus,
        "约束": constraints,
        "追问模式": followup_mode,
        "追问规则": mode_rules.get(followup_mode, mode_rules["严格"]),
        "输出模式": advice_mode or "分析模式",
        "重点关注": focus_map.get(focus, []),
        "已有解读": previous_answer,
        "追问": followup,
        "数据快照": context,
        "输出要求": [
            "直接回答问题",
            "事实描述引用关键数据",
            "不扩展到无关话题",
            "保持两块结构：事实描述 + 自由分析",
        ],
    }
    if followup_mode == "开放":
        payload["任务"] = "自由回答追问，可使用或忽略数据快照与已有解读"
        payload["约束"] = []
        payload["输出模式"] = "自由对话"
        payload["重点关注"] = []
        payload["输出要求"] = ["直接回答问题"]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)
