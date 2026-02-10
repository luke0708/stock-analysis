"""
A股资金流向智能分析系统 - 统一入口 (v2.2)
整合个股分析、市场仪表盘、自选股管理等功能
"""
import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from stock_analysis.visualization.styling import apply_global_styles
from stock_analysis.ui.dashboard import show_dashboard
from stock_analysis.ui.analysis_page import show_analysis_page
from stock_analysis.ui.market_page import show_market_page
from stock_analysis.ui.watchlist_page import show_watchlist_page
from stock_analysis.ui.future_features import (
    show_backtesting,
    show_ai_analysis,
)
from stock_analysis.ui.beta_task_page import show_ai_decision_panel_beta_task
from stock_analysis.ui.global_markets_page import show_global_markets
from stock_analysis.ui.comparison_page import show_comparison_page
from stock_analysis.ui.alert_page import show_alert_page
from stock_analysis.core.prefetch import start_market_prefetch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)

# 页面配置 (必须在所有其他 streamlit 命令之前)
st.set_page_config(
    page_title="A股资金流向智能分析",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded"
)

def main():
    # 1. 应用全局样式 (v2.2 机构暗黑风)
    apply_global_styles()

    start_market_prefetch()
    
    # 2. 处理页面跳转
    if '_navigate_to' in st.session_state:
        # Pass
        pass 

    with st.sidebar:
        st.title("📈 A股智能分析")
        st.caption("v2.2 Pro | 资金驱动")
        
        st.write("") # Spacer
        
        # 导航菜单 - 分组式
        menu_options = ["📊 市场全景", "🔍 智能分析", "🧪 策略回测", "⚙️ 系统管理"]
        default_menu = st.session_state.get("menu_category", "🔍 智能分析")
        if default_menu not in menu_options:
            default_menu = "🔍 智能分析"
        menu_category = st.radio(
            "导航区域",
            menu_options,
            index=menu_options.index(default_menu),
            key="menu_category",
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        selected_sub_page = ""
        
        if menu_category == "📊 市场全景":
            selected_sub_page = st.radio(
                "市场模块",
                ["🚀 仪表盘 (Dashboard)", "🔥 深度热点 & 龙虎榜", "🌍 全球市场 (Pro)"],
                index=0,
                key="market_sub_page"
            )
            
        elif menu_category == "🔍 智能分析":
            analysis_options = [
                "📈 个股资金流向",
                "🔔 实时预警",
                "📋 我的自选股",
                "⚖️ 多股对比 (Pro)",
                "🤖 AI 投顾 (Pro)",
                "🧩 AI决策面板 (Beta)",
            ]
            default_analysis = st.session_state.get("analysis_sub_page", "📈 个股资金流向")
            if default_analysis not in analysis_options:
                default_analysis = "📈 个股资金流向"
            selected_sub_page = st.radio(
                "分析模块",
                analysis_options,
                index=analysis_options.index(default_analysis),
                key="analysis_sub_page"
            )
            
        elif menu_category == "🧪 策略回测":
            selected_sub_page = "策略回测实验室"
            
        elif menu_category == "⚙️ 系统管理":
            selected_sub_page = "全局设置"
        
        # 底部状态栏
        st.markdown("---")
        from stock_analysis.core.cache_manager import CacheManager
        cache_mgr = CacheManager()
        stats = cache_mgr.get_cache_size()
        if stats['has_data']:
            st.caption(f"💾 缓存: ~{stats.get('estimated_memory_mb', 0):.1f}MB")
            
    # 处理跳转逻辑覆盖
    if '_navigate_to' in st.session_state:
        target = st.session_state._navigate_to
        if target == "📈 个股分析":
            menu_category = "🔍 智能分析"
            selected_sub_page = "📈 个股资金流向"
            st.session_state.menu_category = menu_category
            st.session_state.analysis_sub_page = selected_sub_page
        del st.session_state['_navigate_to']
            
    # 路由分发
    if selected_sub_page == "🚀 仪表盘 (Dashboard)":
        show_dashboard()
        
    elif selected_sub_page == "🔥 深度热点 & 龙虎榜":
        show_market_page()
        
    elif selected_sub_page == "🌍 全球市场 (Pro)":
        show_global_markets()
        
    elif selected_sub_page == "📈 个股资金流向":
        show_analysis_page()
        
    elif selected_sub_page == "🔔 实时预警":
        show_alert_page()
        
    elif selected_sub_page == "📋 我的自选股":
        show_watchlist_page()
        
    elif selected_sub_page == "⚖️ 多股对比 (Pro)":
        show_comparison_page()
        
    elif selected_sub_page == "🤖 AI 投顾 (Pro)":
        show_ai_analysis()

    elif selected_sub_page == "🧩 AI决策面板 (Beta)":
        show_ai_decision_panel_beta_task()
        
    elif selected_sub_page == "策略回测实验室":
        show_backtesting()
        
    elif selected_sub_page == "全局设置":
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
                    
        with st.expander("ℹ️ 关于版本 v2.2", expanded=True):
            st.info("""
            **UI 架构升级**: 引入 Institutional Dark Mode 设计语言。
            **新增功能**: 市场全局仪表盘 (Dashboard)。
            **核心引擎**: AkShare (Primary) + Tushare (Backup).
            **路线图**: 已预展示 P2/P5/P7/P8 功能入口。
            """)

if __name__ == "__main__":
    main()
