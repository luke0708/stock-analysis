from __future__ import annotations

import html
import json
import pandas as pd
import re
import sqlite3
import unicodedata
from urllib.parse import quote
from typing import Any, Dict, Optional

import streamlit as st

from stock_analysis.data.stock_list import get_stock_provider
from stock_analysis.tasks import (
    JobStore,
    get_job_result,
    get_job_status,
    run_one_pending_job,
    submit_single_stock_job,
)


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except Exception:
        return str(value)


def _extract_summary(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    market_snapshot = (raw_result or {}).get("market_snapshot") or {}
    raw_change = raw_result.get("change_pct")
    if raw_change is None:
        pct_text = market_snapshot.get("pct_chg")
        if isinstance(pct_text, str):
            m = re.search(r"-?\d+(?:\.\d+)?", pct_text)
            raw_change = float(m.group(0)) if m else None

    return {
        "sentiment_score": raw_result.get("sentiment_score"),
        "operation_advice": raw_result.get("operation_advice"),
        "trend_prediction": raw_result.get("trend_prediction"),
        "confidence_level": raw_result.get("confidence_level"),
        "decision_type": raw_result.get("decision_type"),
        "change_pct": raw_change,
        "analysis_summary": raw_result.get("analysis_summary"),
        "key_points": raw_result.get("key_points"),
        "risk_warning": raw_result.get("risk_warning"),
    }


def _extract_stock_identity(raw_result: Dict[str, Any], job_detail: Dict[str, Any]) -> Dict[str, str]:
    code = str((raw_result or {}).get("code") or job_detail.get("stock_code") or "-")
    name = str((raw_result or {}).get("name") or "").strip()
    return {"code": code, "name": name}


def _extract_strategy(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    dashboard = (raw_result or {}).get("dashboard") or {}
    battle = dashboard.get("battle_plan") or {}
    sniper = battle.get("sniper_points") or {}
    return {
        "ideal_buy": sniper.get("ideal_buy"),
        "secondary_buy": sniper.get("secondary_buy"),
        "stop_loss": sniper.get("stop_loss"),
        "take_profit": sniper.get("take_profit"),
    }


def _split_point_text(raw_value: Any) -> Dict[str, str]:
    text = str(raw_value or "").strip()
    if not text:
        return {"price": "-", "detail": "-"}

    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?(?:元)?)\s*(?:[（(](.*?)[）)])?\s*$", text)
    if m:
        price = m.group(1) or "-"
        detail = (m.group(2) or "").strip() or "-"
        return {"price": price, "detail": detail}
    return {"price": text, "detail": "-"}


def _extract_intelligence(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    dashboard = (raw_result or {}).get("dashboard") or {}
    intelligence = dashboard.get("intelligence") or {}
    return {
        "latest_news": intelligence.get("latest_news"),
        "risk_alerts": intelligence.get("risk_alerts") or [],
        "positive_catalysts": intelligence.get("positive_catalysts") or [],
        "earnings_outlook": intelligence.get("earnings_outlook"),
        "sentiment_summary": intelligence.get("sentiment_summary"),
        "risk_warning": raw_result.get("risk_warning"),
        "news_summary": raw_result.get("news_summary"),
        "hot_topics": raw_result.get("hot_topics"),
    }


def _extract_core_conclusion(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    dashboard = (raw_result or {}).get("dashboard") or {}
    core = dashboard.get("core_conclusion") or {}
    position_advice = core.get("position_advice") or {}
    return {
        "one_sentence": core.get("one_sentence"),
        "signal_type": core.get("signal_type"),
        "time_sensitivity": core.get("time_sensitivity"),
        "no_position": position_advice.get("no_position"),
        "has_position": position_advice.get("has_position"),
    }


def _extract_data_perspective(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    dashboard = (raw_result or {}).get("dashboard") or {}
    dp = dashboard.get("data_perspective") or {}
    trend_status = dp.get("trend_status") or {}
    price_position = dp.get("price_position") or {}
    volume_analysis = dp.get("volume_analysis") or {}
    chip_structure = dp.get("chip_structure") or {}
    return {
        "ma_alignment": trend_status.get("ma_alignment"),
        "trend_score": trend_status.get("trend_score"),
        "current_price": price_position.get("current_price"),
        "ma5": price_position.get("ma5"),
        "ma10": price_position.get("ma10"),
        "ma20": price_position.get("ma20"),
        "bias_ma5": price_position.get("bias_ma5"),
        "support_level": price_position.get("support_level"),
        "resistance_level": price_position.get("resistance_level"),
        "volume_ratio": volume_analysis.get("volume_ratio"),
        "turnover_rate": volume_analysis.get("turnover_rate"),
        "profit_ratio": chip_structure.get("profit_ratio"),
        "chip_health": chip_structure.get("chip_health"),
    }


def _pick_analysis_date(raw_result: Dict[str, Any], context_snapshot: Dict[str, Any]) -> Optional[str]:
    market_snapshot = (raw_result or {}).get("market_snapshot") or {}
    if market_snapshot.get("date"):
        return str(market_snapshot["date"])

    enhanced = (context_snapshot or {}).get("enhanced_context") or {}
    today = enhanced.get("today") or {}
    if today.get("date"):
        return str(today["date"])
    return None


def _text_or_dash(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text or "-"


def _escape_text(value: Any) -> str:
    return html.escape(_text_or_dash(value))


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _tone_from_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "neutral"
    positive_tokens = ("买", "加仓", "看多", "上涨", "突破", "强势", "做多", "增持", "进攻")
    negative_tokens = ("卖", "减仓", "止损", "风险", "下跌", "回撤", "看空", "空仓", "离场")
    warning_tokens = ("震荡", "观望", "谨慎", "等待", "盘整")
    if any(token in text for token in negative_tokens):
        return "risk"
    if any(token in text for token in positive_tokens):
        return "positive"
    if any(token in text for token in warning_tokens):
        return "warning"
    return "neutral"


def _tone_from_score(value: Any) -> str:
    score = _to_float(value)
    if score is None:
        return "neutral"
    if score >= 70:
        return "positive"
    if score <= 40:
        return "risk"
    return "warning"


def _tone_from_change(value: Any) -> str:
    change = _to_float(value)
    if change is None:
        return "neutral"
    if change > 0:
        return "positive"
    if change < 0:
        return "risk"
    return "neutral"


def _go_to_analysis_sub_page(page_name: str) -> None:
    st.session_state["_navigate_to"] = page_name
    st.rerun()


def _ensure_selected_job_id(store: JobStore) -> str:
    current = str(st.session_state.get("beta_task_job_id") or "").strip()
    if current:
        return current
    jobs = store.list_jobs(limit=80)
    latest_succeeded = next((j for j in jobs if j.get("status") == "succeeded"), None)
    if latest_succeeded and latest_succeeded.get("job_id"):
        fallback_id = str(latest_succeeded["job_id"])
        st.session_state.beta_task_job_id = fallback_id
        return fallback_id
    return ""


def _delete_job_with_fallback(store: JobStore, job_id: str) -> Dict[str, int]:
    selected_job_id = str(job_id or "").strip()
    if not selected_job_id:
        return {"job_deleted": 0, "result_deleted": 0}

    delete_method = getattr(store, "delete_job", None)
    if callable(delete_method):
        try:
            return delete_method(selected_job_id, delete_result=True)
        except TypeError:
            # Backward compatible call in case older signature exists.
            return delete_method(selected_job_id)

    db_path = getattr(store, "db_path", None)
    if not db_path:
        return {"job_deleted": 0, "result_deleted": 0}

    with sqlite3.connect(str(db_path), timeout=30) as conn:
        conn.execute("BEGIN")
        cur_result = conn.execute(
            "DELETE FROM analysis_results WHERE job_id = ?",
            (selected_job_id,),
        )
        cur_job = conn.execute(
            "DELETE FROM analysis_jobs WHERE job_id = ?",
            (selected_job_id,),
        )
        conn.commit()
    return {
        "job_deleted": int(cur_job.rowcount or 0),
        "result_deleted": int(cur_result.rowcount or 0),
    }


def _inject_beta_panel_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --beta-positive-bg: #ECFDF3;
            --beta-positive-border: #86EFAC;
            --beta-positive-text: #166534;
            --beta-risk-bg: #FEF2F2;
            --beta-risk-border: #FCA5A5;
            --beta-risk-text: #991B1B;
            --beta-warning-bg: #FFF7ED;
            --beta-warning-border: #FDBA74;
            --beta-warning-text: #9A3412;
            --beta-neutral-bg: #F1F5F9;
            --beta-neutral-border: #CBD5E1;
            --beta-neutral-text: #0F172A;
        }
        @keyframes betaFadeRise {
            from {
                opacity: 0;
                transform: translateY(8px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        @keyframes betaPulseGlow {
            0% {
                box-shadow: 0 0 0 rgba(21, 128, 61, 0.0);
            }
            50% {
                box-shadow: 0 8px 24px rgba(21, 128, 61, 0.12);
            }
            100% {
                box-shadow: 0 0 0 rgba(21, 128, 61, 0.0);
            }
        }
        .beta-section-head {
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
            padding: 12px 14px;
            margin: 10px 0 8px;
        }
        .beta-section-title {
            font-size: 17px;
            font-weight: 700;
            color: #0F172A;
            line-height: 1.2;
        }
        .beta-section-sub {
            margin-top: 3px;
            font-size: 12px;
            color: #64748B;
            line-height: 1.4;
        }
        .beta-kpi-wrap {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin: 4px 0 10px;
        }
        .beta-kpi-card {
            border: 1px solid var(--beta-neutral-border);
            border-radius: 12px;
            padding: 10px 12px;
            background: var(--beta-neutral-bg);
            min-height: 96px;
            animation: betaFadeRise 360ms ease both;
        }
        .beta-kpi-label {
            font-size: 13px;
            color: #475569;
            margin-bottom: 4px;
        }
        .beta-kpi-value {
            font-size: 30px;
            line-height: 1.15;
            letter-spacing: -0.01em;
            font-weight: 700;
            color: var(--beta-neutral-text);
            word-break: break-word;
        }
        .beta-kpi-value.beta-kpi-text {
            font-size: 26px;
            line-height: 1.2;
        }
        .beta-kpi-card.beta-tone-positive {
            border-color: var(--beta-positive-border);
            background: var(--beta-positive-bg);
            animation: betaFadeRise 360ms ease both, betaPulseGlow 2200ms ease 2;
        }
        .beta-kpi-card.beta-tone-positive .beta-kpi-value {
            color: var(--beta-positive-text);
        }
        .beta-kpi-card.beta-tone-risk {
            border-color: var(--beta-risk-border);
            background: var(--beta-risk-bg);
        }
        .beta-kpi-card.beta-tone-risk .beta-kpi-value {
            color: var(--beta-risk-text);
        }
        .beta-kpi-card.beta-tone-warning {
            border-color: var(--beta-warning-border);
            background: var(--beta-warning-bg);
        }
        .beta-kpi-card.beta-tone-warning .beta-kpi-value {
            color: var(--beta-warning-text);
        }
        .beta-kpi-card.beta-tone-neutral .beta-kpi-value {
            color: var(--beta-neutral-text);
        }
        .beta-meta-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 4px 10px;
            margin-right: 6px;
            margin-bottom: 4px;
            font-size: 12px;
            line-height: 1.2;
            border: 1px solid var(--beta-neutral-border);
            background: #FFFFFF;
            color: #334155;
        }
        .beta-meta-pill.beta-tone-positive {
            border-color: var(--beta-positive-border);
            background: var(--beta-positive-bg);
            color: var(--beta-positive-text);
        }
        .beta-meta-pill.beta-tone-risk {
            border-color: var(--beta-risk-border);
            background: var(--beta-risk-bg);
            color: var(--beta-risk-text);
        }
        .beta-meta-pill.beta-tone-warning {
            border-color: var(--beta-warning-border);
            background: var(--beta-warning-bg);
            color: var(--beta-warning-text);
        }
        .beta-point-card {
            border: 1px solid var(--beta-neutral-border);
            border-radius: 12px;
            padding: 10px 12px;
            background: #FFFFFF;
            min-height: 96px;
            animation: betaFadeRise 400ms ease both;
        }
        .beta-point-label {
            font-size: 13px;
            color: #64748B;
            margin-bottom: 4px;
        }
        .beta-point-price {
            font-size: 30px;
            font-weight: 700;
            line-height: 1.15;
            color: #0F172A;
            margin-bottom: 2px;
            word-break: break-word;
        }
        .beta-point-detail {
            font-size: 13px;
            color: #475569;
            line-height: 1.35;
            word-break: break-word;
        }
        .beta-point-card.beta-point-buy {
            border-color: var(--beta-positive-border);
            background: #F0FDF4;
        }
        .beta-point-card.beta-point-buy .beta-point-price {
            color: #166534;
        }
        .beta-point-card.beta-point-stop {
            border-color: var(--beta-risk-border);
            background: var(--beta-risk-bg);
        }
        .beta-point-card.beta-point-stop .beta-point-price {
            color: var(--beta-risk-text);
        }
        .beta-point-card.beta-point-take {
            border-color: var(--beta-warning-border);
            background: var(--beta-warning-bg);
        }
        .beta-point-card.beta-point-take .beta-point-price {
            color: var(--beta-warning-text);
        }
        .beta-conclusion-card {
            border: 1px solid #DBEAFE;
            border-radius: 12px;
            background: #EFF6FF;
            padding: 10px 12px;
            color: #1E3A8A;
            font-size: 14px;
            line-height: 1.5;
            animation: betaFadeRise 360ms ease both;
        }
        .beta-callout {
            border: 1px solid;
            border-radius: 12px;
            padding: 10px 12px;
            margin-top: 8px;
            font-size: 13px;
            line-height: 1.45;
        }
        .beta-callout.beta-risk-callout {
            border-color: var(--beta-risk-border);
            background: var(--beta-risk-bg);
            color: var(--beta-risk-text);
        }
        .beta-callout.beta-key-callout {
            border-color: #BFDBFE;
            background: #F0F9FF;
            color: #0C4A6E;
        }
        .beta-fullscreen-hero {
            border: 1px solid #7DD3FC;
            border-radius: 16px;
            padding: 14px 16px;
            margin-bottom: 8px;
            background: linear-gradient(120deg, #F0F9FF 0%, #ECFDF5 45%, #FFF7ED 100%);
            animation: betaFadeRise 480ms ease both;
        }
        .beta-fullscreen-title {
            font-size: 20px;
            font-weight: 700;
            color: #0F172A;
            line-height: 1.2;
            margin-bottom: 4px;
        }
        .beta-fullscreen-sub {
            font-size: 13px;
            color: #334155;
            line-height: 1.45;
        }
        @media (max-width: 1200px) {
            .beta-kpi-wrap {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .beta-kpi-value {
                font-size: 26px;
            }
            .beta-kpi-value.beta-kpi-text {
                font-size: 24px;
            }
            .beta-point-price {
                font-size: 26px;
            }
        }
        @media (max-width: 760px) {
            .beta-kpi-wrap {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _show_section_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="beta-section-head">
            <div class="beta-section-title">{html.escape(title)}</div>
            <div class="beta-section-sub">{html.escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _show_summary_cards(summary: Dict[str, Any]) -> None:
    score_tone = _tone_from_score(summary.get("sentiment_score"))
    advice_tone = _tone_from_text(summary.get("operation_advice"))
    trend_tone = _tone_from_text(summary.get("trend_prediction"))
    change_tone = _tone_from_change(summary.get("change_pct"))
    score = _escape_text(summary.get("sentiment_score"))
    advice = _escape_text(summary.get("operation_advice"))
    trend = _escape_text(summary.get("trend_prediction"))
    change = summary.get("change_pct")
    change_text = f"{change:.2f}%" if isinstance(change, (int, float)) else "-"
    change_text = _escape_text(change_text)
    confidence_text = _escape_text(summary.get("confidence_level"))
    decision_text = _escape_text(summary.get("decision_type"))
    st.markdown(
        f"""
        <div class="beta-kpi-wrap">
          <div class="beta-kpi-card beta-tone-{score_tone}">
            <div class="beta-kpi-label">评分</div>
            <div class="beta-kpi-value">{score}</div>
          </div>
          <div class="beta-kpi-card beta-tone-{advice_tone}">
            <div class="beta-kpi-label">建议</div>
            <div class="beta-kpi-value beta-kpi-text">{advice}</div>
          </div>
          <div class="beta-kpi-card beta-tone-{trend_tone}">
            <div class="beta-kpi-label">趋势</div>
            <div class="beta-kpi-value beta-kpi-text">{trend}</div>
          </div>
          <div class="beta-kpi-card beta-tone-{change_tone}">
            <div class="beta-kpi-label">分析时涨跌</div>
            <div class="beta-kpi-value">{change_text}</div>
          </div>
        </div>
        <div>
          <span class="beta-meta-pill beta-tone-{score_tone}">置信度: {confidence_text}</span>
          <span class="beta-meta-pill beta-tone-{advice_tone}">决策类型: {decision_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _show_conclusion(summary: Dict[str, Any]) -> None:
    st.markdown("**结论摘要**")
    analysis_summary = _escape_text(summary.get("analysis_summary"))
    st.markdown(f'<div class="beta-conclusion-card">{analysis_summary}</div>', unsafe_allow_html=True)

    kp = summary.get("key_points")
    rw = summary.get("risk_warning")
    if kp:
        st.markdown(
            f'<div class="beta-callout beta-key-callout"><strong>关键要点：</strong>{_escape_text(kp)}</div>',
            unsafe_allow_html=True,
        )
    if rw:
        st.markdown(
            f'<div class="beta-callout beta-risk-callout"><strong>风险警示：</strong>{_escape_text(rw)}</div>',
            unsafe_allow_html=True,
        )


def _show_strategy_cards(strategy: Dict[str, Any]) -> None:
    st.markdown("**策略点位**")
    point_defs = [
        ("理想买入", strategy.get("ideal_buy"), "beta-point-buy"),
        ("次级买入", strategy.get("secondary_buy"), "beta-point-buy"),
        ("止损位", strategy.get("stop_loss"), "beta-point-stop"),
        ("止盈位", strategy.get("take_profit"), "beta-point-take"),
    ]
    cols = st.columns(4)
    for col, (label, raw_value, point_class) in zip(cols, point_defs):
        split = _split_point_text(raw_value)
        price = _escape_text(split["price"])
        detail = _escape_text(split["detail"])
        col.markdown(
            f"""
            <div class="beta-point-card {point_class}">
              <div class="beta-point-label">{label}</div>
              <div class="beta-point-price">{price}</div>
              <div class="beta-point-detail">{detail}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _show_intelligence_block(info: Dict[str, Any]) -> None:
    st.markdown("**情报与风险**")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("`风险提示`")
        risks = info.get("risk_alerts") or []
        if risks:
            for item in risks:
                st.write(f"- {item}")
        else:
            st.write("-")
    with c2:
        st.markdown("`正向催化`")
        catalysts = info.get("positive_catalysts") or []
        if catalysts:
            for item in catalysts:
                st.write(f"- {item}")
        else:
            st.write("-")

    if info.get("latest_news"):
        st.caption(f"最新消息: {info.get('latest_news')}")
    if info.get("sentiment_summary"):
        st.caption(f"情绪概览: {info.get('sentiment_summary')}")
    if info.get("earnings_outlook"):
        st.caption(f"业绩预期: {info.get('earnings_outlook')}")
    if info.get("risk_warning"):
        st.caption(f"补充风险: {info.get('risk_warning')}")


def _show_core_conclusion_block(core: Dict[str, Any]) -> None:
    st.markdown("**核心结论**")
    if core.get("one_sentence"):
        st.info(core.get("one_sentence"))
    else:
        st.info("-")

    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"信号类型: {core.get('signal_type') or '-'}")
    with c2:
        st.caption(f"时效窗口: {core.get('time_sensitivity') or '-'}")

    d1, d2 = st.columns(2)
    with d1:
        st.markdown("`空仓建议`")
        st.write(core.get("no_position") or "-")
    with d2:
        st.markdown("`持仓建议`")
        st.write(core.get("has_position") or "-")


def _show_data_perspective_block(dp: Dict[str, Any]) -> None:
    st.markdown("**关键数据视角**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("现价", dp.get("current_price") if dp.get("current_price") is not None else "-")
    c2.metric("量比", dp.get("volume_ratio") if dp.get("volume_ratio") is not None else "-")
    c3.metric("换手率", dp.get("turnover_rate") if dp.get("turnover_rate") is not None else "-")
    c4.metric("趋势分", dp.get("trend_score") if dp.get("trend_score") is not None else "-")

    m1, m2, m3 = st.columns(3)
    m1.caption(f"MA5: {dp.get('ma5') if dp.get('ma5') is not None else '-'}")
    m2.caption(f"MA10: {dp.get('ma10') if dp.get('ma10') is not None else '-'}")
    m3.caption(f"MA20: {dp.get('ma20') if dp.get('ma20') is not None else '-'}")

    if dp.get("ma_alignment"):
        st.caption(f"均线结构: {dp.get('ma_alignment')}")
    if dp.get("support_level") is not None or dp.get("resistance_level") is not None:
        st.caption(
            f"支撑/压力: {dp.get('support_level') if dp.get('support_level') is not None else '-'}"
            f" / {dp.get('resistance_level') if dp.get('resistance_level') is not None else '-'}"
        )
    if dp.get("profit_ratio") is not None or dp.get("chip_health"):
        st.caption(
            f"筹码状态: {dp.get('chip_health') or '-'} | "
            f"获利盘: {dp.get('profit_ratio') if dp.get('profit_ratio') is not None else '-'}"
        )


def _resolve_code_input() -> str:
    last_code = st.session_state.get("last_stock_code")
    if isinstance(last_code, str) and last_code.isdigit() and len(last_code) == 6:
        return last_code

    code = st.session_state.get("stock_code")
    if isinstance(code, str) and code.isdigit() and len(code) == 6:
        return code

    return "601899"


def _status_label(status: str) -> str:
    mapping = {
        "pending": "🟡 待处理",
        "running": "🔵 执行中",
        "succeeded": "🟢 已完成",
        "failed": "🔴 失败",
        "not_found": "⚪ 未找到",
    }
    return mapping.get(status, status or "-")


def _to_status_value(status_label: str) -> Optional[str]:
    mapping = {
        "全部": None,
        "待处理": "pending",
        "执行中": "running",
        "已完成": "succeeded",
        "失败": "failed",
    }
    return mapping.get(status_label)


def _normalize_stock_code_input(raw_code: str) -> str:
    if raw_code is None:
        return ""
    text = unicodedata.normalize("NFKC", str(raw_code)).strip()
    compact = re.sub(r"\s+", "", text)
    match = re.fullmatch(r"(?i)(?:sh|sz)?(\d{6})(?:\.(?:sh|sz))?", compact)
    if not match:
        return ""
    return match.group(1)


def _valid_stock_code(code: str) -> bool:
    return bool(_normalize_stock_code_input(code))


def _precheck_stock_code_exists(stock_code: str) -> Dict[str, Any]:
    """提交前校验：股票代码是否在A股列表中存在。"""
    try:
        provider = get_stock_provider()
        all_df = provider.get_all_stocks()
        if all_df is None or all_df.empty:
            return {
                "ok": True,
                "strict": False,
                "name": "",
                "message": "股票列表服务当前不可用，已跳过存在性校验。",
            }

        exact = all_df[all_df["代码"] == stock_code]
        if exact.empty:
            return {
                "ok": False,
                "strict": True,
                "name": "",
                "message": f"代码 {stock_code} 不在A股股票列表中，请检查输入。",
            }

        name = str(exact.iloc[0]["名称"])
        return {"ok": True, "strict": True, "name": name, "message": f"识别为: {stock_code} {name}"}
    except Exception as exc:
        return {
            "ok": True,
            "strict": False,
            "name": "",
            "message": f"股票列表校验异常，已跳过: {exc}",
        }


def _fmt_duration(duration_ms: Any) -> str:
    if not isinstance(duration_ms, int) or duration_ms < 0:
        return "-"
    if duration_ms < 1000:
        return f"{duration_ms} ms"
    return f"{duration_ms / 1000:.1f} s"


def _job_option_label(job: Dict[str, Any]) -> str:
    return (
        f"{job.get('job_id', '-')}"
        f" | {job.get('stock_code', '-')}"
        f" | {_status_label(job.get('status', ''))}"
        f" | {job.get('created_at', '-')}"
    )


def _short_text(text: Any, limit: int = 60) -> str:
    if text is None:
        return "-"
    value = str(text).strip()
    if not value:
        return "-"
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _clear_query_keys(qp: Any, keys: tuple[str, ...]) -> None:
    for key in keys:
        try:
            if key in qp:
                del qp[key]
        except Exception:
            continue

    # Some Streamlit builds may keep stale params after keyed deletion.
    exists = False
    for key in keys:
        try:
            raw_value = qp.get(key)
        except Exception:
            raw_value = None

        if isinstance(raw_value, list):
            if raw_value:
                exists = True
                break
        elif raw_value not in (None, ""):
            exists = True
            break

    if exists:
        try:
            qp.clear()
        except Exception:
            pass


def _build_completed_archive_rows(store: JobStore, jobs: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for job in jobs:
        result = store.get_result(job.get("job_id", ""))
        raw_result = (result or {}).get("raw_result") or {}
        summary = _extract_summary(raw_result)
        name = str(raw_result.get("name") or "").strip() or "-"
        rows.append(
            {
                "任务ID": job.get("job_id", "-"),
                "代码": job.get("stock_code", "-"),
                "名称": name,
                "创建时间": job.get("created_at", "-"),
                "耗时": _fmt_duration(job.get("duration_ms")),
                "评分": summary.get("sentiment_score") if summary.get("sentiment_score") is not None else "-",
                "建议": summary.get("operation_advice") or "-",
                "趋势": summary.get("trend_prediction") or "-",
                "摘要": _short_text(summary.get("analysis_summary"), limit=72),
            }
        )
    return rows


def _render_completed_results_table_top(store: JobStore) -> None:
    _show_section_header("已完成结果（核心归档）", "页面加载即展示历史结果；在表格中直接打开详情或删除。")

    qp = st.query_params
    raw_action = qp.get("beta_action")
    raw_job_id = qp.get("beta_job_id")
    action = str(raw_action[0] if isinstance(raw_action, list) and raw_action else raw_action or "").strip().lower()
    selected_job_id = str(
        raw_job_id[0] if isinstance(raw_job_id, list) and raw_job_id else raw_job_id or ""
    ).strip()
    if action and selected_job_id:
        if action == "open":
            # Backward compatibility for old links:
            # only sync selected job and clear params, do not force full-screen jump.
            target_job = store.get_job(selected_job_id)
            target_result = store.get_result(selected_job_id)
            if not target_job:
                st.error(f"打开失败：任务不存在（{selected_job_id}）")
            elif target_job.get("status") != "succeeded":
                st.warning(f"该任务当前状态为 {target_job.get('status')}，不可按“已完成结果”打开。")
            elif not target_result:
                st.error("打开失败：该历史任务缺少结果快照，无法展示分析结果。")
            else:
                st.session_state.beta_task_job_id = selected_job_id
            _clear_query_keys(qp, ("beta_action", "beta_job_id"))
        elif action == "delete":
            deleted = _delete_job_with_fallback(store, selected_job_id)
            if deleted.get("job_deleted", 0) > 0:
                if str(st.session_state.get("beta_task_job_id") or "") == selected_job_id:
                    st.session_state.beta_task_job_id = ""
                st.success(
                    f"已删除任务: {selected_job_id} "
                    f"(任务记录 {deleted.get('job_deleted', 0)} 条, 结果记录 {deleted.get('result_deleted', 0)} 条)"
                )
            else:
                st.error(f"删除失败：未找到任务 {selected_job_id}")
            _clear_query_keys(qp, ("beta_action", "beta_job_id"))
            st.rerun()
        else:
            _clear_query_keys(qp, ("beta_action", "beta_job_id"))

    done_jobs = store.list_jobs(status="succeeded", limit=80)
    if not done_jobs:
        st.info("暂无已完成历史结果。")
        return

    done_rows = _build_completed_archive_rows(store, done_jobs)
    table_rows: list[Dict[str, Any]] = []
    for row in done_rows:
        table_rows.append(
            {
                "代码": row.get("代码", "-"),
                "名称": row.get("名称", "-"),
                "评分": row.get("评分", "-"),
                "建议": row.get("建议", "-"),
                "趋势": row.get("趋势", "-"),
                "摘要": row.get("摘要", "-"),
                "详情": f"?nav=beta_full&job_id={quote(str(row.get('任务ID', '')).strip(), safe='')}",
                "删除": f"?beta_action=delete&beta_job_id={quote(str(row.get('任务ID', '')).strip(), safe='')}",
            }
        )

    table_df = pd.DataFrame(table_rows)
    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "详情": st.column_config.LinkColumn(
                "详情",
                help="选择后跳转到全屏结果页",
                width="small",
                display_text="详情",
            ),
            "删除": st.column_config.LinkColumn(
                "删除",
                help="选择后按条删除该历史结果",
                width="small",
                display_text="删除",
            ),
        },
    )
    st.caption("点击“详情”跳转全屏结果页；点击“删除”直接按条删除。")


def _build_failed_archive_rows(jobs: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for job in jobs:
        rows.append(
            {
                "任务ID": job.get("job_id", "-"),
                "代码": job.get("stock_code", "-"),
                "创建时间": job.get("created_at", "-"),
                "耗时": _fmt_duration(job.get("duration_ms")),
                "错误": _short_text(job.get("error_message"), limit=96),
            }
        )
    return rows


def _find_active_job(
    store: JobStore,
    *,
    stock_code: str,
    report_type: str,
) -> Optional[Dict[str, Any]]:
    jobs = store.list_jobs(limit=200)
    for job in jobs:
        if (
            job.get("stock_code") == stock_code
            and job.get("report_type") == report_type
            and job.get("status") in {"pending", "running"}
        ):
            return job
    return None


def _render_result_zone(
    store: JobStore,
    *,
    debug_mode: bool,
    show_open_fullscreen_button: bool,
    fullscreen_mode: bool,
    key_prefix: str,
) -> None:
    title = "分析结果（核心）" if not fullscreen_mode else "分析结果（全屏）"
    subtitle = (
        "结果优先展示：先看结论、策略点位和风险，再决定是否查看任务细节。"
        if not fullscreen_mode
        else "沉浸式结果视图：突出关键信号与风险提示，适合复盘和汇报。"
    )
    _show_section_header(title, subtitle)

    job_id = _ensure_selected_job_id(store)
    if show_open_fullscreen_button:
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("🧾 全屏查看", key=f"{key_prefix}_open_fullscreen_btn"):
                _go_to_analysis_sub_page("🧾 分析结果全屏 (Beta)")
        with c2:
            if job_id:
                st.caption(f"当前展示任务: {job_id}")

    if not job_id:
        st.info("暂无可展示的分析结果。请在下方任务区提交任务，或在归档中加载已完成任务。")
        return

    job_detail = store.get_job(job_id) or {}
    status = get_job_status(job_id, store=store)
    progress_raw = status.get("progress", 0.0)
    try:
        progress = float(progress_raw)
    except Exception:
        progress = 0.0
    progress = max(0.0, min(1.0, progress))

    if not fullscreen_mode:
        with st.container(border=True):
            st.markdown("#### 任务执行信息")
            st.caption(f"任务ID: {job_id}")
            h1, h2, h3, h4, h5 = st.columns(5)
            h1.metric("股票代码", job_detail.get("stock_code") or "-")
            h2.metric("报告类型", job_detail.get("report_type") or "-")
            h3.metric("任务状态", _status_label(status.get("status", "")))
            h4.metric("任务耗时", _fmt_duration(job_detail.get("duration_ms")))
            h5.metric("创建时间", job_detail.get("created_at") or "-")
            if job_detail.get("started_at") or job_detail.get("finished_at"):
                st.caption(
                    f"开始时间: {job_detail.get('started_at') or '-'} | 完成时间: {job_detail.get('finished_at') or '-'}"
                )
            st.caption(
                f"状态: {_status_label(status.get('status', ''))} | "
                f"进度: {int(progress * 100)}% | 说明: {status.get('message', '-')}"
            )
            st.progress(progress)

    if status.get("status") == "failed":
        if fullscreen_mode:
            st.warning("当前暂无可展示的分析结果，请返回 Beta 面板处理任务后再查看全屏。")
        else:
            err = job_detail.get("error_message") or status.get("message") or "任务失败"
            st.error(err)
        return

    if status.get("status") != "succeeded":
        if fullscreen_mode:
            st.info("分析结果生成中，请稍后刷新，或返回 Beta 面板查看任务进度。")
        return

    result_payload = get_job_result(job_id, store=store)
    if result_payload.get("error"):
        st.error(result_payload["error"])
        return

    meta = result_payload.get("meta") or {}
    raw_result = result_payload.get("raw_result") or {}
    context_snapshot = result_payload.get("context_snapshot") or {}
    analysis_date = _pick_analysis_date(raw_result, context_snapshot if isinstance(context_snapshot, dict) else {})
    identity = _extract_stock_identity(raw_result, job_detail)
    title_text = identity["code"] if not identity["name"] else f"{identity['code']} {identity['name']}"

    summary_data = _extract_summary(raw_result)
    strategy_data = _extract_strategy(raw_result)
    intelligence_data = _extract_intelligence(raw_result)
    core_data = _extract_core_conclusion(raw_result)
    perspective_data = _extract_data_perspective(raw_result)

    if fullscreen_mode:
        st.markdown(
            f"""
            <div class="beta-fullscreen-hero">
              <div class="beta-fullscreen-title">🔎 {html.escape(title_text)} · 决策结果聚焦视图</div>
              <div class="beta-fullscreen-sub">
                QueryID: {html.escape(str(meta.get("query_id") or "-"))}
                | 分析时间: {html.escape(str(meta.get("analysis_time") or "-"))}
                | 数据来源: {html.escape(str(meta.get("source") or "-"))}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        st.markdown("#### 分析结果")
        st.markdown(f"**{title_text}**")
        if fullscreen_mode:
            st.markdown(
                f"`QueryID:` {meta.get('query_id') or '-'}"
                f" | `时间:` {meta.get('analysis_time') or '-'}"
                f" | `来源:` {meta.get('source') or '-'}"
            )
        else:
            st.markdown(
                f"`QueryID:` {meta.get('query_id') or '-'}"
                f" | `时间:` {meta.get('analysis_time') or '-'}"
                f" | `类型:` {job_detail.get('report_type') or '-'}"
                f" | `来源:` {meta.get('source') or '-'}"
            )
        if analysis_date:
            st.info(f"分析基准交易日: {analysis_date}（Beta 页面按原算法结果展示，不做本地重算）")

        tab_overview, tab_strategy, tab_context = st.tabs(["总览", "策略点位", "风险与补充"])
        with tab_overview:
            _show_summary_cards(summary_data)
            _show_conclusion(summary_data)
        with tab_strategy:
            _show_strategy_cards(strategy_data)
            st.caption("策略点位按原算法结果直接展示，不做本地推算。")
        with tab_context:
            _show_core_conclusion_block(core_data)
            _show_data_perspective_block(perspective_data)
            _show_intelligence_block(intelligence_data)

    if debug_mode:
        with st.expander("调试数据（raw_result / context_snapshot）", expanded=False):
            st.json(_safe_json(raw_result))
            st.json(_safe_json(context_snapshot))


def _render_task_zone(store: JobStore) -> None:
    code = _resolve_code_input()
    report_type = "simple"
    control_expanded = not bool(st.session_state.beta_task_job_id)
    _show_section_header("任务区", "提交任务、查看队列与归档；任务区退居次级，不干扰结果阅读。")
    with st.container(border=True):
        with st.expander("展开任务操作（提交 / 队列 / 归档）", expanded=control_expanded):
            submit_tab, queue_tab, archive_tab = st.tabs(["提交任务", "队列状态", "任务归档"])

            with submit_tab:
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    code = st.text_input("股票代码", value=_resolve_code_input(), max_chars=16)
                    normalized_input_code = _normalize_stock_code_input(code)
                    if code:
                        if normalized_input_code:
                            st.caption(f"输入识别: {normalized_input_code}")
                        else:
                            st.caption("请输入6位股票代码（支持 601899 / sh601899 / 601899.SH）")
                with col2:
                    report_type = st.selectbox("报告类型", ["simple", "detailed"], index=0)
                with col3:
                    st.caption("提交后进入队列")

                c1, c2 = st.columns([1, 3])
                with c1:
                    if st.button("提交分析任务", type="primary", key="beta_submit_job_btn"):
                        try:
                            can_submit = True
                            normalized_code = _normalize_stock_code_input(code)
                            if not normalized_code:
                                st.error("股票代码格式无效，请输入6位代码（如 601899）。")
                                can_submit = False

                            if can_submit:
                                check = _precheck_stock_code_exists(normalized_code)
                                if check.get("ok"):
                                    if check.get("strict"):
                                        st.success(check.get("message") or "代码校验通过")
                                    else:
                                        st.warning(check.get("message") or "已跳过代码存在性校验")
                                else:
                                    st.error(check.get("message") or "股票代码校验失败")
                                    can_submit = False

                            if can_submit:
                                active_job = _find_active_job(
                                    store,
                                    stock_code=normalized_code,
                                    report_type=report_type,
                                )
                                if active_job:
                                    st.session_state.beta_task_job_id = active_job["job_id"]
                                    st.info(
                                        f"检测到进行中的同类任务，已定位到: {active_job['job_id']} "
                                        f"({_status_label(active_job.get('status', ''))})"
                                    )
                                else:
                                    payload = submit_single_stock_job(normalized_code, report_type=report_type, store=store)
                                    st.session_state.beta_task_job_id = payload["job_id"]
                                    st.session_state.last_stock_code = normalized_code
                                    st.success(f"任务已提交: {payload['job_id']}")
                        except Exception as exc:
                            st.error(f"提交失败: {exc}")
                with c2:
                    st.caption("MVP 阶段支持单股任务；分析耗时数分钟属于正常。")

            with queue_tab:
                jobs = store.list_jobs(limit=20)
                pending_cnt = len([j for j in jobs if j.get("status") == "pending"])
                running_cnt = len([j for j in jobs if j.get("status") == "running"])
                succeeded_cnt = len([j for j in jobs if j.get("status") == "succeeded"])
                failed_cnt = len([j for j in jobs if j.get("status") == "failed"])
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("待处理", pending_cnt)
                s2.metric("执行中", running_cnt)
                s3.metric("已完成", succeeded_cnt)
                s4.metric("失败", failed_cnt)

                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    if st.button("执行队列任务", key="beta_run_queue_btn"):
                        with st.spinner("正在执行任务..."):
                            outcome = run_one_pending_job(store=store)
                        if outcome.get("status") == "succeeded":
                            st.success(f"任务完成: {outcome.get('job_id')}")
                            st.session_state.beta_task_job_id = outcome.get("job_id", st.session_state.beta_task_job_id)
                        elif outcome.get("status") == "failed":
                            st.error(f"任务失败: {outcome.get('error')}")
                            st.session_state.beta_task_job_id = outcome.get("job_id", st.session_state.beta_task_job_id)
                        else:
                            st.info(outcome.get("message", "当前无待处理任务"))
                with c2:
                    if st.button("刷新", key="beta_refresh_btn"):
                        st.rerun()
                with c3:
                    st.caption("开发模式可手动执行；生产建议使用 worker 持续消费队列。")
                    st.code("python3 -m stock_analysis.tasks.worker_cli --poll 3 --timeout 900")

                if st.session_state.beta_task_job_id:
                    st.caption(f"当前选中任务: {st.session_state.beta_task_job_id}")

            with archive_tab:
                jobs = store.list_jobs(limit=60)
                f1, f2 = st.columns([1, 1])
                with f1:
                    only_current_stock = st.toggle("仅看当前股票", value=False, key="beta_only_current_stock")
                with f2:
                    show_count = st.selectbox("展示条数", [10, 20, 30, 50], index=1, key="beta_archive_show_count")

                filtered_jobs = jobs
                current_code = _normalize_stock_code_input(code)
                if only_current_stock and _valid_stock_code(current_code):
                    filtered_jobs = [j for j in filtered_jobs if j.get("stock_code") == current_code]

                succeeded_jobs = [j for j in filtered_jobs if j.get("status") == "succeeded"][: int(show_count)]
                failed_jobs = [j for j in filtered_jobs if j.get("status") == "failed"][: int(show_count)]

                st.markdown("#### 已完成结果")
                st.caption(
                    f"已完成任务 {len(succeeded_jobs)} 条。核心历史结果表已上移到页面上方，"
                    "请在顶部表格执行“详情/删除”。"
                )

                st.markdown("#### 失败任务（可重试）")
                if failed_jobs:
                    failed_rows = _build_failed_archive_rows(failed_jobs)
                    st.dataframe(failed_rows, use_container_width=True, hide_index=True)

                    failed_label_to_job_id: Dict[str, str] = {}
                    failed_options: list[str] = []
                    for row in failed_rows:
                        job_id_text = str(row["任务ID"])
                        label = (
                            f"{job_id_text} | {row['创建时间']} | {row['代码']} | "
                            f"{_short_text(row['错误'], limit=36)}"
                        )
                        failed_options.append(label)
                        failed_label_to_job_id[label] = job_id_text

                    if (
                        "beta_failed_option_label" not in st.session_state
                        or str(st.session_state.get("beta_failed_option_label")) not in failed_options
                    ):
                        st.session_state["beta_failed_option_label"] = failed_options[0]

                    failed_selected_label = st.selectbox(
                        "选择失败任务",
                        failed_options,
                        key="beta_failed_option_label",
                    )
                    failed_selected_job_id = str(failed_label_to_job_id.get(failed_selected_label, ""))
                    st.caption(f"当前选中失败任务ID: {failed_selected_job_id or '-'}")
                    failed_job = next(
                        (j for j in failed_jobs if str(j.get("job_id")) == str(failed_selected_job_id)),
                        None,
                    )

                    if failed_job:
                        r1, r2 = st.columns([1, 3])
                        with r1:
                            if st.button("重试该失败任务", key="beta_retry_failed_btn"):
                                try:
                                    payload = submit_single_stock_job(
                                        failed_job["stock_code"],
                                        report_type=failed_job.get("report_type", "simple"),
                                        requested_by="beta_ui_retry",
                                        store=store,
                                    )
                                    st.session_state.beta_task_job_id = payload["job_id"]
                                    st.success(f"已重试并生成新任务: {payload['job_id']}")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"重试失败: {exc}")
                        with r2:
                            st.caption(f"错误详情: {failed_job.get('error_message') or '-'}")
                else:
                    st.caption("暂无失败任务。")


def show_ai_decision_panel_beta_task() -> None:
    st.header("🧩 AI决策面板 (Beta)")
    st.warning("⚠️ 当前为冻结状态：本面板基于移植的开源算法，尚未成熟，仅作实验参考。主力功能请使用 🤖 AI 投顾。")
    st.caption("任务化复刻模式：只展示原算法输出的 raw_result/context_snapshot，不做本地策略点位推算。")
    _inject_beta_panel_styles()

    store = JobStore()
    if "beta_task_job_id" not in st.session_state:
        st.session_state.beta_task_job_id = ""

    _render_completed_results_table_top(store)

    debug_mode = st.toggle("调试模式（显示 raw_result / context_snapshot JSON）", value=False, key="beta_debug_mode")
    if not debug_mode:
        st.caption("标准视图：结果区已置顶，并对核心指标进行高亮。")

    _render_result_zone(
        store=store,
        debug_mode=debug_mode,
        show_open_fullscreen_button=True,
        fullscreen_mode=False,
        key_prefix="beta_main",
    )
    _render_task_zone(store)


def show_ai_decision_panel_beta_result_fullscreen() -> None:
    st.header("🧾 分析结果全屏 (Beta)")
    st.caption("独立全屏页面，优先展示分析结果并强化视觉提示，适合复盘与汇报。")
    _inject_beta_panel_styles()

    store = JobStore()
    if "beta_task_job_id" not in st.session_state:
        st.session_state.beta_task_job_id = ""

    n1, n2, n3 = st.columns([1, 1, 3])
    with n1:
        if st.button("← 返回 Beta 面板", key="beta_full_back_btn"):
            _go_to_analysis_sub_page("🧩 AI决策面板 (Beta)")
    with n2:
        if st.button("刷新结果", key="beta_full_refresh_btn"):
            st.rerun()
    with n3:
        debug_mode = st.toggle(
            "调试模式（全屏）",
            value=False,
            key="beta_full_debug_mode",
            help="开启后可查看 raw_result/context_snapshot 原始数据。",
        )

    _render_result_zone(
        store=store,
        debug_mode=debug_mode,
        show_open_fullscreen_button=False,
        fullscreen_mode=True,
        key_prefix="beta_full",
    )
