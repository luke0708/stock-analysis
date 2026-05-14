"""
A股资金流向智能分析系统 - 统一入口 (v4.0)
聚焦双核心：个股资金流向 + AI 投顾
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from stock_analysis.visualization.styling import apply_global_styles
from stock_analysis.ui.analysis_page import show_analysis_page
from stock_analysis.ui.ai_advisor import show_ai_analysis
from stock_analysis.ui.beta_task_page import (
    show_ai_decision_panel_beta_result_fullscreen,
    show_ai_decision_panel_beta_task,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)

st.set_page_config(
    page_title="A股资金流向智能分析",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded"
)


def _query_value(raw_value: object) -> str:
    if isinstance(raw_value, list):
        if not raw_value:
            return ""
        raw_value = raw_value[0]
    if raw_value is None:
        return ""
    return str(raw_value).strip()


def _clear_navigation_query_params() -> None:
    qp = st.query_params
    for key in ("nav", "job_id"):
        try:
            if key in qp:
                del qp[key]
        except Exception:
            continue

    nav_after = _query_value(qp.get("nav"))
    job_after = _query_value(qp.get("job_id"))
    if nav_after or job_after:
        try:
            qp.clear()
        except Exception:
            logging.getLogger(__name__).warning("Failed to clear query params nav/job_id")


def _consume_query_navigation_intent() -> bool:
    qp = st.query_params
    nav = _query_value(qp.get("nav"))
    job_id = _query_value(qp.get("job_id"))
    if not nav and not job_id:
        st.session_state.pop("_query_nav_consumed_token", None)
        return False

    if nav not in {"beta_full", "beta_panel"}:
        return False

    nav_token = f"{nav}|{job_id}"
    if st.session_state.get("_query_nav_consumed_token") == nav_token:
        _clear_navigation_query_params()
        return False

    st.session_state["_query_nav_consumed_token"] = nav_token
    consumed = False

    if nav == "beta_full":
        st.session_state["page"] = "🧾 分析结果全屏 (Beta)"
        consumed = True
    elif nav == "beta_panel":
        st.session_state["page"] = "🧩 决策面板 Beta（冻结）"
        consumed = True

    if job_id:
        st.session_state["beta_task_job_id"] = job_id
        consumed = True

    if consumed:
        _clear_navigation_query_params()
    return consumed


def _show_system_page(cache_mgr) -> None:
    """系统管理页：复盘统计 / 缓存状态 / 回填日志 / 运维工具。"""
    import sqlite3
    from stock_analysis.analysis.advice_journal import AdviceJournal

    st.header("⚙️ 系统管理")

    # ── 复盘统计 ──────────────────────────────────────────────────
    with st.expander("📊 AI 投顾复盘统计", expanded=True):
        try:
            journal = AdviceJournal()
            stats = journal.get_summary_stats()

            # KPI 汇总行
            with journal._conn() as conn:
                agg = conn.execute(
                    "SELECT COUNT(*) AS total, "
                    "SUM(CASE WHEN review_status='reviewed' THEN 1 ELSE 0 END) AS reviewed, "
                    "SUM(CASE WHEN review_status='pending'  THEN 1 ELSE 0 END) AS pending "
                    "FROM advice_log"
                ).fetchone()
            total    = agg["total"]    or 0
            reviewed = agg["reviewed"] or 0
            pending  = agg["pending"]  or 0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("总建议数", total)
            k2.metric("已复盘", reviewed)
            k3.metric("待回填", pending)
            k4.metric("复盘率", f"{reviewed/total*100:.0f}%" if total else "—")

            # 按 prompt 版本分组表格
            if stats:
                import pandas as pd
                df_stats = pd.DataFrame(stats)
                df_stats = df_stats.rename(columns={
                    "prompt_version": "版本",
                    "total":          "总条数",
                    "reviewed":       "已复盘",
                    "avg_t1_pct":     "T+1均涨幅(%)",
                    "avg_t5_pct":     "T+5均涨幅(%)",
                })
                for col in ["T+1均涨幅(%)", "T+5均涨幅(%)"]:
                    df_stats[col] = df_stats[col].apply(
                        lambda v: f"{v:+.2f}" if v is not None else "—"
                    )
                st.dataframe(df_stats, use_container_width=True, hide_index=True)
            else:
                st.info("暂无复盘数据，生成 AI 建议后自动记录。")

            # 手动触发回填
            st.write("")
            col_btn, col_tip = st.columns([1, 3])
            with col_btn:
                if st.button("🔄 立即回填 T+1/T+5"):
                    with st.spinner("回填中，请稍候…"):
                        n = journal.follow_up_pending()
                    st.success(f"回填完成，更新 {n} 条")
                    st.rerun()
            with col_tip:
                st.caption("launchd 每天 16:10 自动触发，此按钮用于手动补跑")

        except Exception as exc:
            st.error(f"复盘统计加载失败：{exc}")

    # ── 数据缓存状态 ──────────────────────────────────────────────
    with st.expander("💾 数据缓存状态（stock_cache.db）", expanded=True):
        cache_db = Path(__file__).parent.parent.parent / "data" / "stock_cache.db"
        if cache_db.exists():
            size_mb = cache_db.stat().st_size / 1024 / 1024
            st.caption(f"文件大小：{size_mb:.2f} MB　路径：{cache_db}")
            try:
                conn = sqlite3.connect(cache_db, timeout=3)
                tables = [r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()]
                rows_data = {}
                for t in tables:
                    try:
                        cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                        rows_data[t] = cnt
                    except Exception:
                        rows_data[t] = "?"
                conn.close()

                import pandas as pd
                df_cache = pd.DataFrame(
                    [{"表名": t, "行数": c} for t, c in rows_data.items()]
                )
                st.dataframe(df_cache, use_container_width=True, hide_index=True)
            except Exception as exc:
                st.warning(f"无法读取缓存DB：{exc}")
        else:
            st.info("stock_cache.db 尚未创建，打开个股资金流向页后自动生成。")

    # ── 自动回填日志 ──────────────────────────────────────────────
    with st.expander("🕐 自动回填日志（最近 15 行）", expanded=False):
        log_path = Path(__file__).parent.parent.parent / "logs" / "backfill_t1.log"
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").splitlines()
            tail = "\n".join(lines[-15:]) if lines else "（日志为空）"
            st.code(tail, language="text")
            st.caption(f"完整日志：{log_path}")
        else:
            st.info("日志文件尚未生成，launchd 首次触发后出现（每天 16:10）。")

    # ── 缓存维护 ──────────────────────────────────────────────────
    with st.expander("🗑️ 缓存维护", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("清理运行时内存缓存，解决数据更新延迟问题。stock_cache.db 不受影响。")
        with col2:
            if st.button("🧹 一键清理"):
                st.cache_data.clear()
                cache_mgr.clear_session_cache()
                st.success("缓存已清理，请刷新页面")

    # ── 关于 ──────────────────────────────────────────────────────
    with st.expander("ℹ️ 关于版本 v4.0", expanded=False):
        st.info("""
        **核心模块**: 个股资金流向 + AI 投顾（DeepSeek）
        **数据引擎**: AkShare（主力）+ yfinance（fallback）
        **数据沉淀**: stock_cache.db（L1/L2/L4 三层）
        **复盘追踪**: advice_journal.db + launchd 每日 16:10 自动回填
        **决策面板 Beta**: 算法移植实验，冻结中
        """)


def main():
    apply_global_styles()

    if _consume_query_navigation_intent():
        st.rerun()

    target = st.session_state.pop("_navigate_to", None)
    if target == "📈 个股分析":
        st.session_state["page"] = "📈 个股资金流向"
    elif target == "🤖 AI 投顾":
        st.session_state["page"] = "🤖 AI 投顾"
    elif target in {"🧩 决策面板 Beta（冻结）", "🧾 分析结果全屏 (Beta)"}:
        st.session_state["page"] = target

    nav_items = [
        "📈 个股资金流向",
        "🤖 AI 投顾",
        "🧩 决策面板 Beta（冻结）",
        "⚙️ 系统管理",
    ]

    with st.sidebar:
        st.title("📈 A股智能分析")
        st.caption("v4.0 | AI 驱动")
        st.write("")

        default_page = st.session_state.get("page", "📈 个股资金流向")
        if default_page not in nav_items:
            default_page = "📈 个股资金流向"

        page = st.radio(
            "导航",
            nav_items,
            index=nav_items.index(default_page),
            key="page",
            label_visibility="collapsed",
        )

        st.markdown("---")
        from stock_analysis.core.cache_manager import CacheManager
        cache_mgr = CacheManager()
        stats = cache_mgr.get_cache_size()
        if stats["has_data"]:
            st.caption(f"💾 缓存: ~{stats.get('estimated_memory_mb', 0):.1f}MB")

    if page == "📈 个股资金流向":
        show_analysis_page()

    elif page == "🤖 AI 投顾":
        show_ai_analysis()

    elif page == "🧩 决策面板 Beta（冻结）":
        show_ai_decision_panel_beta_task()

    elif page == "🧾 分析结果全屏 (Beta)":
        show_ai_decision_panel_beta_result_fullscreen()

    elif page == "⚙️ 系统管理":
        _show_system_page(cache_mgr)


if __name__ == "__main__":
    main()
