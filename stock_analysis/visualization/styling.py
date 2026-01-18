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
