"""
市场热点页面模块
"""
import streamlit as st
import pandas as pd
from stock_analysis.analysis.market_hotspot import MarketHotspotAnalyzer
from stock_analysis.analysis.dragon_tiger import DragonTigerAnalyzer
from stock_analysis.data.news_provider import StockNewsProvider

# (导入原有的缓存函数)
@st.cache_data(ttl=300)
def get_cached_concepts(top_n=20):
    hotspot = MarketHotspotAnalyzer()
    return hotspot.get_hot_concepts(top_n=top_n)

@st.cache_data(ttl=300)
def get_cached_industries(top_n=20):
    hotspot = MarketHotspotAnalyzer()
    return hotspot.get_hot_industries(top_n=top_n)

@st.cache_data(ttl=300)
def get_cached_sentiment():
    hotspot = MarketHotspotAnalyzer()
    return hotspot.analyze_market_sentiment()

@st.cache_data(ttl=600)
def get_cached_lhb(days=3):
    lhb_analyzer = DragonTigerAnalyzer()
    return lhb_analyzer.get_recent_lhb(days=days)

@st.cache_data(ttl=600)
def get_cached_market_news(limit=20):
    news_provider = StockNewsProvider()
    return news_provider.get_market_news(limit=limit)

@st.cache_data(ttl=300)
def get_cached_lhb_stats(lhb_df):
    lhb_analyzer = DragonTigerAnalyzer()
    return lhb_analyzer.get_lhb_statistics(lhb_df)

def show_market_page():
    st.header("🔥 市场热点 & 资讯")
    st.caption("实时板块热点、龙虎榜、重大新闻 | 数据缓存5-10分钟")
    
    # 顶部工具栏
    col_tools, _ = st.columns([1, 5])
    with col_tools:
        if st.button("🔄 刷新数据"):
            st.cache_data.clear()
            st.rerun()
    
    # 创建标签页
    tab1, tab2, tab3 = st.tabs(["📊 板块热点", "💰 龙虎榜", "📰 市场要闻"])
    
    # ===== Tab 1: 板块热点 =====
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🔥 概念板块")
            with st.spinner("加载中..."):
                try:
                    concepts = get_cached_concepts(top_n=20)
                    if not concepts.empty:
                        st.dataframe(
                            concepts[['板块名称', '涨跌幅', '领涨股票', '领涨股票-涨跌幅']],
                            height=500,
                            width='stretch'
                        )
                    else:
                        st.info("暂无数据")
                except Exception as e:
                    st.error(f"加载失败: {e}")
        
        with col2:
            st.subheader("📈 行业板块")
            with st.spinner("加载中..."):
                try:
                    industries = get_cached_industries(top_n=20)
                    if not industries.empty:
                        st.dataframe(
                            industries[['板块名称', '涨跌幅', '领涨股票', '领涨股票-涨跌幅']],
                            height=500,
                            width='stretch'
                        )
                except Exception as e:
                    st.error(f"加载失败: {e}")
        
        # 市场情绪
        st.markdown("---")
        st.subheader("📊 市场情绪")
        try:
            sentiment = get_cached_sentiment()
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            with col_s1: st.metric("市场情绪", sentiment.get('market_sentiment', 'N/A'))
            with col_s2: st.metric("上涨个股", f"{sentiment.get('rising_count', 0)}")
            with col_s3: st.metric("下跌个股", f"{sentiment.get('falling_count', 0)}")
            with col_s4: st.metric("涨停/跌停", f"{sentiment.get('limit_up_count', 0)}/{sentiment.get('limit_down_count', 0)}")
        except:
            st.warning("市场情绪加载失败")
    
    # ===== Tab 2: 龙虎榜 =====
    with tab2:
        days = st.slider("查看最近N天", 1, 7, 3)
        with st.spinner(f"加载数据..."):
            try:
                lhb = get_cached_lhb(days=days)
                if not lhb.empty:
                    stats = get_cached_lhb_stats(lhb)
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("上榜股票", f"{stats.get('unique_stocks', 0)}只")
                    c2.metric("记录", f"{stats.get('total_records', 0)}条")
                    c3.metric("买入总额", f"¥{stats.get('buy_amount_total', 0)/1e8:.2f}亿")
                    net = stats.get('net_buy', 0)
                    c4.metric("净买入", f"¥{net/1e8:.2f}亿", delta="买盘" if net>0 else "卖盘")
                    
                    st.markdown("### 详细记录")
                    display_cols = [c for c in ['代码', '名称', '上榜日', '涨跌幅', '上榜原因'] if c in lhb.columns]
                    if display_cols:
                        st.dataframe(lhb[display_cols].head(100), height=500, width='stretch')
                else:
                    st.info("暂无数据")
            except Exception as e:
                st.error(f"加载失败: {e}")
    
    # ===== Tab 3: 新闻 =====
    with tab3:
        with st.spinner("加载新闻..."):
            try:
                news = get_cached_market_news(limit=20)
                if not news.empty:
                    for idx, row in news.iterrows():
                        with st.expander(f"[{row['发布时间']}] {row['新闻标题']}"):
                             st.write(row.get('新闻内容', ''))
                else:
                    st.info("暂无新闻")
            except Exception as e:
                st.error(f"失败: {e}")
