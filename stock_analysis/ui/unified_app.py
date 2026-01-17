"""
A股资金流向智能分析系统 - 统一入口
整合个股分析、市场热点、自选股管理等功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from stock_analysis.ui.analysis_page import show_analysis_page
from stock_analysis.ui.market_page import show_market_page
from stock_analysis.ui.watchlist_page import show_watchlist_page

# 页面配置 (必须在所有其他 streamlit 命令之前)
st.set_page_config(
    page_title="A股智能分析",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded"
)

def main():
    # 自定义样式
    st.markdown("""
        <style>
        .stButton>button { width: 100%; }
        .sidebar-content { padding: 1rem; }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("📈 A股智能分析")
        st.caption("v1.1 | 资金流向 & 市场热点")
        
        # 导航菜单
        selected_page = st.radio(
            "功能导航",
            ["🏠 市场热点", "📈 个股分析", "📋 我的自选", "⚙️ 设置"],
            index=1 # 默认个股分析
        )
        
        st.markdown("---")
        
        # 显示当前缓存状态 (所有页面通用)
        from stock_analysis.core.cache_manager import CacheManager
        cache_mgr = CacheManager()
        stats = cache_mgr.get_cache_size()
        if stats['has_data']:
            st.caption(f"💾 缓存占用: ~{stats.get('estimated_memory_mb', 0):.1f}MB")
    
    # 路由逻辑
    if selected_page == "🏠 市场热点":
        show_market_page()
        
    elif selected_page == "📈 个股分析":
        show_analysis_page()
        
    elif selected_page == "📋 我的自选":
        show_watchlist_page()
        
    elif selected_page == "⚙️ 设置":
        st.header("⚙️ 全局设置")
        
        with st.expander("🗑️ 缓存与存储", expanded=True):
            st.write("清理本地缓存文件和内存数据。")
            if st.button("清理所有缓存"):
                st.cache_data.clear()
                cache_mgr.clear_session_cache()
                cache_mgr.clear_exported_files(keep_recent=0)
                st.success("✅ 已清理所有缓存")
                st.rerun()
                
        with st.expander("ℹ️ 关于系统"):
            st.info("""
            **A股资金流向智能分析系统**
            
            - **版本**: v1.1
            - **数据源**: AkShare + Tushare
            - **功能**: 
                - 实时资金流向监测
                - 板块热点追踪
                - 龙虎榜分析
            """)

if __name__ == "__main__":
    main()
