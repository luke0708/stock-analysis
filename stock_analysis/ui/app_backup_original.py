import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from pathlib import Path
import os
from datetime import datetime

# 导入数据提供者
from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.data.providers.tushare_provider import TushareProvider

# 导入数据清洗
from stock_analysis.data.cleaner import DataCleaner, get_quality_summary

# 导入分析器
from stock_analysis.analysis.flows import FlowAnalyzer
from stock_analysis.analysis.timeseries import TimeSeriesAnalyzer
from stock_analysis.analysis.indicators import IndicatorCalculator
from stock_analysis.analysis.anomaly import AnomalyDetector
from stock_analysis.analysis.order_strength import OrderStrengthAnalyzer

# 导入可视化
from stock_analysis.visualization.charts import ChartGenerator

# 导入帮助文本和缓存管理
from stock_analysis.core.help_text import get_indicator_help, get_all_help_topics
from stock_analysis.core.cache_manager import CacheManager, DataImporter

# 导入新增功能模块
from stock_analysis.analysis.market_hotspot import MarketHotspotAnalyzer, format_hotspot_summary
from stock_analysis.analysis.dragon_tiger import DragonTigerAnalyzer, format_lhb_summary
from stock_analysis.data.news_provider import StockNewsProvider, format_news_summary

from stock_analysis.core.config import settings

def process_imported_data(df):
    """处理导入的CSV数据"""
    # 数据清洗
    cleaner = DataCleaner()
    df_clean, quality_report = cleaner.clean(df)
    
    # 计算指标
    indicator_calc = IndicatorCalculator()
    df_with_indicators = indicator_calc.calculate_all(df_clean)
    
    # 保存到 session_state
    st.session_state.df = df_with_indicators
    st.session_state.actual_source = "CSV导入"
    st.session_state.quality_report = quality_report
    
    # 执行所有分析
    st.session_state.all_analysis = perform_all_analysis(df_with_indicators)
    
    st.success("✅ 数据导入并分析完成！")

def main():
    st.set_page_config(page_title="A股资金流向分析", layout="wide", page_icon="📈")
    
    # 自定义CSS
    st.markdown("""
        <style>
        .big-metric { font-size: 2em; font-weight: bold; }
        .quality-excellent { color: #52c41a; }
        .quality-good { color: #faad14; }
        .quality-poor { color: #ff4d4f; }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("📈 A股资金流向智能分析系统")
    st.caption("增强版 - 多维度分析 + 丰富可视化")
    
    # ===== 侧边栏配置 =====
    with st.sidebar:
        st.header("⚙️ 参数设置")
        
        # 数据源选择
        with st.expander("📥 数据导入", expanded=False):
            import_option = st.radio("选择数据来源", ["实时获取", "导入CSV文件"])
            
            if import_option == "导入CSV文件":
                uploaded_file = st.file_uploader("上传CSV文件", type=['csv'])
                if uploaded_file and st.button("导入并分析"):
                    importer = DataImporter()
                    df, success, msg = importer.import_from_csv(uploaded_file)
                    
                    if success:
                        st.success(msg)
                        # 直接处理导入的数据
                        process_imported_data(df)
                    else:
                        st.error(msg)
        
        stock_code = st.text_input("股票代码", value="300661", help="输入6位股票代码")
        
        st.markdown("---")
        st.subheader("📡 数据源配置")
        
        provider_choice = st.radio(
            "数据源",
            ["Tushare Pro (推荐)", "AkShare (备用)"],
            help="Tushare 数据质量更高但需要 Token"
        )
        
        tushare_token = ""
        if "Tushare" in provider_choice:
            tushare_token = st.text_input(
                "Tushare Token",
                value=os.getenv("TUSHARE_TOKEN", ""),
                type="password",
                help="在 https://tushare.pro 注册后获取"
            )
            
            if not tushare_token:
                st.warning("⚠️ 请先输入 Tushare Token")
                st.markdown("[👉 点击注册获取 Token](https://tushare.pro/register)")
        
        st.markdown("---")
        st.subheader("⚙️ 运行模式")
        analysis_date = st.date_input("分析日期", value=datetime.now())
        
        st.markdown("---")
        
        # 缓存管理
        with st.expander("🗑️ 缓存管理"):
            cache_mgr = CacheManager()
            cache_info = cache_mgr.get_cache_size()
            
            st.write(f"Session 缓存: {cache_info.get('session_items', 0)} 项")
            if cache_info.get('has_data'):
                st.write(f"数据行数: {cache_info.get('data_rows', 0):,}")
                st.write(f"内存占用: ~{cache_info.get('estimated_memory_mb', 0):.1f} MB")
            
            col_clear1, col_clear2 = st.columns(2)
            with col_clear1:
                if st.button("清除缓存"):
                    cache_mgr.clear_session_cache()
                    st.success("✅ 缓存已清除")
                    st.rerun()
            
            with col_clear2:
                if st.button("清理旧文件"):
                    deleted = cache_mgr.clear_exported_files(keep_recent=5)
                    st.success(f"✅ 已删除 {deleted} 个旧文件")
        
        # 帮助文档
        with st.expander("❓ 指标说明"):
            help_topic = st.selectbox("选择指标", get_all_help_topics())
            if help_topic:
                st.markdown(get_indicator_help(help_topic))
        
        st.markdown("---")
        st.markdown("### 📝 使用说明")
        st.markdown("""
        1. 选择数据源（或导入CSV）
        2. 输入股票代码
        3. 选择日期
        4. 点击"开始分析"
        5. 点击图表标题查看帮助
        """)
        
        st.caption("[📖 部署指南](DEPLOYMENT.md)")

    
    # ===== 初始化 Session State =====
    if 'df' not in st.session_state:
        st.session_state.df = None
        st.session_state.actual_source = None
        st.session_state.quality_report = None
        st.session_state.all_analysis = {}
    
    # ===== 开始分析按钮 =====
    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        date_str = analysis_date.strftime("%Y%m%d")
        
        with st.spinner(f"正在获取 {stock_code} 在 {date_str} 的数据..."):
            # 获取数据
            df, actual_source = fetch_data(stock_code, date_str, provider_choice, tushare_token)
            
            if df.empty:
                st.error("未能获取数据，请检查股票代码或稍后重试。")
                return
            
            # 数据清洗
            cleaner = DataCleaner()
            df_clean, quality_report = cleaner.clean(df)
            
            # 计算指标
            indicator_calc = IndicatorCalculator()
            df_with_indicators = indicator_calc.calculate_all(df_clean)
            
            # 保存到 session_state
            st.session_state.df = df_with_indicators
            st.session_state.actual_source = actual_source
            st.session_state.quality_report = quality_report
            
            # 执行所有分析
            with st.spinner("正在执行多维度分析..."):
                st.session_state.all_analysis = perform_all_analysis(df_with_indicators)
    
    # ===== 显示结果 =====
    if st.session_state.df is not None and not st.session_state.df.empty:
        display_results(stock_code, analysis_date)

def fetch_data(stock_code, date_str, provider_choice, tushare_token):
    """获取股票数据"""
    actual_source = None
    df = pd.DataFrame()
    
    if "Tushare" in provider_choice:
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
                raise ValueError("Tushare returned empty data")
        except Exception as e:
            st.warning("⚠️ Tushare 连接失败，自动切换到 AkShare 备用数据源...")
            provider = AkShareProvider()
            df = provider.get_tick_data(stock_code, date_str=date_str)
            actual_source = "AkShare (Fallback)"
    else:
        provider = AkShareProvider()
        df = provider.get_tick_data(stock_code, date_str=date_str)
        actual_source = "AkShare"
    
    return df, actual_source

def perform_all_analysis(df):
    """执行所有分析"""
    results = {}
    
    # 1. 资金流向分析
    flow_analyzer = FlowAnalyzer()
    results['flows'] = flow_analyzer.calculate_flows(df)
    
    # 2. 分时走势分析
    ts_analyzer = TimeSeriesAnalyzer()
    results['timeseries'] = ts_analyzer.analyze(df)
    
    # 3. 技术指标
    indicator_calc = IndicatorCalculator()
    results['indicators'] = indicator_calc.get_summary(df)
    
    # 4. 异常检测
    anomaly_detector = AnomalyDetector()
    results['anomalies'] = anomaly_detector.detect_all(df)
    
    # 5. 买卖盘强度
    strength_analyzer = OrderStrengthAnalyzer()
    results['strength'] = strength_analyzer.analyze(df)
    results['strength_timeseries'] = strength_analyzer.get_minutely_strength(df)
    
    return results

def display_results(stock_code, analysis_date):
    """显示分析结果"""
    df = st.session_state.df
    source = st.session_state.actual_source
    quality = st.session_state.quality_report
    analysis = st.session_state.all_analysis
    
    # ===== 顶部信息栏 =====
    current_time = datetime.now().strftime("%H:%M:%S")
    st.caption(f"最后更新: {current_time} | 数据源: {source} | 数据质量: {quality['quality_score']:.0f}/100")
    
    # ===== 第一行：核心指标卡片 =====
    st.subheader("📊 核心指标")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    ts_data = analysis.get('timeseries', {})
    ind_data = analysis.get('indicators', {})
    flow_data = analysis.get('flows', {})
    
    with col1:
        change_pct = ts_data.get('price_change_pct', 0)
        st.metric(
            "涨跌幅",
            f"{change_pct:+.2f}%",
            delta=f"{ts_data.get('price_change', 0):+.2f}"
        )
    
    with col2:
        st.metric(
            "成交额",
            f"¥{ts_data.get('turnover_total', 0)/1e8:.2f}亿"
        )
    
    with col3:
        st.metric(
            "振幅",
            f"{ts_data.get('amplitude', 0):.2f}%"
        )
    
    with col4:
        vwap = ind_data.get('vwap', 0)
        close = ts_data.get('close_price', 0)
        vs_vwap = ((close - vwap) / vwap * 100) if vwap > 0 else 0
        st.metric(
            "价格 vs VWAP",
            f"{vs_vwap:+.2f}%",
            delta="高于VWAP" if vs_vwap > 0 else "低于VWAP"
        )
    
    with col5:
        large_orders = analysis.get('anomalies', {}).get('summary', {}).get('large_order_count', 0)
        st.metric(
            "大单数量",
            f"{large_orders} 笔"
        )
    
    st.markdown("---")
    
    # ===== 第二行：主图 - K线图 =====
    st.subheader("📈 分时走势 + 成交量")
    
    chart_gen = ChartGenerator()
    candlestick_fig = chart_gen.create_candlestick_chart(df, stock_code)
    st.plotly_chart(candlestick_fig, use_container_width=True)
    
    st.markdown("---")
    
    # ===== 第三行：资金流向分析（2列布局）=====
    st.subheader("💰 资金流向分析")
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        # 资金流向瀑布图
        waterfall_fig = chart_gen.create_flow_waterfall(flow_data)
        st.plotly_chart(waterfall_fig, use_container_width=True)
        
        # 资金流向指标
        st.info(f"""
        **主力净流入**: ¥{flow_data.get('large_order_net_inflow', 0):,.0f}  
        **散户净流入**: ¥{flow_data.get('retail_net_inflow', 0):,.0f}  
        **总成交额**: ¥{flow_data.get('total_turnover', 0):,.0f}
        """)
    
    with col_right:
        # 买卖盘力度图
        strength_ts = analysis.get('strength_timeseries', pd.DataFrame())
        if not strength_ts.empty:
            strength_fig = chart_gen.create_order_strength_chart(strength_ts)
            st.plotly_chart(strength_fig, use_container_width=True)
        
        # 买卖盘强度指标
        strength_data = analysis.get('strength', {})
        st.info(f"""
        **{strength_data.get('advantage', '未知')} {strength_data.get('advantage_emoji', '')}**  
        买盘强度: {strength_data.get('buy_strength', 0):.1f}%  
        卖盘强度: {strength_data.get('sell_strength', 0):.1f}%
        """)
    
    st.markdown("---")
    
    # ===== 第四行：累计涨跌 + 大单追踪 =====
    col_cum, col_orders = st.columns(2)
    
    with col_cum:
        st.subheader("📉 累计涨跌幅")
        if '累计涨跌幅' in df.columns:
            cum_fig = chart_gen.create_cumulative_change_chart(df)
            st.plotly_chart(cum_fig, use_container_width=True)
    
    with col_orders:
        st.subheader("🎯 大单追踪")
        anomalies = analysis.get('anomalies', {})
        large_orders = anomalies.get('large_orders', [])
        
        if large_orders:
            scatter_fig = chart_gen.create_large_orders_scatter(large_orders, df)
            st.plotly_chart(scatter_fig, use_container_width=True)
            
            # 大单列表
            with st.expander(f"查看大单详情 ({len(large_orders)}笔)"):
                for order in large_orders[:10]:  # 只显示前10笔
                    st.text(f"{order['time']} | {order['type']} | ¥{order['amount']:,.0f} ({order['ratio']:.1f}x)")
        else:
            st.info("今日暂无异常大单")
    
    st.markdown("---")
    
    # ===== 第五行：数据质量 + 原始数据 =====
    with st.expander("📋 数据质量报告"):
        st.code(get_quality_summary(quality))
    
    with st.expander(f"查看原始数据 (共 {len(df)} 条)"):
        st.info(f"💡 完整数据已在内存中，包含全部 {len(df)} 条记录。")
        show_rows = st.slider("显示行数", min_value=10, max_value=min(500, len(df)), value=min(100, len(df)), step=10)
        st.dataframe(df.head(show_rows), width='stretch', height=500)
        
        # 保存按钮
        date_str = analysis_date.strftime("%Y%m%d")
        if st.button("💾 保存到项目文件夹", use_container_width=True):
            export_dir = Path("exported_data")
            export_dir.mkdir(exist_ok=True)
            
            csv_filename = f"{stock_code}_{date_str}_data.csv"
            file_path = export_dir / csv_filename
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            
            st.success(f"✅ 文件已保存到: {file_path.absolute()}")
            st.code(f"open {file_path.absolute()}", language="bash")

if __name__ == "__main__":
    main()
