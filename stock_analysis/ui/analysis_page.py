"""
个股分析页面模块
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import os

# 导入分析组件
from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.data.providers.tushare_provider import TushareProvider
from stock_analysis.data.cleaner import DataCleaner, get_quality_summary
from stock_analysis.analysis.flows import FlowAnalyzer
from stock_analysis.analysis.timeseries import TimeSeriesAnalyzer
from stock_analysis.analysis.indicators import IndicatorCalculator
from stock_analysis.analysis.anomaly import AnomalyDetector
from stock_analysis.analysis.order_strength import OrderStrengthAnalyzer
from stock_analysis.visualization.charts import ChartGenerator
from stock_analysis.core.help_text import get_indicator_help, get_all_help_topics
from stock_analysis.core.cache_manager import CacheManager, DataImporter
from stock_analysis.core.config import settings
from stock_analysis.core.storage import StorageManager
from stock_analysis.data.stock_list import get_stock_provider

def show_analysis_page():
    st.header("📈 个股资金流向分析")
    
    # 初始化 Session State
    if 'stock_code' not in st.session_state:
        st.session_state.stock_code = "300661"
    
    # 侧边栏辅助功能
    with st.sidebar:
        st.subheader("🔍 股票搜索")
        stock_provider = get_stock_provider()
        search_query = st.text_input("搜索 (代码/名称/拼音)", placeholder="如: 300661 或 maotai")
        if search_query:
            results = stock_provider.search(search_query)
            if not results.empty:
                st.dataframe(results[['代码', '名称']], hide_index=True)
                # 快捷选择
                selected_code = st.selectbox("选择股票", results['代码'] + " | " + results['名称'])
                if selected_code:
                    code = selected_code.split(" | ")[0]
                    if st.button("分析此股票"):
                        st.session_state.stock_code = code
                        st.rerun()
            else:
                st.caption("未找到匹配股票")
    
    # 主界面输入区
    col_input1, col_input2, col_input3 = st.columns([2, 2, 3])
    
    with col_input1:
        stock_code = st.text_input("股票代码", value=st.session_state.stock_code, key="_input_code", help="输入6位股票代码")
        # 更新 session state
        st.session_state.stock_code = stock_code
        
    with col_input2:
        analysis_date = st.date_input("分析日期", value=datetime.now())
        
    with col_input3:
        # 添加/移除自选股按钮
        storage = StorageManager()
        watchlist_codes = storage.get_watchlist_codes()
        is_in_watchlist = stock_code in watchlist_codes
        
        st.write("") # Spacer
        st.write("") # Spacer
        if is_in_watchlist:
            if st.button("💔 移出自选"):
                storage.remove_from_watchlist(stock_code)
                st.success("已移除")
                st.rerun()
        else:
            if st.button("❤️ 加入自选"):
                # 获取名称 (如果能获取到)
                name = stock_code # 默认
                try:
                    res = stock_provider.search(stock_code, limit=1)
                    if not res.empty:
                        name = res.iloc[0]['名称']
                except:
                    pass
                storage.add_to_watchlist(stock_code, name)
                st.success(f"已加入自选: {name}")
                st.rerun()

    # 数据源选择
    with st.expander("⚙️ 高级设置 (数据源/导入)", expanded=False):
        import_option = st.radio("数据模式", ["实时获取", "导入CSV文件"], horizontal=True)
        
        if import_option == "导入CSV文件":
             uploaded_file = st.file_uploader("上传CSV文件", type=['csv'])
             if uploaded_file and st.button("导入并分析"):
                importer = DataImporter()
                df, success, msg = importer.import_from_csv(uploaded_file)
                if success:
                    st.success(msg)
                    process_imported_data(df)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            # 修改：AkShare 设为默认推荐
            provider_choice = st.radio("API源", ["AkShare (推荐)", "Tushare Pro"], horizontal=True)
            tushare_token = ""
            if "Tushare" in provider_choice:
                tushare_token = st.text_input("Tushare Token", value=os.getenv("TUSHARE_TOKEN", ""), type="password")

    # 开始分析按钮
    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        date_str = analysis_date.strftime("%Y%m%d")
        
        if import_option == "实时获取":
            with st.spinner(f"正在获取 {stock_code} 在 {date_str} 的数据..."):
                df, actual_source = fetch_data(stock_code, date_str, provider_choice, tushare_token)
                
                if df.empty:
                    st.error("未能获取数据，请检查股票代码或稍后重试。")
                else:
                    process_and_display(df, stock_code, analysis_date, actual_source)
    
    # 显示已存在的结果 (如果有)
    if 'df' in st.session_state and st.session_state.df is not None:
        display_results(st.session_state.get('last_stock_code', stock_code), analysis_date)

# --- 辅助函数 ---

def process_imported_data(df):
    cleaner = DataCleaner()
    df_clean, quality_report = cleaner.clean(df)
    indicator_calc = IndicatorCalculator()
    df_with_indicators = indicator_calc.calculate_all(df_clean)
    
    st.session_state.df = df_with_indicators
    st.session_state.actual_source = "CSV导入"
    st.session_state.quality_report = quality_report
    st.session_state.all_analysis = perform_all_analysis(df_with_indicators)
    st.session_state.last_stock_code = "导入数据"

def process_and_display(df, stock_code, analysis_date, actual_source):
    cleaner = DataCleaner()
    df_clean, quality_report = cleaner.clean(df)
    indicator_calc = IndicatorCalculator()
    df_with_indicators = indicator_calc.calculate_all(df_clean)
    
    st.session_state.df = df_with_indicators
    st.session_state.actual_source = actual_source
    st.session_state.quality_report = quality_report
    st.session_state.all_analysis = perform_all_analysis(df_with_indicators)
    st.session_state.last_stock_code = stock_code

def fetch_data(stock_code, date_str, provider_choice, tushare_token):
    actual_source = None
    df = pd.DataFrame()
    
    # 根据选择的逻辑
    use_tushare = "Tushare" in provider_choice
    
    if use_tushare:
        if not tushare_token:
            st.error("❌ 请先输入 Tushare Token")
            return df, actual_source
        try:
            os.environ["TUSHARE_TOKEN"] = tushare_token
            settings.TUSHARE_TOKEN = tushare_token
            provider = TushareProvider()
            df = provider.get_tick_data(stock_code, date_str=date_str)
            if not df.empty:
                actual_source = "Tushare Pro"
            else:
                raise ValueError("Empty data")
        except:
            st.warning("切换到 AkShare...")
            provider = AkShareProvider()
            df = provider.get_tick_data(stock_code, date_str=date_str)
            actual_source = "AkShare (Fallback)"
    else:
        # AkShare 优先
        provider = AkShareProvider()
        df = provider.get_tick_data(stock_code, date_str=date_str)
        actual_source = "AkShare"
    
    return df, actual_source

def perform_all_analysis(df):
    results = {}
    results['flows'] = FlowAnalyzer().calculate_flows(df)
    results['timeseries'] = TimeSeriesAnalyzer().analyze(df)
    results['indicators'] = IndicatorCalculator().get_summary(df)
    results['anomalies'] = AnomalyDetector().detect_all(df)
    
    sa = OrderStrengthAnalyzer()
    results['strength'] = sa.analyze(df)
    results['strength_timeseries'] = sa.get_minutely_strength(df)
    return results

def display_results(stock_code, analysis_date):
    df = st.session_state.df
    source = st.session_state.actual_source
    quality = st.session_state.quality_report
    analysis = st.session_state.all_analysis
    
    # 顶部状态栏
    current_time = datetime.now().strftime("%H:%M:%S")
    st.caption(f"最后更新: {current_time} | 分析对象: {stock_code} | 数据源: {source} | 质量: {quality['quality_score']:.0f}/100")
    
    # ===== 第一行：核心指标卡片 (恢复5列布局) =====
    ts_data = analysis.get('timeseries', {})
    ind_data = analysis.get('indicators', {})
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        change_pct = ts_data.get('price_change_pct', 0)
        st.metric("涨跌幅", f"{change_pct:+.2f}%", delta=f"{ts_data.get('price_change', 0):+.2f}")
    
    with col2:
        st.metric("成交额", f"¥{ts_data.get('turnover_total', 0)/1e8:.2f}亿")
    
    with col3:
        st.metric("振幅", f"{ts_data.get('amplitude', 0):.2f}%")
    
    with col4:
        vwap = ind_data.get('vwap', 0)
        close = ts_data.get('close_price', 0)
        vs_vwap = ((close - vwap) / vwap * 100) if vwap > 0 else 0
        st.metric("价格 vs VWAP", f"{vs_vwap:+.2f}%", delta="高于均价" if vs_vwap > 0 else "低于均价")
    
    with col5:
        large_orders = analysis.get('anomalies', {}).get('summary', {}).get('large_order_count', 0)
        st.metric("大单数量", f"{large_orders} 笔")
    
    st.markdown("---")

    # ===== 第二行：K线图 =====
    cg = ChartGenerator()
    st.subheader("📈 分时走势 + 成交量")
    st.plotly_chart(cg.create_candlestick_chart(df, stock_code), use_container_width=True)
    
    st.markdown("---")
    
    # ===== 第三行：资金流向 (2列) =====
    st.subheader("💰 资金流向分析")
    col_l, col_r = st.columns(2)
    
    waterfall_fig = cg.create_flow_waterfall(analysis.get('flows', {}))
    strength_fig = cg.create_order_strength_chart(analysis.get('strength_timeseries', pd.DataFrame()))
    
    with col_l:
        st.plotly_chart(waterfall_fig, use_container_width=True)
    with col_r:
        st.plotly_chart(strength_fig, use_container_width=True)
        
    st.markdown("---")
    
    # ===== 第四行：累计涨跌 + 大单追踪 (恢复丢失的图表) =====
    col_cum, col_orders = st.columns(2)
    
    with col_cum:
        st.subheader("📉 累计涨跌幅")
        if '累计涨跌幅' in df.columns:
            cum_fig = cg.create_cumulative_change_chart(df)
            st.plotly_chart(cum_fig, use_container_width=True)
    
    with col_orders:
        st.subheader("🎯 大单追踪")
        anomalies = analysis.get('anomalies', {})
        large_orders_list = anomalies.get('large_orders', [])
        
        if large_orders_list:
            scatter_fig = cg.create_large_orders_scatter(large_orders_list, df)
            st.plotly_chart(scatter_fig, use_container_width=True)
        else:
            st.info("今日暂无异常大单")
            
    # 保存功能
    with st.expander("💾 保存数据"):
         date_str = analysis_date.strftime("%Y%m%d")
         csv = df.to_csv(index=False).encode('utf-8-sig')
         st.download_button("下载 CSV", csv, f"{stock_code}_{date_str}.csv", "text/csv")
