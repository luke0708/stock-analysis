"""UI field mapping for single-stock analysis display groups.

This module maps `raw_result` + `analysis_context_snapshot.enhanced_context`
into grouped panels confirmed in v1 docs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


def _get_path(obj: Mapping[str, Any], path: str) -> Any:
    cur: Any = obj
    for key in path.split("."):
        if not isinstance(cur, Mapping) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _first_non_null(candidates: Sequence[Tuple[str, Any]]) -> Tuple[Any, str]:
    for source, value in candidates:
        if value is not None and value != "":
            return value, source
    return None, ""


def _parse_float_from_text(text: Any) -> Optional[float]:
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group())
    except Exception:
        return None


@dataclass
class DisplayField:
    key: str
    label: str
    value: Any
    source: str = ""


Panel = Dict[str, Any]


def _field(label: str, key: str, value: Any, source: str = "") -> DisplayField:
    return DisplayField(key=key, label=label, value=value if value not in (None, "") else "--", source=source)


def _extract_enhanced_context(context_snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    enhanced = context_snapshot.get("enhanced_context")
    if isinstance(enhanced, Mapping):
        return enhanced
    return {}


def build_display_panels(
    raw_result: Mapping[str, Any],
    context_snapshot: Optional[Mapping[str, Any]] = None,
    query_meta: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build grouped panel payload for UI rendering.

    Args:
        raw_result: Structured AI result payload.
        context_snapshot: Optional context snapshot with enhanced_context.
        query_meta: Optional metadata (query_id, analysis_time, report_type, source).
    """
    context_snapshot = context_snapshot or {}
    query_meta = query_meta or {}
    enhanced = _extract_enhanced_context(context_snapshot)

    dashboard = raw_result.get("dashboard") or {}
    dp = dashboard.get("data_perspective") or {}
    core = dashboard.get("core_conclusion") or {}
    battle = dashboard.get("battle_plan") or {}
    intel = dashboard.get("intelligence") or {}

    today = enhanced.get("today") or {}
    realtime = enhanced.get("realtime") or {}
    chip = enhanced.get("chip") or {}

    top_cards: List[DisplayField] = []
    top_cards.append(_field("AI评分", "sentiment_score", raw_result.get("sentiment_score"), "raw_result.sentiment_score"))
    top_cards.append(_field("AI趋势", "trend_prediction", raw_result.get("trend_prediction"), "raw_result.trend_prediction"))
    top_cards.append(_field("AI建议", "operation_advice", raw_result.get("operation_advice"), "raw_result.operation_advice"))
    top_cards.append(_field("AI置信度", "confidence_level", raw_result.get("confidence_level"), "raw_result.confidence_level"))

    change_val, change_src = _first_non_null(
        [
            ("raw_result.change_pct", raw_result.get("change_pct")),
            ("enhanced_context.realtime.change_pct", realtime.get("change_pct")),
        ]
    )
    top_cards.append(_field("分析时涨跌", "change_pct", change_val, change_src))

    price_val, price_src = _first_non_null(
        [
            ("raw_result.current_price", raw_result.get("current_price")),
            ("enhanced_context.realtime.price", realtime.get("price")),
        ]
    )
    top_cards.append(_field("现价", "current_price", price_val, price_src))

    price_position = dp.get("price_position") or {}
    trend_status = dp.get("trend_status") or {}
    volume_analysis = dp.get("volume_analysis") or {}
    chip_structure = dp.get("chip_structure") or {}

    technical = [
        _field("MA5", "ma5", _first_non_null([
            ("dashboard.data_perspective.price_position.ma5", price_position.get("ma5")),
            ("enhanced_context.today.ma5", today.get("ma5")),
        ])[0], "dashboard|enhanced.today"),
        _field("MA10", "ma10", _first_non_null([
            ("dashboard.data_perspective.price_position.ma10", price_position.get("ma10")),
            ("enhanced_context.today.ma10", today.get("ma10")),
        ])[0], "dashboard|enhanced.today"),
        _field("MA20", "ma20", _first_non_null([
            ("dashboard.data_perspective.price_position.ma20", price_position.get("ma20")),
            ("enhanced_context.today.ma20", today.get("ma20")),
        ])[0], "dashboard|enhanced.today"),
        _field("均线排列结论", "ma_alignment", _first_non_null([
            ("dashboard.data_perspective.trend_status.ma_alignment", trend_status.get("ma_alignment")),
            ("enhanced_context.ma_status", enhanced.get("ma_status")),
        ])[0], "dashboard|enhanced"),
        _field("趋势分", "trend_score", trend_status.get("trend_score"), "dashboard.data_perspective.trend_status.trend_score"),
        _field("乖离率(MA5)", "bias_ma5", price_position.get("bias_ma5"), "dashboard.data_perspective.price_position.bias_ma5"),
        _field("乖离状态", "bias_status", price_position.get("bias_status"), "dashboard.data_perspective.price_position.bias_status"),
        _field("支撑位", "support_level", price_position.get("support_level"), "dashboard.data_perspective.price_position.support_level"),
        _field("压力位", "resistance_level", price_position.get("resistance_level"), "dashboard.data_perspective.price_position.resistance_level"),
    ]

    volume_ratio, volume_ratio_src = _first_non_null(
        [
            ("dashboard.data_perspective.volume_analysis.volume_ratio", volume_analysis.get("volume_ratio")),
            ("enhanced_context.realtime.volume_ratio", realtime.get("volume_ratio")),
        ]
    )
    turnover, turnover_src = _first_non_null(
        [
            ("dashboard.data_perspective.volume_analysis.turnover_rate", volume_analysis.get("turnover_rate")),
            ("enhanced_context.realtime.turnover_rate", realtime.get("turnover_rate")),
        ]
    )

    volume_chip = [
        _field("量比", "volume_ratio", volume_ratio, volume_ratio_src),
        _field("量能状态", "volume_status", volume_analysis.get("volume_status"), "dashboard.data_perspective.volume_analysis.volume_status"),
        _field("换手率", "turnover_rate", turnover, turnover_src),
        _field("量能解读", "volume_meaning", volume_analysis.get("volume_meaning"), "dashboard.data_perspective.volume_analysis.volume_meaning"),
        _field("获利盘", "profit_ratio", _first_non_null([
            ("dashboard.data_perspective.chip_structure.profit_ratio", chip_structure.get("profit_ratio")),
            ("enhanced_context.chip.profit_ratio", chip.get("profit_ratio")),
        ])[0], "dashboard|enhanced.chip"),
        _field("平均成本", "avg_cost", _first_non_null([
            ("dashboard.data_perspective.chip_structure.avg_cost", chip_structure.get("avg_cost")),
            ("enhanced_context.chip.avg_cost", chip.get("avg_cost")),
        ])[0], "dashboard|enhanced.chip"),
        _field("集中度", "concentration", _first_non_null([
            ("dashboard.data_perspective.chip_structure.concentration", chip_structure.get("concentration")),
            ("enhanced_context.chip.concentration_90", chip.get("concentration_90")),
        ])[0], "dashboard|enhanced.chip"),
        _field("筹码健康度", "chip_health", chip_structure.get("chip_health"), "dashboard.data_perspective.chip_structure.chip_health"),
    ]

    sniper = battle.get("sniper_points") or {}
    pos = battle.get("position_strategy") or {}
    strategy = [
        _field("理想买入", "ideal_buy", sniper.get("ideal_buy"), "dashboard.battle_plan.sniper_points.ideal_buy"),
        _field("次级买入", "secondary_buy", sniper.get("secondary_buy"), "dashboard.battle_plan.sniper_points.secondary_buy"),
        _field("止损位", "stop_loss", sniper.get("stop_loss"), "dashboard.battle_plan.sniper_points.stop_loss"),
        _field("止盈位", "take_profit", sniper.get("take_profit"), "dashboard.battle_plan.sniper_points.take_profit"),
        _field("建议仓位", "suggested_position", pos.get("suggested_position"), "dashboard.battle_plan.position_strategy.suggested_position"),
        _field("入场计划", "entry_plan", pos.get("entry_plan"), "dashboard.battle_plan.position_strategy.entry_plan"),
        _field("风控计划", "risk_control", pos.get("risk_control"), "dashboard.battle_plan.position_strategy.risk_control"),
        _field("行动清单", "action_checklist", battle.get("action_checklist"), "dashboard.battle_plan.action_checklist"),
    ]

    intelligence = [
        _field("最新情报", "latest_news", intel.get("latest_news"), "dashboard.intelligence.latest_news"),
        _field("风险提示列表", "risk_alerts", intel.get("risk_alerts"), "dashboard.intelligence.risk_alerts"),
        _field("正向催化", "positive_catalysts", intel.get("positive_catalysts"), "dashboard.intelligence.positive_catalysts"),
        _field("业绩展望", "earnings_outlook", intel.get("earnings_outlook"), "dashboard.intelligence.earnings_outlook"),
        _field("情绪摘要", "sentiment_summary", intel.get("sentiment_summary"), "dashboard.intelligence.sentiment_summary"),
    ]

    conclusion = [
        _field("一句话结论", "one_sentence", core.get("one_sentence"), "dashboard.core_conclusion.one_sentence"),
        _field("信号标签", "signal_type", core.get("signal_type"), "dashboard.core_conclusion.signal_type"),
        _field("空仓建议", "no_position", _get_path(core, "position_advice.no_position"), "dashboard.core_conclusion.position_advice.no_position"),
        _field("持仓建议", "has_position", _get_path(core, "position_advice.has_position"), "dashboard.core_conclusion.position_advice.has_position"),
        _field("综合摘要", "analysis_summary", raw_result.get("analysis_summary"), "raw_result.analysis_summary"),
        _field("关键要点", "key_points", raw_result.get("key_points"), "raw_result.key_points"),
        _field("风险警示", "risk_warning", raw_result.get("risk_warning"), "raw_result.risk_warning"),
        _field("买入/观望理由", "buy_reason", raw_result.get("buy_reason"), "raw_result.buy_reason"),
    ]

    meta = [
        _field("QueryID", "query_id", query_meta.get("query_id"), "query_meta.query_id"),
        _field("分析时间", "analysis_time", query_meta.get("analysis_time"), "query_meta.analysis_time"),
        _field("报告类型", "report_type", query_meta.get("report_type"), "query_meta.report_type"),
        _field("数据来源说明", "data_sources", raw_result.get("data_sources"), "raw_result.data_sources"),
        _field("是否搜索", "search_performed", raw_result.get("search_performed"), "raw_result.search_performed"),
        _field("行情快照", "market_snapshot", raw_result.get("market_snapshot"), "raw_result.market_snapshot"),
        _field("来源", "source", query_meta.get("source"), "query_meta.source"),
    ]

    panels: List[Panel] = [
        {"id": "top_cards", "title": "顶部总览卡片", "fields": [f.__dict__ for f in top_cards]},
        {"id": "technical", "title": "技术结构面板", "fields": [f.__dict__ for f in technical]},
        {"id": "volume_chip", "title": "量能与筹码面板", "fields": [f.__dict__ for f in volume_chip]},
        {"id": "strategy", "title": "策略点位面板", "fields": [f.__dict__ for f in strategy]},
        {"id": "intelligence", "title": "情报与风险面板", "fields": [f.__dict__ for f in intelligence]},
        {"id": "conclusion", "title": "结论与解释面板", "fields": [f.__dict__ for f in conclusion]},
        {"id": "meta", "title": "底部元数据面板", "fields": [f.__dict__ for f in meta]},
    ]

    diagnostics = {
        "conflict_flags": {
            "volume_ratio_conflict": False,
            "ohlc_conflict": False,
        },
        "notes": [],
    }

    # Detect known conflicts for debugging and data hygiene.
    today_ratio = _parse_float_from_text(today.get("volume_ratio"))
    realtime_ratio = _parse_float_from_text(realtime.get("volume_ratio"))
    if today_ratio is not None and realtime_ratio is not None and abs(today_ratio - realtime_ratio) > 0.5:
        diagnostics["conflict_flags"]["volume_ratio_conflict"] = True
        diagnostics["notes"].append("volume_ratio differs between today and realtime contexts")

    high = _parse_float_from_text(realtime.get("high"))
    low = _parse_float_from_text(realtime.get("low"))
    if high is not None and low is not None and high < low:
        diagnostics["conflict_flags"]["ohlc_conflict"] = True
        diagnostics["notes"].append("realtime high < low, likely upstream mapping issue")

    return {
        "schema_version": "display_panels_v1",
        "stock": {
            "code": raw_result.get("code") or enhanced.get("code"),
            "name": raw_result.get("name") or enhanced.get("stock_name"),
        },
        "panels": panels,
        "diagnostics": diagnostics,
    }


__all__ = ["build_display_panels"]
