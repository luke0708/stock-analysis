from __future__ import annotations

import json
import re
import unicodedata
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


def _show_summary_cards(summary: Dict[str, Any]) -> None:
    st.markdown(
        """
        <style>
        .beta-kpi-wrap {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 14px;
            margin-top: 4px;
            margin-bottom: 10px;
        }
        .beta-kpi-card {
            border: 1px solid #E6E8EF;
            border-radius: 12px;
            padding: 12px 14px 10px;
            background: #FAFBFD;
            min-height: 108px;
        }
        .beta-kpi-label {
            font-size: 14px;
            color: #6B7280;
            margin-bottom: 4px;
        }
        .beta-kpi-value {
            font-size: 56px;
            line-height: 1.0;
            letter-spacing: -0.02em;
            font-weight: 700;
            color: #111827;
            word-break: break-word;
        }
        .beta-kpi-value.beta-kpi-text {
            font-size: 58px;
        }
        @media (max-width: 1200px) {
            .beta-kpi-wrap {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .beta-kpi-value {
                font-size: 48px;
            }
            .beta-kpi-value.beta-kpi-text {
                font-size: 46px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    score = summary.get("sentiment_score") if summary.get("sentiment_score") is not None else "-"
    advice = summary.get("operation_advice") or "-"
    trend = summary.get("trend_prediction") or "-"
    change = summary.get("change_pct")
    change_text = f"{change:.2f}%" if isinstance(change, (int, float)) else "-"
    st.markdown(
        f"""
        <div class="beta-kpi-wrap">
          <div class="beta-kpi-card">
            <div class="beta-kpi-label">评分</div>
            <div class="beta-kpi-value">{score}</div>
          </div>
          <div class="beta-kpi-card">
            <div class="beta-kpi-label">建议</div>
            <div class="beta-kpi-value beta-kpi-text">{advice}</div>
          </div>
          <div class="beta-kpi-card">
            <div class="beta-kpi-label">趋势</div>
            <div class="beta-kpi-value beta-kpi-text">{trend}</div>
          </div>
          <div class="beta-kpi-card">
            <div class="beta-kpi-label">分析时涨跌</div>
            <div class="beta-kpi-value">{change_text}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"置信度: {summary.get('confidence_level') or '-'}"
        f" | 决策类型: {summary.get('decision_type') or '-'}"
    )


def _show_conclusion(summary: Dict[str, Any]) -> None:
    st.markdown("**结论摘要**")
    st.markdown(summary.get("analysis_summary") or "-")

    kp = summary.get("key_points")
    rw = summary.get("risk_warning")
    if kp:
        st.caption(f"关键要点: {kp}")
    if rw:
        st.caption(f"风险警示: {rw}")


def _show_strategy_cards(strategy: Dict[str, Any]) -> None:
    st.markdown("**策略点位**")
    st.markdown(
        """
        <style>
        .beta-point-card {
            border: 1px solid #E5E7EB;
            border-radius: 10px;
            padding: 10px 12px;
            background: #FAFAFA;
            min-height: 96px;
        }
        .beta-point-label {
            font-size: 13px;
            color: #6B7280;
            margin-bottom: 4px;
        }
        .beta-point-price {
            font-size: 44px;
            font-weight: 700;
            line-height: 1.15;
            color: #111827;
            margin-bottom: 3px;
            word-break: break-word;
        }
        .beta-point-detail {
            font-size: 13px;
            color: #4B5563;
            line-height: 1.35;
            word-break: break-word;
        }
        @media (max-width: 1200px) {
            .beta-point-price {
                font-size: 36px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    point_defs = [
        ("理想买入", strategy.get("ideal_buy")),
        ("次级买入", strategy.get("secondary_buy")),
        ("止损位", strategy.get("stop_loss")),
        ("止盈位", strategy.get("take_profit")),
    ]
    cols = st.columns(4)
    for col, (label, raw_value) in zip(cols, point_defs):
        split = _split_point_text(raw_value)
        col.markdown(
            f"""
            <div class="beta-point-card">
              <div class="beta-point-label">{label}</div>
              <div class="beta-point-price">{split["price"]}</div>
              <div class="beta-point-detail">{split["detail"]}</div>
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


def _build_completed_archive_rows(store: JobStore, jobs: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for job in jobs:
        result = store.get_result(job.get("job_id", ""))
        raw_result = (result or {}).get("raw_result") or {}
        summary = _extract_summary(raw_result)
        rows.append(
            {
                "任务ID": job.get("job_id", "-"),
                "代码": job.get("stock_code", "-"),
                "创建时间": job.get("created_at", "-"),
                "耗时": _fmt_duration(job.get("duration_ms")),
                "评分": summary.get("sentiment_score") if summary.get("sentiment_score") is not None else "-",
                "建议": summary.get("operation_advice") or "-",
                "趋势": summary.get("trend_prediction") or "-",
                "摘要": _short_text(summary.get("analysis_summary"), limit=72),
            }
        )
    return rows


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


def show_ai_decision_panel_beta_task() -> None:
    st.header("🧩 AI决策面板 (Beta)")
    st.caption("任务化复刻模式：只展示原算法输出的 raw_result/context_snapshot，不做本地策略点位推算。")

    store = JobStore()

    if "beta_task_job_id" not in st.session_state:
        st.session_state.beta_task_job_id = ""

    code = _resolve_code_input()
    report_type = "simple"
    control_expanded = not bool(st.session_state.beta_task_job_id)
    with st.expander("任务操作区（提交 / 队列 / 归档）", expanded=control_expanded):
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

            st.markdown("#### 已完成结果（重点）")
            if succeeded_jobs:
                done_rows = _build_completed_archive_rows(store, succeeded_jobs)
                st.dataframe(done_rows, use_container_width=True, hide_index=True)

                current_done_index = 0
                current_id = st.session_state.beta_task_job_id
                for idx, row in enumerate(done_rows):
                    if row["任务ID"] == current_id:
                        current_done_index = idx
                        break

                done_labels = [
                    (
                        f"{row['创建时间']} | {row['代码']} | "
                        f"评分{row['评分']} | {row['建议']}/{row['趋势']}"
                    )
                    for row in done_rows
                ]
                done_selected = st.selectbox(
                    "选择已完成任务",
                    done_labels,
                    index=current_done_index,
                    key="beta_done_jobs",
                )
                done_idx = done_labels.index(done_selected)
                done_job_id = done_rows[done_idx]["任务ID"]

                p1, p2 = st.columns([1, 1])
                with p1:
                    if st.button("加载该已完成任务", key="beta_load_done_btn"):
                        st.session_state.beta_task_job_id = done_job_id
                        st.success(f"已加载任务: {done_job_id}")
                        st.rerun()
                with p2:
                    preview = done_rows[done_idx]
                    st.caption(
                        f"预览: 评分 {preview['评分']} | 建议 {preview['建议']} | "
                        f"趋势 {preview['趋势']} | 摘要 {preview['摘要']}"
                    )
            else:
                st.info("暂无已完成任务。")

            st.markdown("#### 失败任务（可重试）")
            if failed_jobs:
                failed_rows = _build_failed_archive_rows(failed_jobs)
                st.dataframe(failed_rows, use_container_width=True, hide_index=True)

                failed_labels = [
                    f"{row['创建时间']} | {row['代码']} | {_short_text(row['错误'], limit=36)}"
                    for row in failed_rows
                ]
                failed_selected = st.selectbox(
                    "选择失败任务",
                    failed_labels,
                    index=0,
                    key="beta_failed_jobs",
                )
                failed_idx = failed_labels.index(failed_selected)
                failed_job_id = failed_rows[failed_idx]["任务ID"]
                failed_job = next((j for j in failed_jobs if j.get("job_id") == failed_job_id), None)

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

    debug_mode = st.toggle("调试模式（显示 raw_result / context_snapshot JSON）", value=False, key="beta_debug_mode")
    if not debug_mode:
        st.caption("当前为标准视图：结果区按单页集中布局展示。")

    job_id = st.session_state.beta_task_job_id
    if not job_id:
        st.caption("请选择或提交一个任务后查看结果。")
        return

    job_detail = store.get_job(job_id) or {}
    status = get_job_status(job_id, store=store)
    st.markdown("### 分析结果")
    with st.container(border=True):
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
            f"进度: {int(float(status.get('progress', 0.0)) * 100)}% | "
            f"说明: {status.get('message', '-')}"
        )
        st.progress(float(status.get("progress", 0.0)))

    if status.get("status") == "failed":
        err = job_detail.get("error_message") or status.get("message") or "任务失败"
        st.error(err)
        return

    if status.get("status") != "succeeded":
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
    st.markdown(f"#### {title_text}")
    st.markdown(
        f"`QueryID:` {meta.get('query_id') or '-'}"
        f" | `时间:` {meta.get('analysis_time') or '-'}"
        f" | `类型:` {job_detail.get('report_type') or '-'}"
        f" | `来源:` {meta.get('source') or '-'}"
    )
    if analysis_date:
        st.info(f"分析基准交易日: {analysis_date}（Beta 页面按原算法结果展示，不做本地重算）")

    summary_data = _extract_summary(raw_result)
    strategy_data = _extract_strategy(raw_result)
    intelligence_data = _extract_intelligence(raw_result)
    core_data = _extract_core_conclusion(raw_result)
    perspective_data = _extract_data_perspective(raw_result)

    _show_summary_cards(summary_data)
    _show_conclusion(summary_data)
    _show_strategy_cards(strategy_data)
    st.caption("策略点位按原算法结果直接展示，不做本地推算。")

    with st.expander("补充视角（核心结论/数据视角/情报与风险）", expanded=False):
        _show_core_conclusion_block(core_data)
        _show_data_perspective_block(perspective_data)
        _show_intelligence_block(intelligence_data)

    if debug_mode:
        with st.expander("调试数据（raw_result / context_snapshot）", expanded=False):
            st.json(_safe_json(raw_result))
            st.json(_safe_json(context_snapshot))
