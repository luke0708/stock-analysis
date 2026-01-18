"""
多股对比分析页面
"""
import streamlit as st
from datetime import datetime

from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.data.stock_list import get_stock_provider
from stock_analysis.analysis.flows import FlowAnalyzer
from stock_analysis.visualization.charts import ChartGenerator

def show_comparison_page():
    st.header("⚖️ 多股对比分析 (Pro)")
    
    # 初始化 Session State
    if 'comp_stock_a' not in st.session_state:
        st.session_state.comp_stock_a = "600519"  # 茅台
    if 'comp_stock_b' not in st.session_state:
        st.session_state.comp_stock_b = "000858"  # 五粮液
        
    # 输入区域
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.subheader("股票 A")
        stock_a = st.text_input("代码 A", value=st.session_state.comp_stock_a, key="input_a")
        st.session_state.comp_stock_a = stock_a
        
    with col2:
        st.subheader("股票 B")
        stock_b = st.text_input("代码 B", value=st.session_state.comp_stock_b, key="input_b")
        st.session_state.comp_stock_b = stock_b
        
    with col3:
        st.subheader("分析日期")
        date = st.date_input("日期", value=datetime.now())
        run_btn = st.button("开始对比", type="primary", use_container_width=True)

    if run_btn:
        compare_stocks(stock_a, stock_b, date)

def compare_stocks(code_a, code_b, date):
    """执行对比逻辑"""
    provider = AkShareProvider()
    stock_provider = get_stock_provider()
    flow_analyzer = FlowAnalyzer()
    chart_generator = ChartGenerator()
    
    date_str = date.strftime("%Y%m%d")
    
    with st.status("正在获取对比数据...", expanded=True) as status:
        # 获取股票名称
        name_a = _get_name(stock_provider, code_a)
        name_b = _get_name(stock_provider, code_b)
        
        st.write(f"正在获取 {name_a} ({code_a})...")
        df_a = provider.get_tick_data(code_a, date_str)
        
        st.write(f"正在获取 {name_b} ({code_b})...")
        df_b = provider.get_tick_data(code_b, date_str)
        
        if df_a.empty or df_b.empty:
            st.error("无法获取数据，请检查代码或日期")
            status.update(label="数据获取失败", state="error")
            return
            
        status.update(label="数据获取成功，开始分析", state="complete")
        
    # 大屏展示关键指标
    st.markdown("### 📊 核心指标对比")
    
    def _get_price_pair(df):
        close_col = None
        for col in ['收盘', '成交价格', '价格', '最新价']:
            if col in df.columns:
                close_col = col
                break
        if close_col is None or df.empty:
            return 0.0, 0.0
        open_col = '开盘' if '开盘' in df.columns else close_col
        return df[open_col].iloc[0], df[close_col].iloc[-1]

    flow_summary_a = flow_analyzer.calculate_flows(df_a)
    flow_summary_b = flow_analyzer.calculate_flows(df_b)

    open_a, close_a = _get_price_pair(df_a)
    open_b, close_b = _get_price_pair(df_b)

    pct_a = (close_a - open_a) / open_a * 100 if open_a else 0
    pct_b = (close_b - open_b) / open_b * 100 if open_b else 0
    vol_a = flow_summary_a.get('total_turnover', 0)
    vol_b = flow_summary_b.get('total_turnover', 0)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{name_a}", f"{close_a:.2f}", f"{pct_a:.2f}%")
    c1.metric(f"成交额", f"{vol_a/1e8:.2f}亿")
    
    c2.metric(f"{name_b}", f"{close_b:.2f}", f"{pct_b:.2f}%")
    c2.metric(f"成交额", f"{vol_b/1e8:.2f}亿")
    
    # 差异
    diff_pct = pct_a - pct_b
    c3.metric(f"涨幅差异 (A-B)", f"{diff_pct:.2f}%", delta=diff_pct)

    net_a = flow_summary_a.get('large_order_net_inflow', 0) + flow_summary_a.get('retail_net_inflow', 0)
    net_b = flow_summary_b.get('large_order_net_inflow', 0) + flow_summary_b.get('retail_net_inflow', 0)
    net_diff = net_a - net_b
    c4.metric("净流入差异 (A-B)", f"{net_diff/1e8:.2f}亿")
    
    # 图表区域
    st.markdown("---")
    tab1, tab2 = st.tabs(["📈 走势叠加", "💰 资金流对比"])
    
    flow_series_a = flow_analyzer.calculate_flow_series(df_a)
    flow_series_b = flow_analyzer.calculate_flow_series(df_b)
    
    with tab1:
        fig_price = chart_generator.create_comparison_price_chart(df_a, df_b, name_a, name_b)
        st.plotly_chart(fig_price, use_container_width=True)
        
    with tab2:
        if flow_series_a.empty or flow_series_b.empty:
            st.warning("资金流数据不足，暂无法绘制对比图。")
        else:
            fig_flow = chart_generator.create_comparison_flow_chart(
                flow_series_a,
                flow_series_b,
                name_a,
                name_b
            )
            st.plotly_chart(fig_flow, use_container_width=True)
            st.caption("注：实线对应左轴，虚线对应右轴。向上代表净流入，向下代表净流出。")

def _get_name(provider, code):
    try:
        res = provider.search(code, limit=1)
        if not res.empty:
            return res.iloc[0]['名称']
    except:
        pass
    return code
