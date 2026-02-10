"""Quick local demo for trend signal + panel mapping.

Run:
  python3 '股票分析算法/demo_run.py'
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from trend_signal import analyze_trend_signal
from ui_mapping import build_display_panels


def _build_synthetic_daily() -> pd.DataFrame:
    """Build a reproducible sample daily series ending near the provided case."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2025-11-10", periods=65, freq="B")
    prices = [33.5]
    for _ in range(64):
        prices.append(prices[-1] * (1 + rng.normal(0.0012, 0.012)))

    # Force last values near the user sample context.
    prices[-3] = 37.19
    prices[-2] = 38.11
    prices[-1] = 38.65

    close = np.array(prices)
    open_ = close * (1 + rng.normal(0, 0.004, len(close)))
    high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.01, len(close)))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.01, len(close)))
    volume = rng.integers(2_000_000, 8_000_000, len(close))
    volume[-1] = 6_017_100
    amount = close * volume

    return pd.DataFrame(
        {
            "date": dates,
            "open": np.round(open_, 2),
            "high": np.round(high, 2),
            "low": np.round(low, 2),
            "close": np.round(close, 2),
            "volume": volume,
            "amount": np.round(amount, 0),
        }
    )


def _build_case_payload() -> tuple[dict, dict, dict]:
    raw_result = {
        "code": "601899",
        "name": "紫金矿业",
        "sentiment_score": 62,
        "trend_prediction": "震荡",
        "operation_advice": "观望",
        "confidence_level": "中",
        "change_pct": 3.93,
        "current_price": 38.65,
        "analysis_summary": "紫金矿业今日呈现显著的放量反弹态势（量比4.1）...",
        "key_points": "均线缠绕待突破,放量反弹信号",
        "risk_warning": "需警惕大宗商品价格波动及海外矿区地缘政治风险。",
        "buy_reason": "低乖离率但均线未完全转多，建议等待确认。",
        "data_sources": "交易所实时行情、Tavily深度搜索、机构研报汇总",
        "search_performed": True,
        "market_snapshot": {
            "date": "2026-02-09",
            "close": "38.65",
            "pct_chg": "3.93%",
            "volume_ratio": 4.1,
        },
        "dashboard": {
            "core_conclusion": {
                "one_sentence": "放量反弹但均线尚未多头排列，建议等待回踩MA5确认支撑。",
                "signal_type": "🟡持有观望",
                "position_advice": {
                    "no_position": "暂不追涨，等待回踩38.25附近企稳。",
                    "has_position": "关注39.44压力，不能突破可减仓。",
                },
            },
            "data_perspective": {
                "trend_status": {
                    "ma_alignment": "MA10(39.44) > MA20(38.71) > MA5(38.25)，尚未形成多头排列。",
                    "trend_score": 55,
                },
                "price_position": {
                    "current_price": 38.65,
                    "ma5": 38.25,
                    "ma10": 39.44,
                    "ma20": 38.71,
                    "bias_ma5": 1.05,
                    "bias_status": "安全",
                    "support_level": 38.25,
                    "resistance_level": 39.44,
                },
                "volume_analysis": {
                    "volume_ratio": 4.1,
                    "volume_status": "放量",
                    "turnover_rate": 0.29,
                    "volume_meaning": "量比4.1属于巨量反弹。",
                },
                "chip_structure": {
                    "profit_ratio": 80.5,
                    "avg_cost": 32.36,
                    "concentration": 38.39,
                    "chip_health": "一般",
                },
            },
            "intelligence": {
                "latest_news": "大摩上调目标价；海外矿山风险受关注。",
                "risk_alerts": ["海外矿山安全风险", "短期均线压制"],
                "positive_catalysts": ["降息预期支撑金价", "铜矿产能增长"],
                "earnings_outlook": "2025业绩预期向好。",
                "sentiment_summary": "基本面认可，技术面修复中。",
            },
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "38.25元",
                    "secondary_buy": "37.50元",
                    "stop_loss": "36.70元",
                    "take_profit": "42.20元",
                },
                "position_strategy": {
                    "suggested_position": "3成",
                    "entry_plan": "回踩MA5先建仓，站稳MA10再加仓。",
                    "risk_control": "跌破MA20严格止损。",
                },
                "action_checklist": [
                    "❌ 多头排列未完成",
                    "✅ 乖离率<5%",
                    "✅ 量能配合",
                ],
            },
        },
    }

    context_snapshot = {
        "enhanced_context": {
            "code": "601899",
            "stock_name": "紫金矿业",
            "ma_status": "震荡整理 ↔️",
            "today": {
                "ma5": 38.25,
                "ma10": 39.44,
                "ma20": 38.71,
                "volume_ratio": 0.14,
            },
            "realtime": {
                "price": 38.65,
                "change_pct": 3.93,
                "volume_ratio": 4.1,
                "turnover_rate": 0.29,
                "high": 38.11,
                "low": 38.65,
            },
            "chip": {
                "profit_ratio": 0.8048,
                "avg_cost": 32.36,
                "concentration_90": 0.3839,
            },
        }
    }

    query_meta = {
        "query_id": "601899_20260209_093702_385256",
        "analysis_time": "2026-02-09T09:38:48.833427",
        "report_type": "simple",
        "source": "api",
    }

    return raw_result, context_snapshot, query_meta


def main() -> None:
    daily = _build_synthetic_daily()
    signal = analyze_trend_signal(
        daily_df=daily,
        stock_meta={"code": "601899", "name": "紫金矿业"},
        as_of_date="2026-02-09",
    )

    raw_result, context_snapshot, query_meta = _build_case_payload()
    panels = build_display_panels(raw_result, context_snapshot, query_meta)

    out_dir = Path("股票分析算法")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "demo_trend_signal_output.json").write_text(
        json.dumps(signal, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "demo_display_panels_output.json").write_text(
        json.dumps(panels, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("[ok] trend signal =>", out_dir / "demo_trend_signal_output.json")
    print("[ok] display panels =>", out_dir / "demo_display_panels_output.json")
    print("[diag]", panels.get("diagnostics"))


if __name__ == "__main__":
    main()
