"""
全球市场概览页面（YFinance）
"""
from __future__ import annotations

from datetime import datetime
import time
from typing import Dict, List

import pandas as pd
import streamlit as st

GLOBAL_MARKETS = [
    {"name": "标普500", "symbol": "^GSPC"},
    {"name": "纳斯达克", "symbol": "^IXIC"},
    {"name": "道琼斯", "symbol": "^DJI"},
    {"name": "恒生指数", "symbol": "^HSI"},
    {"name": "日经225", "symbol": "^N225"},
    {"name": "德国DAX", "symbol": "^GDAXI"},
]

A_INDEX_MARKETS = [
    {"name": "上证指数", "symbol": "上证指数"},
    {"name": "深证成指", "symbol": "深证成指"},
    {"name": "创业板指", "symbol": "创业板指"},
]


def show_global_markets():
    st.header("🌍 全球市场概览")
    st.caption("可切换数据源并查看测速结果（全球市场优先推荐 YFinance）")

    source = st.radio(
        "数据源选择",
        ["YFinance（全球）", "AkShare（仅A股指数）"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if source.startswith("YFinance"):
        try:
            import yfinance as yf
        except Exception:
            st.warning("缺少依赖 yfinance，请先在虚拟环境中安装。")
            st.code("pip install yfinance", language="bash")
            return

        symbols = [m["symbol"] for m in GLOBAL_MARKETS]
        start_ts = time.perf_counter()
        snapshots = _fetch_snapshots(yf, symbols)
        elapsed = time.perf_counter() - start_ts
        markets = GLOBAL_MARKETS
    else:
        try:
            import akshare as ak
        except Exception:
            st.warning("缺少依赖 akshare，请先在虚拟环境中安装。")
            st.code("pip install akshare", language="bash")
            return

        start_ts = time.perf_counter()
        snapshots = _fetch_a_index_snapshots(ak)
        elapsed = time.perf_counter() - start_ts
        markets = A_INDEX_MARKETS

    success_count = sum(1 for m in markets if snapshots.get(m["symbol"], {}).get("price") is not None)
    st.caption(f"数据源：{source} | 耗时: {elapsed:.2f}s | 成功: {success_count}/{len(markets)}")

    cols = st.columns(3)
    for idx, market in enumerate(markets):
        data = snapshots.get(market["symbol"], {})
        price = _fmt_number(data.get("price"))
        change = _fmt_number(data.get("change"))
        pct = _fmt_number(data.get("pct"))
        label = market["name"]

        with cols[idx % 3]:
            st.metric(label, price, f"{change} ({pct}%)")

    st.caption(f"最后更新: {datetime.now().strftime('%H:%M:%S')}")


@st.cache_data(ttl=300)
def _fetch_snapshots(yf, symbols: List[str]) -> Dict[str, Dict]:
    try:
        df = yf.download(
            tickers=" ".join(symbols),
            period="2d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            threads=True,
            progress=False,
        )
    except Exception:
        df = pd.DataFrame()

    snapshots: Dict[str, Dict] = {}
    if df.empty:
        return snapshots

    if isinstance(df.columns, pd.MultiIndex):
        for symbol in symbols:
            if symbol not in df.columns.get_level_values(0):
                continue
            sub = df[symbol].dropna()
            snapshots[symbol] = _extract_snapshot(sub)
    else:
        snapshots[symbols[0]] = _extract_snapshot(df.dropna())

    return snapshots


def _extract_snapshot(df: pd.DataFrame) -> Dict:
    if df.empty:
        return {}
    df = df.dropna()
    latest = df.iloc[-1]
    prev_close = df.iloc[-2]["Close"] if len(df) > 1 else latest.get("Open")

    price = latest.get("Close")
    change = None
    pct = None
    if price is not None and prev_close:
        change = price - prev_close
        pct = change / prev_close * 100

    return {
        "price": price,
        "change": change,
        "pct": pct,
        "high": latest.get("High"),
        "low": latest.get("Low"),
        "open": latest.get("Open"),
        "volume": latest.get("Volume"),
    }


@st.cache_data(ttl=300)
def _fetch_a_index_snapshots(ak) -> Dict[str, Dict]:
    try:
        df = ak.stock_zh_index_spot_sina()
    except Exception:
        df = pd.DataFrame()

    snapshots: Dict[str, Dict] = {}
    if df.empty:
        return snapshots

    for market in A_INDEX_MARKETS:
        row = df[df["名称"] == market["symbol"]]
        if row.empty:
            continue
        r = row.iloc[0]
        snapshots[market["symbol"]] = {
            "price": r.get("最新价"),
            "change": r.get("涨跌额"),
            "pct": r.get("涨跌幅"),
            "high": r.get("最高"),
            "low": r.get("最低"),
            "open": r.get("今开", r.get("开盘")),
            "volume": r.get("成交量"),
            "amount": r.get("成交额"),
        }

    return snapshots


def _fmt_number(value):
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "--"
