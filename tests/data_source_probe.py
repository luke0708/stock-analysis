"""
数据源下载探测脚本（不改现有结构，仅用于评估替代源可用性）

测试内容：
1) tick / 分钟级数据：get_tick_data(code, date) 是否返回有效数据与时间范围
2) 实时数据：get_realtime_data(code) 是否可用、字段是否完整
3) 历史日线：get_history_data(code, start_date, end_date) 是否可用

使用示例：
  python tests/data_source_probe.py --code 600519 --date 20260121 --providers akshare,tushare
  python tests/data_source_probe.py --providers akshare --skip-realtime
"""
import argparse
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.data.providers.tushare_provider import TushareProvider
from stock_analysis.data.providers.yfinance_provider import YFinanceProvider


def _parse_date(value: str) -> date:
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {value}")


def _pick_time_col(df: pd.DataFrame, candidates) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _log_df_summary(name: str, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        logging.warning("%s: 数据为空", name)
        return

    logging.info("%s: 行数=%s 列数=%s", name, len(df), len(df.columns))
    logging.info("%s: 列=%s", name, list(df.columns))

    time_col = _pick_time_col(df, ["时间", "date", "日期", "trade_date", "datetime"])
    if time_col:
        try:
            series = pd.to_datetime(df[time_col], errors="coerce").dropna()
            if not series.empty:
                logging.info(
                    "%s: 时间范围=%s ~ %s",
                    name,
                    series.min().strftime("%Y-%m-%d %H:%M:%S"),
                    series.max().strftime("%Y-%m-%d %H:%M:%S"),
                )
        except Exception as exc:
            logging.warning("%s: 时间范围解析失败: %s", name, exc)

    if hasattr(df, "attrs") and df.attrs:
        attrs_keys = [
            "actual_date",
            "requested_date",
            "fallback_date",
            "fallback_reason",
            "source_granularity",
            "imported_tick",
        ]
        attrs = {k: df.attrs.get(k) for k in attrs_keys if k in df.attrs}
        if attrs:
            logging.info("%s: attrs=%s", name, attrs)


def _build_provider(name: str):
    try:
        if name == "akshare":
            return AkShareProvider()
        if name == "tushare":
            return TushareProvider()
        if name == "yfinance":
            return YFinanceProvider()
    except Exception as exc:
        logging.error("%s: 初始化失败: %s", name, exc)
        return None
    logging.error("未知数据源: %s", name)
    return None


def _probe_tick(provider, code: str, date_str: str) -> None:
    fetch = getattr(provider, "get_tick_data", None)
    if not callable(fetch):
        logging.info("tick: 当前数据源未实现 get_tick_data")
        return
    try:
        df = fetch(code, date_str)
        _log_df_summary("tick", df)
    except Exception as exc:
        logging.error("tick: 拉取失败: %s", exc)


def _probe_realtime(provider, code: str) -> None:
    try:
        df = provider.get_realtime_data(code)
        _log_df_summary("realtime", df)
    except Exception as exc:
        logging.error("realtime: 拉取失败: %s", exc)


def _probe_history(provider, code: str, start_date: date, end_date: date) -> None:
    try:
        df = provider.get_history_data(code, start_date=start_date, end_date=end_date)
        _log_df_summary("history", df)
    except Exception as exc:
        logging.error("history: 拉取失败: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="数据源下载能力探测脚本")
    parser.add_argument("--code", default="600519", help="股票代码，如 600519")
    parser.add_argument("--date", default=date.today().strftime("%Y%m%d"), help="日期，如 20260121")
    parser.add_argument("--history-days", type=int, default=20, help="历史窗口天数")
    parser.add_argument(
        "--providers",
        default="akshare,tushare",
        help="逗号分隔的数据源: akshare,tushare,yfinance",
    )
    parser.add_argument("--skip-tick", action="store_true", help="跳过 tick/分钟拉取")
    parser.add_argument("--skip-realtime", action="store_true", help="跳过实时拉取")
    parser.add_argument("--skip-history", action="store_true", help="跳过历史日线拉取")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    target_date = _parse_date(args.date)
    start_date = target_date - timedelta(days=args.history_days)

    providers = [name.strip() for name in args.providers.split(",") if name.strip()]
    for name in providers:
        logging.info("==== 数据源: %s ====", name)
        provider = _build_provider(name)
        if provider is None:
            continue
        if not args.skip_tick:
            _probe_tick(provider, args.code, target_date.strftime("%Y%m%d"))
        if not args.skip_realtime:
            _probe_realtime(provider, args.code)
        if not args.skip_history:
            _probe_history(provider, args.code, start_date, target_date)


if __name__ == "__main__":
    main()
