"""
YFinance 数据源封装（用于美股/港股/全球指数）
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from .base import StockDataProvider


class YFinanceProvider(StockDataProvider):
    def __init__(self) -> None:
        try:
            import yfinance as yf
        except Exception as exc:
            raise RuntimeError("缺少依赖 yfinance，请先安装") from exc
        self.yf = yf

    def get_stock_info(self, code: str) -> dict:
        symbol = self._normalize_symbol(code)
        return {"code": code, "symbol": symbol}

    def get_realtime_data(self, code: str) -> pd.DataFrame:
        symbol = self._normalize_symbol(code)
        ticker = self.yf.Ticker(symbol)
        df = ticker.history(period="1d", interval="1m")
        return self._normalize_history(df)

    def get_tick_data(self, code: str, date_str: str = None) -> pd.DataFrame:
        symbol = self._normalize_symbol(code)
        ticker = self.yf.Ticker(symbol)
        if date_str:
            start = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            end = start
            df = ticker.history(start=start, end=end, interval="1m")
        else:
            df = ticker.history(period="1d", interval="1m")
        return self._normalize_history(df)

    def get_history_data(self, code: str, start_date: date, end_date: date) -> pd.DataFrame:
        symbol = self._normalize_symbol(code)
        ticker = self.yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, interval="1d")
        return self._normalize_history(df)

    def get_market_snapshot(self, symbol: str) -> dict:
        ticker = self.yf.Ticker(symbol)
        df = ticker.history(period="2d", interval="1d")
        if df.empty:
            return {"symbol": symbol, "price": None}
        df = df.dropna()
        if len(df) == 1:
            latest = df.iloc[-1]
            prev_close = latest.get("Open")
        else:
            latest = df.iloc[-1]
            prev_close = df.iloc[-2].get("Close")

        price = latest.get("Close")
        change = None
        pct = None
        if price is not None and prev_close:
            change = price - prev_close
            pct = change / prev_close * 100

        return {
            "symbol": symbol,
            "price": price,
            "change": change,
            "pct": pct,
            "open": latest.get("Open"),
            "high": latest.get("High"),
            "low": latest.get("Low"),
            "volume": latest.get("Volume"),
        }

    def _normalize_symbol(self, code: str) -> str:
        if "." in code or code.startswith("^"):
            return code
        if code.isdigit():
            suffix = ".SS" if code.startswith("6") else ".SZ"
            return f"{code}{suffix}"
        return code

    def _normalize_history(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        df = df.reset_index()
        df = df.rename(columns={
            "Datetime": "时间",
            "Date": "时间",
            "Open": "开盘",
            "High": "最高",
            "Low": "最低",
            "Close": "收盘",
            "Volume": "成交量",
        })
        df["成交额(元)"] = df.get("成交量", 0) * df.get("收盘", 0)
        return df
