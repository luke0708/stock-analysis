"""
个股分析页面模块
"""
import logging
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional
import os
import json
import numpy as np

# 导入分析组件
from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.data.providers.tushare_provider import TushareProvider
from stock_analysis.data.cleaner import DataCleaner, get_quality_summary
from stock_analysis.analysis.flows import FlowAnalyzer
from stock_analysis.analysis.timeseries import TimeSeriesAnalyzer
from stock_analysis.analysis.indicators import IndicatorCalculator
from stock_analysis.analysis.anomaly import AnomalyDetector
from stock_analysis.analysis.order_strength import OrderStrengthAnalyzer
from stock_analysis.analysis.tick_cleaner import TickDataCleaner
from stock_analysis.analysis.tick_flow import TickFlowAnalyzer
from stock_analysis.analysis.tick_aggregator import TickAggregator
from stock_analysis.analysis.tick_anomaly import TickAnomalyDetector
from stock_analysis.analysis.ai_client import get_deepseek_key, call_deepseek
from stock_analysis.visualization.charts import ChartGenerator
from stock_analysis.core.help_text import get_indicator_help, get_all_help_topics
from stock_analysis.core.cache_manager import CacheManager, DataImporter
from stock_analysis.core.config import settings
from stock_analysis.core.storage import StorageManager
from stock_analysis.data.stock_list import get_stock_provider

logger = logging.getLogger(__name__)

def show_analysis_page():
    st.header("📈 个股资金流向分析")
    
    # 初始化 Session State
    if 'stock_code' not in st.session_state:
        st.session_state.stock_code = "300661"
    
    # 侧边栏辅助功能
    with st.sidebar:
        st.subheader("🔍 股票搜索")
        stock_provider = get_stock_provider()
        search_query = st.text_input("搜索 (代码/名称/拼音)", placeholder="如: 300661 或 maotai")
        if search_query:
            results = stock_provider.search(search_query)
            if not results.empty:
                st.dataframe(results[['代码', '名称']], hide_index=True)
                # 快捷选择
                selected_code = st.selectbox("选择股票", results['代码'] + " | " + results['名称'])
                if selected_code:
                    code = selected_code.split(" | ")[0]
                    if st.button("分析此股票"):
                        st.session_state.stock_code = code
                        st.rerun()
            else:
                st.caption("未找到匹配股票")
    
    # 主界面输入区
    col_input1, col_input2, col_input3 = st.columns([2, 2, 3])
    
    with col_input1:
        stock_code = st.text_input("股票代码", value=st.session_state.stock_code, key="_input_code", help="输入6位股票代码")
        # 更新 session state
        st.session_state.stock_code = stock_code
        
    with col_input2:
        analysis_date = st.date_input("分析日期", value=datetime.now())
        if (datetime.now().date() - analysis_date).days > 7:
            st.caption("提示：分钟级数据源通常仅保留最近约 7 个交易日，较早日期可能自动回退或无数据。")
        
    with col_input3:
        # 添加/移除自选股按钮
        storage = StorageManager()
        watchlist_codes = storage.get_watchlist_codes()
        is_in_watchlist = stock_code in watchlist_codes
        
        st.write("") # Spacer
        st.write("") # Spacer
        if is_in_watchlist:
            if st.button("💔 移出自选"):
                storage.remove_from_watchlist(stock_code)
                st.success("已移除")
                st.rerun()
        else:
            if st.button("❤️ 加入自选"):
                # 获取名称 (如果能获取到)
                name = stock_code # 默认
                try:
                    res = stock_provider.search(stock_code, limit=1)
                    if not res.empty:
                        name = res.iloc[0]['名称']
                except:
                    pass
                storage.add_to_watchlist(stock_code, name)
                st.success(f"已加入自选: {name}")
                st.rerun()

    # 数据源选择
    with st.expander("⚙️ 高级设置 (数据源/导入)", expanded=False):
        import_option = st.radio("数据模式", ["实时获取", "导入CSV文件"], horizontal=True)
        
        if import_option == "导入CSV文件":
             uploaded_file = st.file_uploader("上传CSV文件", type=['csv'])
             if uploaded_file and st.button("导入并分析"):
                importer = DataImporter()
                df, success, msg = importer.import_from_csv(uploaded_file)
                if success:
                    st.success(msg)
                    process_imported_data(df, analysis_date)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            # 修改：AkShare 设为默认推荐
            provider_choice = st.radio("API源", ["AkShare (推荐)", "Tushare Pro"], horizontal=True)
            tushare_token = ""
            if "Tushare" in provider_choice:
                tushare_token = st.text_input("Tushare Token", value=os.getenv("TUSHARE_TOKEN", ""), type="password")

    # 开始分析按钮
    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        date_str = analysis_date.strftime("%Y%m%d")
        
        if import_option == "实时获取":
            with st.spinner(f"正在获取 {stock_code} 在 {date_str} 的数据..."):
                df, actual_source, raw_df = fetch_data(stock_code, date_str, provider_choice, tushare_token)
                
                if df.empty:
                    requested_date = df.attrs.get('requested_date')
                    fallback_date = df.attrs.get('fallback_date')
                    if requested_date and fallback_date:
                        st.error(f"所选日期 {requested_date} 无分钟数据，回退到 {fallback_date} 仍未获取到。")
                        st.caption("建议：更换为近期交易日或切换数据源。")
                    elif requested_date:
                        st.error(f"所选日期 {requested_date} 暂无分钟数据，请更换日期或稍后重试。")
                    else:
                        st.error("未能获取数据，请检查股票代码或稍后重试。")
                else:
                    requested_date = df.attrs.get('requested_date')
                    actual_date = df.attrs.get('actual_date')
                    if requested_date and actual_date and requested_date != actual_date:
                        st.info(f"所选日期无交易数据，已自动切换到最近交易日 {actual_date}。")
                    process_and_display(df, stock_code, analysis_date, actual_source, raw_df)
    
    # 显示已存在的结果 (如果有)
    if 'df' in st.session_state and st.session_state.df is not None:
        display_results(st.session_state.get('last_stock_code', stock_code), analysis_date)

# --- 辅助函数 ---

def _convert_tick_to_minute(df_tick: pd.DataFrame, analysis_date) -> tuple[pd.DataFrame, list]:
    analysis_day = analysis_date.date() if hasattr(analysis_date, "date") else analysis_date
    if analysis_day is None:
        analysis_day = datetime.now().date()

    cleaner = TickDataCleaner()
    clean_df, quality_flags, _, _ = cleaner.clean(df_tick, analysis_day)
    if clean_df.empty:
        return pd.DataFrame(), ["tick_clean_empty"]

    tick_df = clean_df.copy()
    tick_df["分钟"] = tick_df["时间"].dt.floor("min")
    grouped = tick_df.groupby("分钟", sort=True)

    minute_df = grouped["成交价格"].agg(["first", "last", "max", "min"]).rename(
        columns={"first": "开盘", "last": "收盘", "max": "最高", "min": "最低"}
    )
    minute_df["成交量"] = grouped["成交量"].sum()
    minute_df["成交额"] = grouped["成交额(元)"].sum()
    minute_df = minute_df.reset_index().rename(columns={"分钟": "时间"})
    minute_df["成交额(元)"] = minute_df["成交额"]

    minute_df.attrs["raw_tick"] = df_tick
    minute_df.attrs["source_granularity"] = "tick_import"
    minute_df.attrs["imported_tick"] = True
    minute_df.attrs["analysis_date"] = analysis_day
    return minute_df, quality_flags


def process_imported_data(df, analysis_date=None):
    data_type = df.attrs.get("data_type", "minute") if df is not None else "minute"
    if data_type == "tick":
        minute_df, tick_flags = _convert_tick_to_minute(df, analysis_date)
        if minute_df.empty:
            st.error("Tick 数据清洗后为空，无法生成分钟数据。")
            return

        cleaner = DataCleaner()
        df_clean, quality_report = cleaner.clean(minute_df)
        indicator_calc = IndicatorCalculator()
        df_with_indicators = indicator_calc.calculate_all(df_clean)

        st.session_state.df = df_with_indicators
        st.session_state.actual_source = "CSV导入(Tick)"
        st.session_state.raw_df = minute_df.attrs.get("raw_tick", df)
        st.session_state.tick_context = _build_tick_context(
            st.session_state.raw_df, analysis_date, allow_imported=True
        )
        st.session_state.quality_report = quality_report
        st.session_state.all_analysis = perform_all_analysis(df_with_indicators)
        st.session_state.last_stock_code = "导入数据"
        if tick_flags:
            st.session_state.tick_import_flags = tick_flags
        return

    cleaner = DataCleaner()
    df_clean, quality_report = cleaner.clean(df)
    indicator_calc = IndicatorCalculator()
    df_with_indicators = indicator_calc.calculate_all(df_clean)

    st.session_state.df = df_with_indicators
    st.session_state.actual_source = "CSV导入"
    st.session_state.raw_df = None
    st.session_state.tick_context = None
    st.session_state.quality_report = quality_report
    st.session_state.all_analysis = perform_all_analysis(df_with_indicators)
    st.session_state.last_stock_code = "导入数据"

def process_and_display(df, stock_code, analysis_date, actual_source, raw_df=None):
    cleaner = DataCleaner()
    df_clean, quality_report = cleaner.clean(df)
    indicator_calc = IndicatorCalculator()
    df_with_indicators = indicator_calc.calculate_all(df_clean)
    
    st.session_state.df = df_with_indicators
    st.session_state.actual_source = actual_source
    st.session_state.raw_df = raw_df
    st.session_state.tick_context = _build_tick_context(raw_df, analysis_date)
    st.session_state.quality_report = quality_report
    st.session_state.all_analysis = perform_all_analysis(df_with_indicators)
    st.session_state.last_stock_code = stock_code

def fetch_data(stock_code, date_str, provider_choice, tushare_token):
    actual_source = None
    df = pd.DataFrame()
    raw_df = None
    
    # 根据选择的逻辑
    use_tushare = "Tushare" in provider_choice
    
    if use_tushare:
        if not tushare_token:
            st.error("❌ 请先输入 Tushare Token")
            return df, actual_source, raw_df
        try:
            os.environ["TUSHARE_TOKEN"] = tushare_token
            settings.TUSHARE_TOKEN = tushare_token
            provider = TushareProvider()
            df = provider.get_tick_data(stock_code, date_str=date_str)
            if not df.empty:
                actual_source = "Tushare Pro"
            else:
                raise ValueError("Empty data")
        except:
            st.warning("切换到 AkShare...")
            provider = AkShareProvider()
            df = provider.get_tick_data(stock_code, date_str=date_str)
            actual_source = "AkShare (Fallback)"
    else:
        # AkShare 优先
        provider = AkShareProvider()
        df = provider.get_tick_data(stock_code, date_str=date_str)
        actual_source = "AkShare"
    
    raw_df = df.attrs.get('raw_tick')
    return df, actual_source, raw_df

def perform_all_analysis(df):
    results = {}
    results['flows'] = FlowAnalyzer().calculate_flows(df)
    results['timeseries'] = TimeSeriesAnalyzer().analyze(df)
    results['indicators'] = IndicatorCalculator().get_summary(df)
    results['anomalies'] = AnomalyDetector().detect_all(df)
    
    sa = OrderStrengthAnalyzer()
    results['strength'] = sa.analyze(df)
    results['strength_timeseries'] = sa.get_minutely_strength(df)
    return results

def display_results(stock_code, analysis_date):
    df = st.session_state.df
    source = st.session_state.actual_source
    quality = st.session_state.quality_report
    analysis = st.session_state.all_analysis
    tick_context = st.session_state.get('tick_context')
    show_auction = False

    def _get_stock_name(code):
        if 'stock_name_cache' not in st.session_state:
            st.session_state.stock_name_cache = {}
        cache = st.session_state.stock_name_cache
        if code in cache:
            return cache[code]
        provider = get_stock_provider()
        name = code
        try:
            res = provider.search(code, limit=1)
            if not res.empty:
                name = res.iloc[0]['名称']
        except Exception:
            pass
        cache[code] = name
        return name
    
    # 顶部状态栏
    current_time = datetime.now().strftime("%H:%M:%S")
    actual_date = df.attrs.get('actual_date') or analysis_date.strftime("%Y%m%d")
    requested_date = df.attrs.get('requested_date')
    actual_date_fmt = f"{actual_date[:4]}-{actual_date[4:6]}-{actual_date[6:]}"
    name = _get_stock_name(stock_code)

    date_note = f"分析日期: {actual_date_fmt}"
    if requested_date and requested_date != actual_date:
        requested_fmt = f"{requested_date[:4]}-{requested_date[4:6]}-{requested_date[6:]}"
        date_note = f"分析日期: {actual_date_fmt} (所选: {requested_fmt})"

    source_note = source
    if tick_context:
        source_note = f"{source} + Tick"
    st.caption(
        f"最后更新: {current_time} | {date_note} | 分析对象: {stock_code} {name} | 数据源: {source_note} | 质量: {quality['quality_score']:.0f}/100"
    )

    if tick_context and tick_context.get("auction_df") is not None:
        if not tick_context["auction_df"].empty:
            show_auction = st.toggle(
                "显示集合竞价",
                value=False,
                help="默认不纳入主图表，开启后会在资金流图中显示集合竞价标记。",
            )

    tick_window_1m = tick_context.get("window_1m") if tick_context else None
    tick_window_5m = tick_context.get("window_5m") if tick_context else None
    tick_ofi_display = tick_context.get("ofi_display_df") if tick_context else None
    tick_clean_df = tick_context.get("clean_df") if tick_context else None
    combined_df = None

    if show_auction and tick_context:
        auction_processed = tick_context.get("auction_processed_df")
        if (
            auction_processed is not None
            and not auction_processed.empty
            and tick_clean_df is not None
            and not tick_clean_df.empty
        ):
            combined_df = pd.concat([tick_clean_df, auction_processed], ignore_index=True)
            combined_df = combined_df.sort_values("时间")
            windows = TickAggregator().aggregate(combined_df, windows=[1, 5, 10])
            tick_window_1m = windows.get(1, tick_window_1m)
            tick_window_5m = windows.get(5, tick_window_5m)

            if tick_window_1m is not None and not tick_window_1m.empty:
                tick_window_1m["cum_net_inflow"] = tick_window_1m["net_inflow"].cumsum()
                tick_window_1m["cum_net_inflow_ema"] = tick_window_1m["cum_net_inflow"].ewm(
                    alpha=0.2, adjust=False
                ).mean()

            if tick_window_1m is not None and not tick_window_1m.empty and "ofi" in tick_window_1m.columns:
                tick_ofi_display = tick_window_1m[["时间", "ofi"]].copy()
                tick_ofi_display["ofi"] = tick_ofi_display["ofi"].ewm(
                    alpha=0.3, adjust=False
                ).mean()
    
    # ===== 第一行：核心指标卡片 (恢复5列布局) =====
    ts_data = analysis.get('timeseries', {})
    ind_data = analysis.get('indicators', {})
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        change_pct = ts_data.get('price_change_pct', 0)
        st.metric("涨跌幅", f"{change_pct:+.2f}%", delta=f"{ts_data.get('price_change', 0):+.2f}")
    
    with col2:
        st.metric("成交额", f"¥{ts_data.get('turnover_total', 0)/1e8:.2f}亿")
    
    with col3:
        st.metric("振幅", f"{ts_data.get('amplitude', 0):.2f}%")
    
    with col4:
        vwap = ind_data.get('vwap', 0)
        close = ts_data.get('close_price', 0)
        vs_vwap = ((close - vwap) / vwap * 100) if vwap > 0 else 0
        st.metric("价格 vs VWAP", f"{vs_vwap:+.2f}%", delta="高于均价" if vs_vwap > 0 else "低于均价")
    
    with col5:
        large_orders = analysis.get('anomalies', {}).get('summary', {}).get('large_order_count', 0)
        if tick_context and tick_context.get("flow_summary"):
            large_orders = tick_context["flow_summary"].get("large_order_count", large_orders)
        st.metric("大单数量", f"{large_orders} 笔")
    
    st.markdown("---")

    # ===== 第二行：核心走势 =====
    cg = ChartGenerator()
    st.subheader("📈 分时走势 + 成交量")
    st.plotly_chart(cg.create_candlestick_chart(df, stock_code), use_container_width=True)

    flows = analysis.get('flows', {})
    if tick_context and tick_context.get("flow_summary"):
        flows = tick_context["flow_summary"]
    total_net = flows.get('large_order_net_inflow', 0) + flows.get('retail_net_inflow', 0)
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.metric("主力净流入", f"¥{flows.get('large_order_net_inflow', 0)/1e8:.2f}亿")
    with col_f2:
        st.metric("散户净流入", f"¥{flows.get('retail_net_inflow', 0)/1e8:.2f}亿")
    with col_f3:
        st.metric("总净流入", f"¥{total_net/1e8:.2f}亿")

    st.markdown("---")

    # ===== 资金流向全景 =====
    st.subheader("💰 资金流向全景监控")
    df_chart = df.copy()

    if (
        tick_window_1m is not None
        and not tick_window_1m.empty
        and {"时间", "net_inflow", "turnover"}.issubset(tick_window_1m.columns)
    ):
        time_col = tick_window_1m["时间"]
        if isinstance(time_col, pd.DataFrame):
            time_col = time_col.iloc[:, 0]
        net_inflow_col = tick_window_1m["net_inflow"]
        if isinstance(net_inflow_col, pd.DataFrame):
            net_inflow_col = net_inflow_col.iloc[:, 0]
        turnover_col = tick_window_1m["turnover"]
        if isinstance(turnover_col, pd.DataFrame):
            turnover_col = turnover_col.iloc[:, 0]
        df_chart = pd.DataFrame(
            {
                "时间": time_col.values,
                "净流入额": net_inflow_col.values,
                "成交额(元)": turnover_col.values,
            }
        )
        df_chart["累计净流入"] = df_chart["净流入额"].cumsum()
        if "cum_net_inflow_ema" in tick_window_1m.columns:
            ema_col = tick_window_1m["cum_net_inflow_ema"]
            if isinstance(ema_col, pd.DataFrame):
                ema_col = ema_col.iloc[:, 0]
            df_chart["累计净流入_ema"] = ema_col.values
    else:
        def calc_net(row):
            amt = row.get('成交额(元)', row.get('amount', 0))
            nature = str(row.get('性质', ''))
            if '买' in nature:
                return amt
            elif '卖' in nature:
                return -amt
            return 0

        df_chart['净流入额'] = df_chart.apply(calc_net, axis=1)
        df_chart['累计净流入'] = df_chart['净流入额'].cumsum()

    if show_auction and tick_context and tick_context.get("auction_time"):
        marker_value = 0.0
        if not df_chart.empty and "累计净流入" in df_chart.columns:
            marker_value = float(df_chart["累计净流入"].iloc[0])
        df_chart.attrs["auction_marker"] = {
            "time": tick_context.get("auction_time"),
            "value": marker_value,
            "label": "集合竞价",
        }

    col_a1, col_a2 = st.columns(2)

    with col_a1:
        st.markdown("**📈 全天累计资金流曲线**")
        try:
            cum_flow_fig = cg.create_cumulative_flow_chart(df_chart)
            st.plotly_chart(cum_flow_fig, use_container_width=True)
        except Exception as e:
            st.error(f"累计资金流曲线生成失败: {e}")

    with col_a2:
        st.markdown("**🌡️ 日内分时资金流热力**")
        try:
            heatmap_fig = cg.create_intraday_heatmap(df_chart, resample_minutes=10)
            st.plotly_chart(heatmap_fig, use_container_width=True)
        except Exception as e:
            st.error(f"热力图生成失败: {e}")

    st.markdown("---")

    # ===== 资金流向深度分析 =====
    st.subheader("🔍 资金流向深度分析")
    col_l, col_r = st.columns(2)

    flow_data = analysis.get('flows', {})
    if tick_context and tick_context.get("flow_summary"):
        flow_data = tick_context["flow_summary"]

    flow_source_df = df
    if tick_clean_df is not None:
        flow_source_df = tick_clean_df
    if combined_df is not None and not combined_df.empty:
        flow_source_df = combined_df

    stacked_area_fig = cg.create_stacked_area_flow(flow_source_df, flow_data, resample_minutes=30)

    strength_df = analysis.get('strength_timeseries', pd.DataFrame())
    if (
        tick_window_5m is not None
        and not tick_window_5m.empty
        and {"时间", "buy_amount", "sell_amount"}.issubset(tick_window_5m.columns)
    ):
        strength_df = tick_window_5m[["时间", "buy_amount", "sell_amount"]].rename(
            columns={"buy_amount": "买盘额", "sell_amount": "卖盘额"}
        )
    strength_fig = cg.create_order_strength_chart(strength_df)

    with col_l:
        st.markdown("**💼 主力/散户资金流构成 (30分钟)**")
        st.plotly_chart(stacked_area_fig, use_container_width=True)

        st.info(f"""
        **主力净流入**: ¥{flows.get('large_order_net_inflow', 0):,.0f}  
        **散户净流入**: ¥{flows.get('retail_net_inflow', 0):,.0f}
        """)

    with col_r:
        st.markdown("**⚖️ 买卖盘力度对比**")
        st.plotly_chart(strength_fig, use_container_width=True)

    st.markdown("---")

    # ===== Tick 节奏监控 =====
    if tick_window_5m is not None and not tick_window_5m.empty:
        st.subheader("📊 Tick 节奏监控")
        col_t1, col_t2 = st.columns(2)

        with col_t1:
            st.markdown("**📐 订单流失衡 (OFI)**")
            ofi_source = tick_ofi_display
            if ofi_source is None or ofi_source.empty:
                if "ofi" in tick_window_5m.columns:
                    ofi_source = tick_window_5m[["时间", "ofi"]]
            if ofi_source is not None and not ofi_source.empty:
                ofi_fig = cg.create_ofi_trend_chart(ofi_source)
                st.plotly_chart(ofi_fig, use_container_width=True)
            else:
                st.info("暂无 OFI 数据")

        with col_t2:
            st.markdown("**📌 成交密度与波动**")
            density_df = tick_window_1m if tick_window_1m is not None and not tick_window_1m.empty else tick_window_5m
            if density_df is not None and not density_df.empty:
                density_fig = cg.create_trade_density_chart(density_df)
                st.plotly_chart(density_fig, use_container_width=True)
            else:
                st.info("暂无成交密度数据")

        st.markdown("---")

    # ===== 异动与追踪 =====
    st.subheader("📉 价格异动与大单追踪")
    col_cum, col_orders = st.columns(2)

    with col_cum:
        st.subheader("📉 累计涨跌幅")
        if '累计涨跌幅' in df.columns:
            cum_fig = cg.create_cumulative_change_chart(df)
            st.plotly_chart(cum_fig, use_container_width=True)

    with col_orders:
        st.subheader("🎯 大单追踪")
        anomalies = analysis.get('anomalies', {})
        large_orders_list = anomalies.get('large_orders', [])
        if tick_context and tick_context.get("large_orders_list"):
            large_orders_list = tick_context["large_orders_list"]

        if large_orders_list:
            scatter_fig = cg.create_large_orders_scatter(large_orders_list, df)
            st.plotly_chart(scatter_fig, use_container_width=True)
        else:
            st.info("今日暂无异常大单")

    st.markdown("---")

    # ===== AI 图表解读 =====
    st.subheader("🤖 图表解读 (AI)")
    st.caption("仅解读当前图表，独立于“AI 智能投顾”的对话")

    if "chart_ai_history" not in st.session_state:
        st.session_state.chart_ai_history = []
    if "chart_ai_last" not in st.session_state:
        st.session_state.chart_ai_last = None

    api_key, api_key_name = get_deepseek_key()
    if not api_key:
        st.info("未检测到 DeepSeek API Key，请先在 .env 中配置后使用。")
    else:
        st.caption(f"当前使用环境变量: {api_key_name}")
        stock_name = _get_stock_name(stock_code)
        current_key = f"{stock_code}:{actual_date}"
        focus = st.radio(
            "解读侧重点",
            ["总体结论", "资金流向", "风险提示"],
            horizontal=True,
            help="切换侧重点后，需要点击“生成图表解读”才会更新结果。"
        )
        style = st.radio(
            "解读风格",
            ["简洁", "专业"],
            horizontal=True,
            help="简洁=要点短句；专业=分小标题。"
        )
        with st.expander("📌 传递给模型的数据预览", expanded=False):
            chart_context = _build_chart_context(df, analysis, tick_context)
            st.json(chart_context)

        col_ai1, col_ai2 = st.columns([1, 3])
        with col_ai1:
            gen_chart_btn = st.button("生成图表解读", type="primary")
        with col_ai2:
            st.caption("提示：生成会调用外部API，速度取决于网络。")

        if gen_chart_btn:
            chart_context = _build_chart_context(df, analysis, tick_context)
            system_prompt, user_prompt = _build_chart_prompts(
                chart_context=chart_context,
                focus=focus,
                style=style
            )
            with st.spinner("正在生成图表解读..."):
                try:
                    response = call_deepseek(
                        api_key=api_key,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=0.2,
                        max_tokens=600
                    )
                    entry = {
                        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "key": current_key,
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "actual_date": actual_date,
                        "focus": focus,
                        "style": style,
                        "response": response,
                        "context": chart_context,
                    }
                    st.session_state.chart_ai_history.append(entry)
                    st.session_state.chart_ai_last = entry
                except Exception as exc:
                    st.error(f"请求失败: {exc}")

        if st.session_state.chart_ai_last and st.session_state.chart_ai_last.get("key") == current_key:
            st.markdown("### ✅ 最新图表解读")
            st.caption(
                f"{st.session_state.chart_ai_last['ts']} | "
                f"{st.session_state.chart_ai_last['stock_code']} {st.session_state.chart_ai_last['stock_name']} | "
                f"{st.session_state.chart_ai_last['focus']} | "
                f"{st.session_state.chart_ai_last['style']}"
            )
            st.write(st.session_state.chart_ai_last["response"])
        else:
            st.info("当前股票暂无图表解读，请点击“生成图表解读”。")

        if st.session_state.chart_ai_history:
            show_all = st.toggle("显示全部历史", value=False, help="默认只展示当前股票与日期。")
            history_items = st.session_state.chart_ai_history
            if not show_all:
                history_items = [item for item in history_items if item.get("key") == current_key]
            with st.expander("🗂️ 历史图表解读", expanded=False):
                for item in reversed(history_items[-5:]):
                    st.markdown(
                        f"**{item['ts']} | {item['stock_code']} {item['stock_name']} | "
                        f"{item['focus']} | {item['style']}**"
                    )
                    st.write(item["response"])

    # 保存功能
    st.subheader("💾 保存数据")
    date_str = analysis_date.strftime("%Y%m%d")
    raw_df = st.session_state.get('raw_df')
    export_df = df
    file_suffix = "minute"
    if raw_df is not None and not raw_df.empty:
        use_tick = st.toggle("下载 Tick 数据", value=True, help="仅当日实时获取可用")
        if use_tick:
            export_df = raw_df
            file_suffix = "tick"
    csv = export_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("下载 CSV", csv, f"{stock_code}_{date_str}_{file_suffix}.csv", "text/csv")


def _build_chart_context(df: pd.DataFrame, analysis: dict, tick_context: Optional[dict] = None) -> dict:
    timeseries = analysis.get('timeseries', {})
    flows = analysis.get('flows', {})
    if tick_context and tick_context.get("flow_summary"):
        flows = tick_context["flow_summary"]
    indicators = analysis.get('indicators', {})
    anomalies = analysis.get('anomalies', {})

    df_chart = df.copy()
    if tick_context and tick_context.get("window_1m") is not None:
        window_1m = tick_context["window_1m"]
        if (
            not window_1m.empty
            and {"时间", "net_inflow", "turnover"}.issubset(window_1m.columns)
        ):
            time_col = window_1m["时间"]
            if isinstance(time_col, pd.DataFrame):
                time_col = time_col.iloc[:, 0]
            net_inflow_col = window_1m["net_inflow"]
            if isinstance(net_inflow_col, pd.DataFrame):
                net_inflow_col = net_inflow_col.iloc[:, 0]
            turnover_col = window_1m["turnover"]
            if isinstance(turnover_col, pd.DataFrame):
                turnover_col = turnover_col.iloc[:, 0]
            df_chart = pd.DataFrame(
                {
                    "时间": time_col.values,
                    "净流入额": net_inflow_col.values,
                    "成交额(元)": turnover_col.values,
                }
            )

    if '成交额(元)' not in df_chart.columns:
        if '成交额' in df_chart.columns:
            df_chart['成交额(元)'] = df_chart['成交额']
        elif 'amount' in df_chart.columns:
            df_chart['成交额(元)'] = df_chart['amount']

    def calc_net(row):
        amt = row.get('成交额(元)', 0)
        nature = str(row.get('性质', ''))
        if '买' in nature:
            return amt
        if '卖' in nature:
            return -amt
        return 0

    if not df_chart.empty:
        if '净流入额' not in df_chart.columns:
            df_chart['净流入额'] = df_chart.apply(calc_net, axis=1)
        df_chart['累计净流入'] = df_chart['净流入额'].cumsum()
        cum_flow_last = float(df_chart['累计净流入'].iloc[-1])
    else:
        cum_flow_last = 0.0

    total_net = flows.get('large_order_net_inflow', 0) + flows.get('retail_net_inflow', 0)

    context = {
        "charts": [
            "分时K线+成交量",
            "累计资金流曲线",
            "资金流热力图",
            "主力/散户资金流构成",
            "买卖盘力度对比",
            "累计涨跌幅",
            "大单追踪",
        ],
        "price": {
            "open": timeseries.get("open_price"),
            "close": timeseries.get("close_price"),
            "high": timeseries.get("high_price"),
            "low": timeseries.get("low_price"),
            "change_pct": timeseries.get("price_change_pct"),
            "amplitude": timeseries.get("amplitude"),
        },
        "flow": {
            "large_net": flows.get("large_order_net_inflow"),
            "retail_net": flows.get("retail_net_inflow"),
            "total_net": total_net,
            "large_ratio": flows.get("large_order_ratio"),
            "cum_flow_last": cum_flow_last,
            "quality": flows.get("flow_quality", {}),
        },
        "indicators": {
            "vwap": indicators.get("vwap"),
            "ma5": indicators.get("ma5"),
            "ma10": indicators.get("ma10"),
            "price_vs_vwap": indicators.get("price_vs_vwap"),
        },
        "anomalies": {
            "large_order_count": anomalies.get("summary", {}).get("large_order_count", 0),
            "price_spike_count": anomalies.get("summary", {}).get("price_spike_count", 0),
            "volume_surge_count": anomalies.get("summary", {}).get("volume_surge_count", 0),
        },
    }

    if tick_context and tick_context.get("tick_ai_summary"):
        context["tick_summary"] = tick_context["tick_ai_summary"]

    return context


def _build_tick_context(raw_df: pd.DataFrame, analysis_date, allow_imported: bool = False) -> Optional[dict]:
    if raw_df is None or raw_df.empty:
        return None

    analysis_day = analysis_date.date() if hasattr(analysis_date, "date") else analysis_date
    allow_tick = allow_imported or bool(getattr(raw_df, "attrs", {}).get("imported_tick"))
    if not allow_tick and analysis_day != datetime.now().date():
        return None

    # ===== 诊断快照 1: raw_df 原始状态 =====
    logger.info("=" * 60)
    logger.info("🔍 Tick 诊断快照 - 阶段 1: raw_df 原始状态")
    logger.info(f"raw_df.shape: {raw_df.shape}")
    logger.info(f"raw_df.columns: {list(raw_df.columns)}")
    
    nature_col = raw_df.get("性质")
    if nature_col is not None:
        nature_dist = nature_col.value_counts().to_dict()
        nature_notnull_ratio = nature_col.notna().sum() / len(raw_df) if len(raw_df) > 0 else 0
        logger.info(f"性质_分布: {nature_dist}")
        logger.info(f"性质_非空比例: {nature_notnull_ratio:.2%}")
        logger.info(f"性质_样本前5行: {nature_col.head().tolist()}")
    else:
        logger.warning("❌ raw_df 缺少 '性质' 列")
    
    if "成交额" in raw_df.columns or "成交额(元)" in raw_df.columns:
        amount_col = "成交额(元)" if "成交额(元)" in raw_df.columns else "成交额"
        amount_nonzero = (pd.to_numeric(raw_df[amount_col], errors='coerce') != 0).sum()
        logger.info(f"{amount_col}_非零数量: {amount_nonzero}/{len(raw_df)}")
    logger.info("=" * 60)

    cleaner = TickDataCleaner()
    clean_df, quality_flags, auction_df, inferred_ratio = cleaner.clean(raw_df, analysis_day)
    if clean_df.empty:
        logger.error("❌ clean_df 为空，清洗失败")
        return None
    
    # ===== 诊断快照 2: clean_df 清洗后状态 =====
    logger.info("🔍 Tick 诊断快照 - 阶段 2: clean_df 清洗后状态")
    logger.info(f"clean_df.shape: {clean_df.shape}")
    
    clean_nature_col = clean_df.get("性质")
    if clean_nature_col is not None:
        nature_dist_clean = clean_nature_col.value_counts().to_dict()
        nature_na_count = clean_nature_col.isna().sum()
        logger.info(f"性质_分布: {nature_dist_clean}")
        logger.info(f"性质_NA数量: {nature_na_count}/{len(clean_df)}")
        logger.info(f"性质_样本前5行: {clean_nature_col.head().tolist()}")
    else:
        logger.warning("❌ clean_df 缺少 '性质' 列")
    
    if "成交额(元)" in clean_df.columns:
        amount_nonzero_clean = (clean_df["成交额(元)"] != 0).sum()
        logger.info(f"成交额(元)_非零数量: {amount_nonzero_clean}/{len(clean_df)}")
        logger.info(f"成交额(元)_样本前5行: {clean_df['成交额(元)'].head().tolist()}")
    
    logger.info(f"quality_flags: {quality_flags}")
    logger.info(f"inferred_ratio: {inferred_ratio:.2%}")
    logger.info("=" * 60)

    flow_analyzer = TickFlowAnalyzer()
    flow_result = flow_analyzer.analyze(clean_df)
    processed_df = flow_result.get("processed_df", clean_df)
    quality_flags.extend(flow_result.get("quality_flags", []))
    
    # ===== 诊断快照 3: flow_result 分析后状态 =====
    logger.info("🔍 Tick 诊断快照 - 阶段 3: flow_result 分析后状态")
    
    if "方向" in processed_df.columns:
        direction_dist = processed_df["方向"].value_counts().to_dict()
        logger.info(f"方向_分布: {direction_dist}")
        logger.info(f"方向_样本前10行: {processed_df['方向'].head(10).tolist()}")
    else:
        logger.warning("❌ processed_df 缺少 '方向' 列")
    
    summary = flow_result.get("summary", {})
    logger.info(f"buy_amount: {summary.get('buy_amount', 0):,.2f}")
    logger.info(f"sell_amount: {summary.get('sell_amount', 0):,.2f}")
    logger.info(f"net_inflow: {summary.get('net_inflow', 0):,.2f}")
    logger.info(f"ofi: {summary.get('ofi', 0):.4f}")
    logger.info(f"trade_count: {summary.get('trade_count', 0)}")
    logger.info(f"buy_count: {summary.get('buy_count', 0)}, sell_count: {summary.get('sell_count', 0)}, neutral_count: {summary.get('neutral_count', 0)}")
    logger.info(f"flow_quality_flags: {flow_result.get('quality_flags', [])}")
    logger.info("=" * 60)

    auction_processed_df = pd.DataFrame()
    if auction_df is not None and not auction_df.empty:
        auction_flow = flow_analyzer.analyze(auction_df)
        auction_processed_df = auction_flow.get("processed_df", auction_df)

    aggregator = TickAggregator()
    windows = aggregator.aggregate(processed_df, windows=[1, 5, 10])
    window_1m = windows.get(1, pd.DataFrame())
    window_5m = windows.get(5, pd.DataFrame())
    window_10m = windows.get(10, pd.DataFrame())
    
    # ===== 诊断快照 4: aggregator 聚合后状态 =====
    logger.info("🔍 Tick 诊断快照 - 阶段 4: aggregator 聚合后状态")
    logger.info(f"window_1m.shape: {window_1m.shape if not window_1m.empty else 'EMPTY'}")
    logger.info(f"window_5m.shape: {window_5m.shape if not window_5m.empty else 'EMPTY'}")
    
    if not window_5m.empty:
        logger.info(f"window_5m.columns: {list(window_5m.columns)}")
        display_cols = ["time_window", "buy_amount", "sell_amount", "net_inflow", "ofi", "turnover"]
        available_cols = [c for c in display_cols if c in window_5m.columns]
        logger.info(f"window_5m 前5行关键字段:\n{window_5m[available_cols].head().to_string()}")
        
        if "buy_amount" in window_5m.columns:
            logger.info(f"buy_amount 非零数量: {(window_5m['buy_amount'] != 0).sum()}/{len(window_5m)}")
        if "sell_amount" in window_5m.columns:
            logger.info(f"sell_amount 非零数量: {(window_5m['sell_amount'] != 0).sum()}/{len(window_5m)}")
        if "ofi" in window_5m.columns:
            logger.info(f"ofi 非零数量: {(window_5m['ofi'] != 0).sum()}/{len(window_5m)}")
    else:
        logger.error("❌ window_5m 为空")
    
    logger.info("=" * 60)
    logger.info("✅ Tick 诊断快照完成")
    logger.info("=" * 60)

    ofi_display_df = pd.DataFrame()
    if not window_1m.empty and "ofi" in window_1m.columns:
        ofi_display_df = window_1m[["时间", "ofi"]].copy()
        ofi_display_df["ofi"] = ofi_display_df["ofi"].ewm(alpha=0.3, adjust=False).mean()

        if not window_5m.empty:
            ofi_ema_5m = (
                ofi_display_df.set_index("时间")["ofi"]
                .resample("5min")
                .last()
                .reset_index()
                .rename(columns={"ofi": "ofi_ema"})
            )
            window_5m = window_5m.merge(ofi_ema_5m, on="时间", how="left")

    if not window_1m.empty and "net_inflow" in window_1m.columns:
        window_1m["cum_net_inflow"] = window_1m["net_inflow"].cumsum()
        window_1m["cum_net_inflow_ema"] = window_1m["cum_net_inflow"].ewm(
            alpha=0.2, adjust=False
        ).mean()

    anomaly_detector = TickAnomalyDetector()
    anomaly_source = window_5m if not window_5m.empty else window_1m
    anomaly_result = anomaly_detector.detect(processed_df, anomaly_source)

    large_orders_df = flow_result.get("large_orders", pd.DataFrame())
    large_orders_list = []
    if large_orders_df is not None and not large_orders_df.empty:
        large_orders_df = large_orders_df.sort_values("时间")
        time_score = pd.Series(
            np.linspace(1.0, 0.3, len(large_orders_df)),
            index=large_orders_df.index,
        )
        large_orders_df["weighted_amount"] = large_orders_df["成交额(元)"] * time_score
        top_orders = large_orders_df.sort_values("weighted_amount", ascending=False).head(15)
        for _, row in top_orders.iterrows():
            large_orders_list.append(
                {
                    "time": row.get("时间"),
                    "amount": float(row.get("成交额(元)", 0)),
                    "price": float(row.get("成交价格", row.get("收盘", 0))),
                    "type": row.get("性质", "中性盘"),
                    "ratio": float(row.get("ratio", 0)),
                }
            )

    summary = flow_result.get("summary", {})
    trade_count = summary.get("trade_count", 0) or 1
    flow_summary = {
        "total_turnover": summary.get("total_turnover", 0),
        "large_order_net_inflow": summary.get("large_order_net_inflow", 0),
        "retail_net_inflow": summary.get("retail_net_inflow", 0),
        "large_order_ratio": summary.get("large_order_count", 0) / trade_count * 100,
        "large_order_count": summary.get("large_order_count", 0),
        "large_buy_amount": summary.get("large_buy_amount", 0),
        "large_sell_amount": summary.get("large_sell_amount", 0),
        "retail_buy_amount": summary.get("retail_buy_amount", 0),
        "retail_sell_amount": summary.get("retail_sell_amount", 0),
        "flow_quality": {
            "direction_source": "tick",
            "data_granularity": "tick",
            "large_order_threshold": summary.get("large_order_threshold", 0),
            "large_order_threshold_early": summary.get("large_order_threshold_early", 0),
            "large_order_threshold_note": "per_minute_percentile_or_min",
        },
        "trade_count": summary.get("trade_count", 0),
        "buy_count": summary.get("buy_count", 0),
        "sell_count": summary.get("sell_count", 0),
        "neutral_count": summary.get("neutral_count", 0),
        "buy_amount": summary.get("buy_amount", 0),
        "sell_amount": summary.get("sell_amount", 0),
        "net_inflow": summary.get("net_inflow", 0),
        "buy_ratio": summary.get("buy_ratio", 0),
        "sell_ratio": summary.get("sell_ratio", 0),
        "ofi": summary.get("ofi", 0),
    }

    volume_unit = "shares" if "volume_unit_shares" in quality_flags else "unknown"
    auction_time = None
    if not auction_df.empty and "时间" in auction_df.columns:
        auction_time = auction_df["时间"].max()
    auction_summary = {
        "auction_volume": float(auction_df["成交量"].sum()) if not auction_df.empty else 0.0,
        "auction_amount": float(auction_df["成交额(元)"].sum()) if not auction_df.empty else 0.0,
        "open_gap_percent": None,
        "open_gap_available": False,
        "auction_time": str(auction_time) if auction_time is not None else "",
    }

    base_window_df = window_5m if not window_5m.empty else window_1m
    tick_ai_summary = {}
    if base_window_df is not None and not base_window_df.empty:
        time_windows = base_window_df["time_window"].tolist()
        ofi_series = (
            base_window_df["ofi_ema"] if "ofi_ema" in base_window_df.columns else base_window_df["ofi"]
        )
        tick_ai_summary = {
            "core_20w": {
                "ofi_trend": ofi_series.tail(20).tolist(),
                "net_inflow_trend": base_window_df["net_inflow"].tail(20).tolist(),
                "large_order_counts": base_window_df.get("large_order_count", 0).tail(20).tolist()
                if "large_order_count" in base_window_df.columns
                else [],
            },
            "detail_40w": {
                "time_windows": time_windows[-40:],
                "buy_pressure": base_window_df["buy_amount"].tail(40).tolist()
                if "buy_amount" in base_window_df.columns
                else [],
                "sell_pressure": base_window_df["sell_amount"].tail(40).tolist()
                if "sell_amount" in base_window_df.columns
                else [],
                "price_volatility": base_window_df["range_pct"].tail(40).tolist()
                if "range_pct" in base_window_df.columns
                else [],
            },
            "extended_60w": {
                "available": True,
            },
            "metadata": {
                "summary_range": "40w",
                "inferred_ratio": round(inferred_ratio, 4),
                "volume_unit": volume_unit,
                "note": "All volume data is standardized to shares (1 hand = 100 shares).",
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "auction_summary": auction_summary,
        }

    return {
        "clean_df": processed_df,
        "flow_summary": flow_summary,
        "window_1m": window_1m,
        "window_5m": window_5m,
        "window_10m": window_10m,
        "large_orders_list": large_orders_list,
        "large_orders_top5": large_orders_list[:5],
        "ofi_display_df": ofi_display_df,
        "auction_df": auction_df,
        "auction_processed_df": auction_processed_df,
        "auction_summary": auction_summary,
        "auction_time": auction_time,
        "tick_ai_summary": tick_ai_summary,
        "volume_unit": volume_unit,
        "inferred_ratio": inferred_ratio,
        "burst_windows": anomaly_result.get("burst_windows", []),
        "anomaly_notes": anomaly_result.get("anomaly_notes", []),
        "quality_flags": quality_flags,
    }


def _build_chart_prompts(chart_context: dict, focus: str, style: str) -> tuple[str, str]:
    style_map = {
        "简洁": "4-6条要点，句子短",
        "专业": "分小标题+要点",
    }
    system_prompt = (
        "你是A股日内图表解读助手，只能围绕交易与金融话题回答。"
        "不要给出买卖指令，只解释图表含义与风险。"
    )
    user_prompt = {
        "任务": "解读当前页面图表，不要发散到其他主题",
        "解读侧重点": focus,
        "输出风格": style_map.get(style, style),
        "数据快照": chart_context,
        "输出格式": [
            "总体结论(1-2句)",
            "图表要点(逐条)",
            "风险/不确定性",
            "观察清单(触发条件)"
        ],
    }
    return system_prompt, json.dumps(user_prompt, ensure_ascii=False, indent=2, default=str)
