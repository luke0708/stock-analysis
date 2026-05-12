"""
导出训练集 CLI（占位实现，未来扩展）。

未来用法：
    python -m stock_analysis.ml.export_training_set \\
        --since 2025-01-01 --until 2026-04-30 \\
        --features trend_signal,flow_summary \\
        --output train.parquet

数据需求：
- 本项目 stock_cache.db 中累积的 L2 + L4 快照（需 6-12 个月积累）
- 若需扩到 5000 只 × 5 年的大规模历史，需要 stockdb 提供批量接口（见 CLAUDE.md）
"""
from __future__ import annotations


def main() -> None:
    raise NotImplementedError("本轮仅搭框架，导出 CLI 留待数据累积后实现")


if __name__ == "__main__":
    main()
