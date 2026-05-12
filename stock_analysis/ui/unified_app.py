"""
A股资金流向智能分析系统 - 统一入口 (v3.0)
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
        st.caption("v3.0 | AI 驱动")
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
        st.header("⚙️ 系统管理")
        with st.expander("🗑️ 缓存维护", expanded=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write("清理本地缓存文件和运行时内存数据，解决数据更新延迟问题。")
            with col2:
                if st.button("🧹 一键清理"):
                    st.cache_data.clear()
                    cache_mgr.clear_session_cache()
                    st.success("缓存已清理，请刷新页面")

        with st.expander("ℹ️ 关于版本 v3.0", expanded=True):
            st.info("""
            **核心模块**: 个股资金流向 + AI 投顾（DeepSeek）
            **数据引擎**: AkShare（主力）
            **决策面板 Beta**: 算法移植实验，冻结中
            """)


if __name__ == "__main__":
    main()
