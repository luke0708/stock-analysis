"""
多股对比分析页面
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.data.cleaner import DataCleaner
from stock_analysis.data.stock_list import get_stock_provider
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
    cleaner = DataCleaner()
    stock_provider = get_stock_provider()
    
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
    
    # 简易计算
    close_a = df_a['收盘'].iloc[-1]
    open_a = df_a['开盘'].iloc[0]
    pct_a = (close_a - open_a) / open_a * 100
    vol_a = df_a['成交额(元)'].sum()
    
    close_b = df_b['收盘'].iloc[-1]
    open_b = df_b['开盘'].iloc[0]
    pct_b = (close_b - open_b) / open_b * 100
    vol_b = df_b['成交额(元)'].sum()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{name_a}", f"{close_a:.2f}", f"{pct_a:.2f}%")
    c1.metric(f"成交额", f"{vol_a/1e8:.2f}亿")
    
    c2.metric(f"{name_b}", f"{close_b:.2f}", f"{pct_b:.2f}%")
    c2.metric(f"成交额", f"{vol_b/1e8:.2f}亿")
    
    # 差异
    diff_pct = pct_a - pct_b
    c3.metric(f"涨幅差异 (A-B)", f"{diff_pct:.2f}%", delta=diff_pct)
    
    # 图表区域
    st.markdown("---")
    tab1, tab2 = st.tabs(["📈 走势叠加", "💰 资金流对比"])
    
    # 预处理数据 for charts
    df_a['时间'] = pd.to_datetime(df_a['时间'])
    df_b['时间'] = pd.to_datetime(df_b['时间'])
    
    # 归一化价格 (Base 0%)
    df_a['Norm_Price'] = (df_a['收盘'] - df_a['开盘'].iloc[0]) / df_a['开盘'].iloc[0] * 100
    df_b['Norm_Price'] = (df_b['收盘'] - df_b['开盘'].iloc[0]) / df_b['开盘'].iloc[0] * 100
    
    with tab1:
        fig_price = go.Figure()
        fig_price.add_trace(go.Scatter(x=df_a['时间'], y=df_a['Norm_Price'], name=f"{name_a}", line=dict(color='#ff4d4f', width=2)))
        fig_price.add_trace(go.Scatter(x=df_b['时间'], y=df_b['Norm_Price'], name=f"{name_b}", line=dict(color='#1890ff', width=2)))
        fig_price.update_layout(title="日内涨幅走势叠加 (%)", hovermode="x unified", template="plotly_white")
        fig_price.add_hline(y=0, line_dash="dash", line_color="gray")
        st.plotly_chart(fig_price, use_container_width=True)
        
    with tab2:
        # 计算资金流
        def calculate_cumulative_flow(df):
            """计算累计资金净流入序列"""
            df = df.copy()
            # 简单的流向计算：根据'性质'或价格变化
            if '性质' not in df.columns:
                # 简单回退策略：收盘>开盘 = 流入
                df['net_flow'] = df.apply(lambda x: x['成交额(元)'] if x['收盘'] >= x['开盘'] else -x['成交额(元)'], axis=1)
                # 更精细的策略是看 tick data，但这里只有 minute data
                # 如果有 '性质' 列 (某些源提供)，则更准
            else:
                # 如果包含 '买盘'/'卖盘'
                def get_flow(row):
                    amt = row['成交额(元)']
                    t = str(row['性质'])
                    if '买' in t: return amt
                    if '卖' in t: return -amt
                    return 0
                df['net_flow'] = df.apply(get_flow, axis=1)
            
            # 累计求和
            df['cumulative_flow'] = df['net_flow'].cumsum()
            return df

        # 计算两只股票的资金流
        df_a_flow = calculate_cumulative_flow(df_a)
        df_b_flow = calculate_cumulative_flow(df_b)
        
        # 绘制双轴图表
        from plotly.subplots import make_subplots
        fig_flow = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Trace A (Left Y)
        fig_flow.add_trace(
            go.Scatter(x=df_a_flow['时间'], y=df_a_flow['cumulative_flow'], 
                      name=f"{name_a} 资金流", line=dict(color='#ff4d4f')),
            secondary_y=False
        )
        
        # Trace B (Right Y) - 使用不同刻度因为量级可能不同
        fig_flow.add_trace(
            go.Scatter(x=df_b_flow['时间'], y=df_b_flow['cumulative_flow'], 
                      name=f"{name_b} 资金流", line=dict(color='#1890ff', dash='dot')),
            secondary_y=True
        )
        
        fig_flow.update_layout(
            title="累计资金净流入对比 (双轴)", 
            hovermode="x unified",
            template="plotly_white",
            legend=dict(orientation="h", y=1.1)
        )
        
        # Set axis titles
        fig_flow.update_yaxes(title_text=f"{name_a} (元)", secondary_y=False, title_font=dict(color="#ff4d4f"))
        fig_flow.update_yaxes(title_text=f"{name_b} (元)", secondary_y=True, title_font=dict(color="#1890ff"))
        
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
