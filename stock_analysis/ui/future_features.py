"""
未来功能占位页 (Mockups)
展示即将推出的功能预览图，让用户更有实感
"""
import streamlit as st
import pandas as pd
import numpy as np

def show_multi_stock_compare():
    st.header("⚖️ 多股票对比分析 (Coming Soon)")
    st.info("🚧 此功能将在 v1.2 版本上线")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("功能预览")
        st.markdown("""
        - **多维叠加**: 同时查看最多 5 只股票的走势
        - **相对收益**: 以某日为基准查看相对涨跌幅
        - **资金流对比**: 横向比较谁的主力介入更深
        """)
        
    with col2:
        # Mock chart
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100)
        # Generate trend data (cumulative sum) + ensure no infinities
        np.random.seed(42)  # Fixed seed for stability
        data = pd.DataFrame(
            np.random.randn(100, 3).cumsum(0),
            index=dates,
            columns=['贵州茅台 (Mock)', '宁德时代 (Mock)', '招商银行 (Mock)']
        )
        # Add offset to avoid 0/negative if using log scale (though line_chart defaults to linear)
        data = data + 100 
        
        st.line_chart(data)

def show_backtesting():
    st.header("🧪 策略回测实验室 (Coming Soon)")
    st.warning("🚧 此功能将在 v1.3 版本上线")
    
    st.markdown("### 预设策略配置")
    c1, c2, c3 = st.columns(3)
    c1.selectbox("交易策略", ["双均线交叉", "RSI超买超卖", "网格交易"])
    c2.date_input("回测开始", value=pd.to_datetime("2023-01-01"))
    c3.number_input("初始资金", value=100000)
    
    st.button("开始回测 (演示按钮)", disabled=True)
    
    st.markdown("### 预期回测报告")
    st.write("📈 年化收益率: 15.2% | 📉 最大回撤: -8.5% | 🎯 胜率: 58%")
    
def show_global_markets():
    st.header("🌍 全球市场概览 (Coming Soon)")
    st.success("🚧 长期规划功能 (v2.0)")
    
    cols = st.columns(4)
    cols[0].metric("纳斯达克", "14,890.30", "+1.2%")
    cols[1].metric("恒生指数", "16,500.00", "-0.5%")
    cols[2].metric("日经225", "35,000.00", "+0.8%")
    cols[3].metric("标普500", "4,780.00", "+0.9%")
    
    st.caption("*以上数据仅为静态演示*")

def show_ai_analysis():
    st.header("🤖 AI 智能投顾 (Coming Soon)")
    st.info("🚧 正在接入 DeepSeek-V3 模型...")
    
    with st.chat_message("assistant"):
        st.write("我是您的 AI 投资助手。检测到 **贵州茅台 (600519)** 今日主力资金大幅净流入 5 亿元，且突破 20 日均线，建议关注。")
    
    st.chat_input("问我任何关于股票的问题...", disabled=True)
