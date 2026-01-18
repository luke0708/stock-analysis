"""
全局样式与主题定义 - 浅色主题版本
"""
import streamlit as st

def apply_global_styles():
    """注入全局 CSS 样式 - 优化为清晰易读的浅色主题"""
    
    # 使用更清晰的浅色配色方案
    css = """
    <style>
    /* 覆盖 Streamlit 默认主题为浅色 */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* 侧边栏样式 */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
    }
    section[data-testid="stSidebar"] .stMarkdown {
        color: #333333;
    }
    
    /* 主内容区 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        background-color: #f8f9fa;
    }
    
    /* 标题样式 */
    h1, h2, h3 {
        color: #1a1a2e !important;
        font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
        font-weight: 600;
    }
    
    /* 正文颜色 */
    p, span, div, label {
        color: #333333;
    }
    
    /* 卡片容器 - 白色背景 */
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    /* 涨跌幅颜色 - 中国市场红涨绿跌 */
    .trend-up { color: #e53935 !important; font-weight: bold; }
    .trend-down { color: #43a047 !important; font-weight: bold; }
    
    /* 数据表格 */
    [data-testid="stDataFrame"] {
        font-family: 'SF Mono', 'Menlo', monospace;
        font-size: 0.9rem;
    }
    
    /* 分割线 */
    hr {
        margin: 1.5rem 0;
        border-color: #e0e0e0;
    }
    
    /* 按钮样式 */
    .stButton>button {
        border-radius: 6px;
        font-weight: 500;
        background-color: #1976d2;
        color: white;
    }
    .stButton>button:hover {
        background-color: #1565c0;
    }
    
    /* 标签页样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        color: #333333;
        background-color: transparent;
    }
    
    /* Expander 样式 */
    .streamlit-expanderHeader {
        background-color: #ffffff;
        border-radius: 6px;
    }
    
    /* 输入框样式 */
    .stTextInput input, .stSelectbox select {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        color: #333333;
    }

    /* 板块资金流向榜单 */
    .flow-panel {
        background: #ffffff;
        border: 1px solid #e6e6e6;
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .flow-row {
        display: grid;
        grid-template-columns: 28px 1fr 160px 72px;
        align-items: center;
        gap: 10px;
        padding: 6px 0;
    }
    .flow-rank {
        width: 24px;
        height: 24px;
        border-radius: 999px;
        background: #f0f2f5;
        color: #444444;
        font-size: 12px;
        text-align: center;
        line-height: 24px;
        font-weight: 600;
    }
    .flow-name {
        font-weight: 600;
        color: #1a1a2e;
    }
    .flow-bar {
        height: 8px;
        background: #f3f4f6;
        border-radius: 999px;
        overflow: hidden;
    }
    .flow-bar span {
        display: block;
        height: 100%;
        border-radius: 999px;
    }
    .flow-pct {
        text-align: right;
        font-weight: 600;
        font-family: 'SF Mono', 'Menlo', monospace;
    }
    .flow-meta {
        margin-left: 38px;
        color: #6b7280;
        font-size: 12px;
        padding-bottom: 4px;
    }

    /* 指数看板 */
    .index-panel {
        background: linear-gradient(135deg, #ffffff 0%, #f6f7fb 100%);
        border: 1px solid #e6e6e6;
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
    }
    .index-title {
        font-size: 14px;
        font-weight: 600;
        color: #4b5563;
        margin-bottom: 6px;
    }
    .index-price {
        font-size: 28px;
        font-weight: 700;
        color: #111827;
        font-family: 'SF Mono', 'Menlo', monospace;
        line-height: 1.2;
    }
    .index-change {
        font-size: 13px;
        font-weight: 600;
        margin-top: 4px;
    }
    .index-range {
        height: 8px;
        background: #e5e7eb;
        border-radius: 999px;
        overflow: hidden;
        margin: 10px 0 8px;
    }
    .index-range span {
        display: block;
        height: 100%;
        border-radius: 999px;
    }
    .index-meta {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px 12px;
        font-size: 12px;
        color: #6b7280;
    }
    .index-meta b {
        color: #374151;
        font-weight: 600;
    }
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)

def metric_card(label, value, delta=None, color=None):
    """自定义 HTML 指标卡片 - 浅色主题版"""
    delta_html = ""
    if delta:
        try:
            delta_val = float(str(delta).replace('%', '').replace('+', ''))
            delta_cls = "trend-up" if delta_val > 0 else "trend-down" if delta_val < 0 else ""
            delta_html = f'<span class="{delta_cls}" style="font-size: 0.9rem;">{delta}</span>'
        except:
            delta_html = f'<span style="font-size: 0.9rem; color: #666;">{delta}</span>'
    
    # 根据颜色参数设置数值颜色
    value_color = "#1a1a2e"  # 默认深色
    if color == "up": value_color = "#e53935"  # 红色上涨
    elif color == "down": value_color = "#43a047"  # 绿色下跌
    
    html = f"""
    <div class="metric-card">
        <div style="color: #666666; font-size: 0.85rem; margin-bottom: 6px;">{label}</div>
        <div style="font-size: 1.8rem; font-weight: 700; font-family: 'SF Mono', 'Menlo', monospace; color: {value_color};">
            {value}
        </div>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
