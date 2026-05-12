"""
回填 labels 表的 T+1/T+5/T+20 涨跌幅（占位实现）。

未来用法：
    python -m stock_analysis.ml.label_backfiller --since 2025-01-01

实现思路：
- 读取 trend_signal_snapshot 中所有 (code, analysis_date)
- 对每条调 CacheStore.get_daily 取 T0/T+1/T+5/T+20 收盘价
- 写入 labels 表（upsert_label）
"""
from __future__ import annotations


def main() -> None:
    raise NotImplementedError("本轮仅搭框架，回填逻辑留待数据累积后实现")


if __name__ == "__main__":
    main()
