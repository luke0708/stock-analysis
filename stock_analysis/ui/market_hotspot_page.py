"""
市场热点和资讯页面 - 优化版
展示板块热点、龙虎榜、市场新闻
添加数据缓存，避免重复下载
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
from stock_analysis.analysis.market_hotspot import MarketHotspotAnalyzer
from stock_analysis.analysis.dragon_tiger import DragonTigerAnalyzer
from stock_analysis.data.news_provider import StockNewsProvider

# ===== 缓存函数：避免重复下载 =====
@st.cache_data(ttl=300)  # 缓存5分钟
def get_cached_concepts(top_n=20):
    """获取并缓存概念板块数据"""
    hotspot = MarketHotspotAnalyzer()
    return hotspot.get_hot_concepts(top_n=top_n)

@st.cache_data(ttl=300)
def get_cached_industries(top_n=20):
    """获取并缓存行业板块数据"""
    hotspot = MarketHotspotAnalyzer()
    return hotspot.get_hot_industries(top_n=top_n)

@st.cache_data(ttl=300)
def get_cached_sentiment():
    """获取并缓存市场情绪"""
    hotspot = MarketHotspotAnalyzer()
    return hotspot.analyze_market_sentiment()

@st.cache_data(ttl=600)  # 龙虎榜缓存10分钟
def get_cached_lhb(days=3):
    """获取并缓存龙虎榜数据"""
    lhb_analyzer = DragonTigerAnalyzer()
    return lhb_analyzer.get_recent_lhb(days=days)

@st.cache_data(ttl=600)
def get_cached_market_news(limit=20):
    """获取并缓存市场新闻"""
    news_provider = StockNewsProvider()
    return news_provider.get_market_news(limit=limit)

@st.cache_data(ttl=300)
def get_cached_lhb_stats(lhb_df):
    """获取并缓存龙虎榜统计"""
    lhb_analyzer = DragonTigerAnalyzer()
    return lhb_analyzer.get_lhb_statistics(lhb_df)

def main():
    st.set_page_config(page_title="市场热点", layout="wide", page_icon="🔥")
    
    st.title("🔥 市场热点 & 资讯中心")
    st.caption("实时板块热点、龙虎榜、重大新闻 | 数据缓存5-10分钟")
    
    # 添加刷新按钮
    if st.button("🔄 强制刷新数据"):
        st.cache_data.clear()
        st.rerun()
    
    # 创建3个标签页
    tab1, tab2, tab3 = st.tabs(["📊 板块热点", "💰 龙虎榜", "📰 市场要闻"])
    
    # ===== Tab 1: 板块热点 =====
    with tab1:
        st.header("📊 板块热点分析")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🔥 概念板块排行")
            with st.spinner("加载中..."):
                try:
                    concepts = get_cached_concepts(top_n=20)
                    
                    if not concepts.empty:
                        st.caption(f"✅ 数据已缓存 | 共 {len(concepts)} 个板块")
                        st.dataframe(
                            concepts[['板块名称', '涨跌幅', '领涨股票', '领涨股票-涨跌幅']],
                            height=600,
                            width='stretch'
                        )
                    else:
                        st.info("暂无数据")
                except Exception as e:
                    st.error(f"加载失败: {e}")
        
        with col2:
            st.subheader("📈 行业板块排行")
            with st.spinner("加载中..."):
                try:
                    industries = get_cached_industries(top_n=20)
                    
                    if not industries.empty:
                        st.caption(f"✅ 数据已缓存 | 共 {len(industries)} 个板块")
                        st.dataframe(
                            industries[['板块名称', '涨跌幅', '领涨股票', '领涨股票-涨跌幅']],
                            height=600,
                            width='stretch'
                        )
                except Exception as e:
                    st.error(f"加载失败: {e}")
        
        # 市场情绪
        st.markdown("---")
        st.subheader("📈 市场情绪")
        
        try:
            sentiment = get_cached_sentiment()
            
            col_s1, col_s2, col_s3, col_s4 = st.columns(4)
            
            with col_s1:
                st.metric("市场情绪", sentiment.get('market_sentiment', 'N/A'))
            with col_s2:
                st.metric("上涨个股", f"{sentiment.get('rising_count', 0)}")
            with col_s3:
                st.metric("下跌个股", f"{sentiment.get('falling_count', 0)}")
            with col_s4:
                st.metric("涨停/跌停", f"{sentiment.get('limit_up_count', 0)}/{sentiment.get('limit_down_count', 0)}")
        except:
            st.warning("市场情绪加载失败")
    
    # ===== Tab 2: 龙虎榜 =====
    with tab2:
        st.header("💰 龙虎榜追踪")
        
        days = st.slider("查看最近N天", 1, 7, 3)
        
        with st.spinner(f"加载最近{days}天龙虎榜..."):
            try:
                lhb = get_cached_lhb(days=days)
                
                if not lhb.empty:
                    st.caption(f"✅ 数据已缓存 | 共 {len(lhb)} 条记录")
                    
                    # 统计信息
                    stats = get_cached_lhb_stats(lhb)
                    
                    col_l1, col_l2, col_l3, col_l4 = st.columns(4)
                    
                    with col_l1:
                        st.metric("上榜股票", f"{stats.get('unique_stocks', 0)}只")
                    with col_l2:
                        st.metric("总记录", f"{stats.get('total_records', 0)}条")
                    with col_l3:
                        st.metric("买入总额", f"¥{stats.get('buy_amount_total', 0)/1e8:.2f}亿")
                    with col_l4:
                        net_buy = stats.get('net_buy', 0)
                        st.metric("净买入", f"¥{net_buy/1e8:.2f}亿", delta=f"{'买盘' if net_buy > 0 else '卖盘'}")
                    
                    # 龙虎榜详情
                    st.markdown("---")
                    st.subheader("详细记录")
                    
                    # 筛选列
                    display_cols = []
                    if '代码' in lhb.columns:
                        display_cols.append('代码')
                    if '名称' in lhb.columns:
                        display_cols.append('名称')
                    if '上榜日' in lhb.columns:
                        display_cols.append('上榜日')
                    if '涨跌幅' in lhb.columns:
                        display_cols.append('涨跌幅')
                    if '上榜原因' in lhb.columns:
                        display_cols.append('上榜原因')
                    
                    if display_cols:
                        st.dataframe(
                            lhb[display_cols].head(50),
                            height=500,
                            width='stretch'
                        )
                else:
                    st.info(f"最近{days}天暂无龙虎榜数据")
                    
            except Exception as e:
                st.error(f"加载龙虎榜失败: {e}")
    
    # ===== Tab 3: 市场要闻 =====
    with tab3:
        st.header("📰 市场要闻")
        
        with st.spinner("加载最新新闻..."):
            try:
                news = get_cached_market_news(limit=20)
                
                if not news.empty:
                    st.caption(f"✅ 数据已缓存 | 共 {len(news)} 条新闻")
                    
                    for idx, row in news.iterrows():
                        with st.expander(f"[{row['发布时间']}] {row['新闻标题']}"):
                            if '新闻内容' in row and row['新闻内容']:
                                st.write(row['新闻内容'])
                else:
                    st.info("暂无新闻")
            except Exception as e:
                st.error(f"加载新闻失败: {e}")
    
    # 底部说明
    st.markdown("---")
    st.caption("""
    💡 **性能优化说明**：
    - 板块数据缓存 **5分钟**
    - 龙虎榜数据缓存 **10分钟**  
    - 新闻数据缓存 **10分钟**
    - 调整参数时使用缓存数据，无需重新下载
    - 点击"🔄 强制刷新数据"可清除缓存获取最新数据
    """)

if __name__ == "__main__":
    main()
