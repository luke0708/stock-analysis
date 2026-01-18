"""
Background data prefetch helpers.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict

import akshare as ak

from stock_analysis.analysis.market_hotspot import MarketHotspotAnalyzer
from stock_analysis.data.news_provider import StockNewsProvider

_cache_lock = threading.Lock()
_cache: Dict[str, Any] = {}
_started = False


def start_market_prefetch() -> None:
    global _started
    if _started:
        return
    _started = True
    thread = threading.Thread(target=_prefetch_market_data, daemon=True)
    thread.start()


def get_prefetched_data() -> Dict[str, Any]:
    with _cache_lock:
        return dict(_cache)


def _prefetch_market_data() -> None:
    data: Dict[str, Any] = {}
    try:
        data["indices_df"] = ak.stock_zh_index_spot_sina()
    except Exception:
        pass

    try:
        data["hot_industries"] = MarketHotspotAnalyzer.get_hot_industries(top_n=10)
    except Exception:
        pass

    try:
        data["sentiment"] = MarketHotspotAnalyzer.analyze_market_sentiment()
    except Exception:
        pass

    try:
        data["news"] = StockNewsProvider.get_market_news(limit=6)
    except Exception:
        pass

    data["ts"] = datetime.now()

    with _cache_lock:
        _cache.update(data)
