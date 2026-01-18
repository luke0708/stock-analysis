"""
市场概览仪表盘 (Dashboard)
"""
import streamlit as st
import pandas as pd
import akshare as ak
from datetime import datetime
from textwrap import dedent

from stock_analysis.analysis.market_hotspot import MarketHotspotAnalyzer
from stock_analysis.data.news_provider import StockNewsProvider
from stock_analysis.core.prefetch import get_prefetched_data

@st.cache_data(ttl=60)
def get_market_indices():
    """获取主要指数实时行情 (一次性批量获取)"""
    target_indices = ["上证指数", "深证成指", "创业板指"]
    results = []
    
    try:
        # 使用新浪源批量获取，速度通常快于逐个请求
        # stock_zh_index_spot_sina 获取的是所有指数的实时列表
        prefetch = get_prefetched_data()
        df = prefetch.get("indices_df")
        if df is None or df.empty:
            df = ak.stock_zh_index_spot_sina()
        
        for name in target_indices:
            row = df[df['名称'] == name]
            if not row.empty:
                r = row.iloc[0]
                results.append({
                    "name": name,
                    "price": r['最新价'],
                    "change": r['涨跌额'],
                    "pct": r['涨跌幅'],
                    "open": r.get('今开', r.get('开盘')),
                    "high": r.get('最高'),
                    "low": r.get('最低'),
                    "amount": r.get('成交额'),
                    "volume": r.get('成交量'),
                    "prev_close": r.get('昨收')
                })
            else:
                results.append({
                    "name": name,
                    "price": "--",
                    "change": 0,
                    "pct": 0,
                    "open": None,
                    "high": None,
                    "low": None,
                    "amount": None,
                    "volume": None,
                    "prev_close": None
                })
                
    except Exception as e:
        print(f"Index batch fetch error: {e}")
        for name in target_indices:
             results.append({
                 "name": name,
                 "price": "--",
                 "change": 0,
                 "pct": 0,
                 "open": None,
                 "high": None,
                 "low": None,
                 "amount": None,
                 "volume": None,
                 "prev_close": None
             })
            
    return results

@st.cache_data(ttl=300)
def get_cached_hot_industries(top_n=10):
    prefetch = get_prefetched_data()
    df = prefetch.get("hot_industries")
    if df is not None and not df.empty:
        return df.head(top_n)
    return MarketHotspotAnalyzer.get_hot_industries(top_n=top_n)

@st.cache_data(ttl=300)
def get_cached_market_news(limit=5):
    prefetch = get_prefetched_data()
    df = prefetch.get("news")
    if df is not None and not df.empty:
        return df.head(limit)
    return StockNewsProvider.get_market_news(limit=limit)

@st.cache_data(ttl=300)
def get_cached_sentiment():
    prefetch = get_prefetched_data()
    data = prefetch.get("sentiment")
    if data:
        return data
    return MarketHotspotAnalyzer.analyze_market_sentiment()

def _format_amount(value):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "--"
    if num >= 1e8:
        return f"{num/1e8:.2f}亿"
    if num >= 1e4:
        return f"{num/1e4:.2f}万"
    return f"{num:.0f}"

def _format_number(value):
    try:
        num = float(value)
        return f"{num:.2f}"
    except (TypeError, ValueError):
        return "--"

def render_index_panels(indices):
    cols = st.columns(3)
    for idx, data in enumerate(indices):
        with cols[idx]:
            price = _format_number(data.get('price'))
            change = data.get('change', 0)
            pct = data.get('pct', 0)
            change_val = _format_number(change)
            pct_val = _format_number(pct)
            is_up = False
            try:
                is_up = float(pct) >= 0
            except (TypeError, ValueError):
                pass
            color = "#e53935" if is_up else "#43a047"

            high = data.get('high')
            low = data.get('low')
            price_raw = data.get('price')
            range_pct = 50
            try:
                high_val = float(high)
                low_val = float(low)
                price_val = float(price_raw)
                if high_val > low_val:
                    range_pct = int((price_val - low_val) / (high_val - low_val) * 100)
                    range_pct = max(0, min(range_pct, 100))
            except (TypeError, ValueError):
                range_pct = 50

            html = f"""
            <div class="index-panel">
                <div class="index-title">{data.get('name', '--')}</div>
                <div class="index-price">{price}</div>
                <div class="index-change" style="color:{color};">
                    {change_val} ({pct_val}%)
                </div>
                <div class="index-range"><span style="width:{range_pct}%; background:{color};"></span></div>
                <div class="index-meta">
                    <div>今开 <b>{_format_number(data.get('open'))}</b></div>
                    <div>昨收 <b>{_format_number(data.get('prev_close'))}</b></div>
                    <div>最高 <b>{_format_number(data.get('high'))}</b></div>
                    <div>最低 <b>{_format_number(data.get('low'))}</b></div>
                    <div>成交额 <b>{_format_amount(data.get('amount'))}</b></div>
                    <div>成交量 <b>{_format_amount(data.get('volume'))}</b></div>
                </div>
            </div>
            """
            st.markdown(dedent(html), unsafe_allow_html=True)

def render_industry_flow_top10(df: pd.DataFrame):
    if df.empty or '板块名称' not in df.columns:
        st.info("暂无板块数据")
        return

    df = df.copy()
    df['涨跌幅'] = pd.to_numeric(df.get('涨跌幅'), errors='coerce').fillna(0)
    max_abs = float(df['涨跌幅'].abs().max()) or 1.0

    rows = []
    for idx, row in df.head(10).iterrows():
        rank = len(rows) + 1
        name = row.get('板块名称', '未知')
        pct = float(row.get('涨跌幅', 0))
        leader = row.get('领涨股票', '—')
        leader_pct = row.get('领涨股票-涨跌幅', '')
        try:
            leader_pct = f"{float(leader_pct):+.2f}%"
        except Exception:
            leader_pct = str(leader_pct) if leader_pct else ""

        bar_width = int(min(abs(pct) / max_abs * 100, 100))
        bar_color = "#e53935" if pct >= 0 else "#43a047"
        pct_color = bar_color

        row_html = f"""
        <div class="flow-row">
            <div class="flow-rank">{rank}</div>
            <div class="flow-name">{name}</div>
            <div class="flow-bar"><span style="width:{bar_width}%; background:{bar_color};"></span></div>
            <div class="flow-pct" style="color:{pct_color};">{pct:+.2f}%</div>
        </div>
        <div class="flow-meta">领涨：{leader} {leader_pct}</div>
        """
        rows.append(dedent(row_html))

    html = f"<div class=\"flow-panel\">{''.join(rows)}</div>"
    st.markdown(dedent(html), unsafe_allow_html=True)

def show_dashboard():
    st.markdown("## 📊 市场全局概览")
    st.caption(f"数据更新时间: {datetime.now().strftime('%H:%M:%S')}")
    
    # 1. 顶部指数行情
    indices = get_market_indices()
    render_index_panels(indices)

    st.markdown("---")

    sentiment = get_cached_sentiment()
    if sentiment:
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.metric("市场情绪", sentiment.get('market_sentiment', 'N/A'))
        with col_s2:
            st.metric("上涨个股", f"{sentiment.get('rising_count', 0)}")
        with col_s3:
            st.metric("下跌个股", f"{sentiment.get('falling_count', 0)}")
        with col_s4:
            st.metric("涨停/跌停", f"{sentiment.get('limit_up_count', 0)}/{sentiment.get('limit_down_count', 0)}")
            
    st.markdown("---")
    
    # 2. 核心布局 (2:1)
    col_main, col_side = st.columns([2, 1])
    
    with col_main:
        # 热门行业
        st.subheader("🔥 行业板块资金流向 TOP 10")
        hot_inds = get_cached_hot_industries(top_n=10)
        render_industry_flow_top10(hot_inds)
            
        # 市场新闻
        st.subheader("📰 7x24小时 财经要闻")
        df_news = get_cached_market_news(limit=6)
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
                
                st.markdown(f"**[{time_str}] {title}**")
                if content:
                    st.caption(content)
        else:
            st.info("暂无新闻")

    with col_side:
        st.subheader("📌 今日提示")
        st.info("行业板块榜单基于最新涨跌幅排序，更多维度请查看“市场要闻”页面。")
