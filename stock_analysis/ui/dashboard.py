"""
市场概览仪表盘 (Dashboard)
"""
import streamlit as st
import pandas as pd
import akshare as ak
from datetime import datetime
import plotly.express as px

from stock_analysis.visualization.styling import metric_card
from stock_analysis.analysis.market_hotspot import MarketHotspotAnalyzer
from stock_analysis.core.storage import StorageManager
from stock_analysis.data.news_provider import StockNewsProvider
from stock_analysis.data.stock_list import get_stock_provider

@st.cache_data(ttl=60)
def get_market_indices():
    """获取主要指数实时行情 (一次性批量获取)"""
    target_indices = ["上证指数", "深证成指", "创业板指"]
    results = []
    
    try:
        # 使用新浪源批量获取，速度通常快于逐个请求
        # stock_zh_index_spot_sina 获取的是所有指数的实时列表
        df = ak.stock_zh_index_spot_sina()
        
        for name in target_indices:
            row = df[df['名称'] == name]
            if not row.empty:
                r = row.iloc[0]
                results.append({
                    "name": name,
                    "price": r['最新价'],
                    "change": r['涨跌额'],
                    "pct": r['涨跌幅']
                })
            else:
                results.append({"name": name, "price": "--", "change": 0, "pct": 0})
                
    except Exception as e:
        print(f"Index batch fetch error: {e}")
        for name in target_indices:
             results.append({"name": name, "price": "--", "change": 0, "pct": 0})
            
    return results

def show_dashboard():
    st.markdown("## 📊 市场全局概览")
    st.caption(f"数据更新时间: {datetime.now().strftime('%H:%M:%S')}")
    
    # 1. 顶部指数行情
    indices = get_market_indices()
    cols = st.columns(len(indices))
    for i, idx in enumerate(indices):
        with cols[i]:
            color = "up" if idx['pct'] > 0 else "down" if idx['pct'] < 0 else "gray"
            metric_card(
                label=idx['name'], 
                value=f"{idx['price']}", 
                delta=f"{idx['pct']:+.2f}%",
                color=color
            )
            
    st.markdown("---")
    
    # 2. 核心布局 (2:1)
    col_main, col_side = st.columns([2, 1])
    
    with col_main:
        # 热门行业
        st.subheader("🔥 行业板块资金流向 TOP 10")
        hot_inds = MarketHotspotAnalyzer.get_hot_industries(top_n=10)
        
        if not hot_inds.empty:
            # 简单的条形图
            fig = px.bar(
                hot_inds, 
                x='涨跌幅', 
                y='板块名称', 
                orientation='h',
                color='涨跌幅',
                color_continuous_scale=['#52c41a', '#181818', '#ff4d4f'],
                text='领涨股票'
            )
            fig.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无板块数据")
            
        # 市场新闻
        st.subheader("📰 7x24小时 财经要闻")
        df_news = StockNewsProvider.get_market_news(limit=5)
        if not df_news.empty:
            for _, row in df_news.iterrows():
                # AkShare returns columns like '发布时间', '新闻标题', '新闻内容'
                time_str = row.get('发布时间', '')
                try:
                    # Try simplify time string if it's full datetime
                    if len(str(time_str)) > 10:
                        time_str = str(time_str)[-8:] # Keep HH:MM:SS
                except:
                    pass
                    
                title = row.get('新闻标题', '无标题')
                content = row.get('新闻内容', '无内容')
                
                with st.expander(f"[{time_str}] {title}"):
                    st.write(content)
        else:
            st.info("暂无新闻")

    with col_side:
        # 自选股概况
        st.subheader("📋 我的自选股")
        storage = StorageManager()
        watchlist = storage.get_watchlist()
        
        if watchlist:
            # 转换为 DataFrame
            wl_data = []
            provider = get_stock_provider() # 用于获取最新价
            
            # 这是一个轻量级获取，实际可能需要批量API
            # 以免block
            for item in watchlist:
                wl_data.append(item)
                
            df_wl = pd.DataFrame(wl_data)
            st.dataframe(
                df_wl, 
                column_config={
                    "code": "代码",
                    "name": "名称",
                    "added_at": "加入时间"
                },
                hide_index=True,
                use_container_width=True
            )

            
            if st.button("查看详情分析"):
                # 跳转逻辑 (通过 session state)
                st.session_state._navigate_to = "📈 个股分析"
                st.session_state.stock_code = watchlist[0]['code'] if watchlist else ""
                st.rerun()
        else:
            st.caption("暂无自选股，去添加一些吧！")
            
        # 市场情绪概览
        st.subheader("🌡️ 市场情绪")
        sentiment = MarketHotspotAnalyzer.analyze_market_sentiment()
        if sentiment:
            up = sentiment.get('rising_count', 0)
            down = sentiment.get('falling_count', 0)
            total = up + down
            if total > 0:
                st.progress(up / total, text=f"上涨 {up} 家 / 下跌 {down} 家")
            
            st.write(f"涨停: {sentiment.get('limit_up_count', 0)} 家")
            st.write(f"跌停: {sentiment.get('limit_down_count', 0)} 家")

