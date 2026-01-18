"""
市场热点页面模块
"""
import streamlit as st
import pandas as pd
import akshare as ak
import time
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

@st.cache_data(ttl=3600)
def get_cached_concept_list():
    return ak.stock_board_concept_name_em()

@st.cache_data(ttl=3600)
def get_cached_industry_list():
    return ak.stock_board_industry_name_em()

@st.cache_data(ttl=600)
def get_cached_concept_cons(symbol: str):
    return MarketHotspotAnalyzer.get_concept_constituents(symbol)

@st.cache_data(ttl=600)
def get_cached_industry_cons(symbol: str):
    return MarketHotspotAnalyzer.get_industry_constituents(symbol)

@st.cache_data(ttl=300)
def get_cached_lhb_stats(lhb_df):
    lhb_analyzer = DragonTigerAnalyzer()
    return lhb_analyzer.get_lhb_statistics(lhb_df)

def show_market_page():
    st.header("🔥 市场热点 & 资讯")
    st.caption("实时板块热点、龙虎榜、重大新闻 | 数据缓存5-10分钟")
    
    if 'market_load_hotspot' not in st.session_state:
        st.session_state.market_load_hotspot = False
    if 'market_load_lhb' not in st.session_state:
        st.session_state.market_load_lhb = False
    if 'market_load_news' not in st.session_state:
        st.session_state.market_load_news = False

    # 顶部工具栏
    col_tools, col_toggle = st.columns([1, 5])
    with col_tools:
        if st.button("🔄 刷新数据"):
            st.cache_data.clear()
            st.session_state.market_load_hotspot = False
            st.session_state.market_load_lhb = False
            st.session_state.market_load_news = False
            st.rerun()
    with col_toggle:
        auto_load = st.toggle(
            "自动加载数据（可能较慢）",
            value=st.session_state.get("market_auto_load", False),
            key="market_auto_load"
        )
    
    # 创建标签页
    tab1, tab2, tab3, tab4 = st.tabs(["📊 板块热点", "💰 龙虎榜", "📰 市场要闻", "🧩 板块分析"])
    
    # ===== Tab 1: 板块热点 =====
    with tab1:
        if not auto_load and not st.session_state.market_load_hotspot:
            if st.button("加载板块热点"):
                st.session_state.market_load_hotspot = True
                st.rerun()
            st.info("点击按钮再加载板块热点与市场情绪，避免页面初始化过慢。")
        else:
            progress = st.progress(0, text="正在加载板块热点...")
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
                    finally:
                        progress.progress(33, text="概念板块完成，加载行业板块...")
            
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
                    finally:
                        progress.progress(66, text="行业板块完成，加载市场情绪...")
            
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
            finally:
                progress.progress(100, text="板块热点加载完成")
                progress.empty()
    
    # ===== Tab 2: 龙虎榜 =====
    with tab2:
        if not auto_load and not st.session_state.market_load_lhb:
            if st.button("加载龙虎榜"):
                st.session_state.market_load_lhb = True
                st.rerun()
            st.info("点击按钮后再拉取龙虎榜数据，减少页面初始化时间。")
        else:
            progress = st.progress(0, text="正在加载龙虎榜...")
            days = st.slider("查看最近N天", 1, 7, 3)
            with st.spinner(f"加载数据..."):
                try:
                    lhb = get_cached_lhb(days=days)
                    if not lhb.empty:
                        progress.progress(70, text="龙虎榜数据完成，计算统计...")
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
                finally:
                    progress.progress(100, text="龙虎榜加载完成")
                    progress.empty()
    
    # ===== Tab 3: 新闻 =====
    with tab3:
        if not auto_load and not st.session_state.market_load_news:
            if st.button("加载市场要闻"):
                st.session_state.market_load_news = True
                st.rerun()
            st.info("点击按钮后再拉取新闻列表，减少页面初始化时间。")
        else:
            progress = st.progress(0, text="正在加载市场要闻...")
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
                finally:
                    progress.progress(100, text="市场要闻加载完成")
                    progress.empty()

    # ===== Tab 4: 板块分析 =====
    with tab4:
        st.subheader("🧩 板块成分股分析")

        if "sector_detail_loaded" not in st.session_state:
            st.session_state.sector_detail_loaded = False

        sector_type = st.radio("板块类型", ["行业板块", "概念板块"], horizontal=True, key="sector_type")
        if sector_type == "行业板块":
            board_df = get_cached_industry_list()
        else:
            board_df = get_cached_concept_list()

        if board_df.empty:
            st.info("暂无板块列表数据")
            return

        name_col = None
        for col in ["板块名称", "板块", "名称"]:
            if col in board_df.columns:
                name_col = col
                break

        if name_col is None:
            st.warning("板块列表字段异常，暂无法展示")
            return

        board_names = board_df[name_col].dropna().tolist()
        selected_board = st.selectbox("选择板块", board_names, key="sector_board")

        if st.session_state.get("sector_last") != (sector_type, selected_board):
            st.session_state.sector_detail_loaded = False
            st.session_state.sector_last = (sector_type, selected_board)

        if st.button("加载成分股"):
            st.session_state.sector_detail_loaded = True

        if st.session_state.sector_detail_loaded:
            start_ts = time.perf_counter()
            with st.spinner("加载成分股..."):
                cons_df = pd.DataFrame()
                error_msg = None
                try:
                    if sector_type == "行业板块":
                        cons_df = get_cached_industry_cons(selected_board)
                    else:
                        cons_df = get_cached_concept_cons(selected_board)
                except Exception as exc:
                    error_msg = str(exc)
            elapsed = time.perf_counter() - start_ts

            if error_msg:
                st.error(f"成分股拉取失败: {error_msg}")
                st.caption(f"耗时: {elapsed:.2f}s")
                return

            if cons_df.empty:
                st.warning("暂无成分股数据，可能为接口暂不可用或数据源限制。")
                st.caption(f"耗时: {elapsed:.2f}s")
                return

            display_cols = [c for c in ["代码", "名称", "最新价", "涨跌幅", "成交量", "成交额"] if c in cons_df.columns]
            if not display_cols:
                display_cols = cons_df.columns.tolist()

            st.dataframe(cons_df[display_cols].head(50), use_container_width=True, height=520)
            st.caption(f"成分股拉取耗时: {elapsed:.2f}s")
