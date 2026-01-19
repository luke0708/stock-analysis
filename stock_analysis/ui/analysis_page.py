"""
个股分析页面模块
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json

# 导入分析组件
from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.data.providers.tushare_provider import TushareProvider
from stock_analysis.data.cleaner import DataCleaner, get_quality_summary
from stock_analysis.analysis.flows import FlowAnalyzer
from stock_analysis.analysis.timeseries import TimeSeriesAnalyzer
from stock_analysis.analysis.indicators import IndicatorCalculator
from stock_analysis.analysis.anomaly import AnomalyDetector
from stock_analysis.analysis.order_strength import OrderStrengthAnalyzer
from stock_analysis.analysis.ai_client import get_deepseek_key, call_deepseek
from stock_analysis.visualization.charts import ChartGenerator
from stock_analysis.core.help_text import get_indicator_help, get_all_help_topics
from stock_analysis.core.cache_manager import CacheManager, DataImporter
from stock_analysis.core.config import settings
from stock_analysis.core.storage import StorageManager
from stock_analysis.data.stock_list import get_stock_provider

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
                    process_imported_data(df)
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

def process_imported_data(df):
    cleaner = DataCleaner()
    df_clean, quality_report = cleaner.clean(df)
    indicator_calc = IndicatorCalculator()
    df_with_indicators = indicator_calc.calculate_all(df_clean)
    
    st.session_state.df = df_with_indicators
    st.session_state.actual_source = "CSV导入"
    st.session_state.raw_df = None
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

    st.caption(
        f"最后更新: {current_time} | {date_note} | 分析对象: {stock_code} {name} | 数据源: {source} | 质量: {quality['quality_score']:.0f}/100"
    )
    
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
        st.metric("大单数量", f"{large_orders} 笔")
    
    st.markdown("---")

    # ===== 第二行：核心走势 =====
    cg = ChartGenerator()
    st.subheader("📈 分时走势 + 成交量")
    st.plotly_chart(cg.create_candlestick_chart(df, stock_code), use_container_width=True)

    flows = analysis.get('flows', {})
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

    stacked_area_fig = cg.create_stacked_area_flow(df, analysis.get('flows', {}), resample_minutes=30)
    strength_fig = cg.create_order_strength_chart(analysis.get('strength_timeseries', pd.DataFrame()))

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
            chart_context = _build_chart_context(df, analysis)
            st.json(chart_context)

        col_ai1, col_ai2 = st.columns([1, 3])
        with col_ai1:
            gen_chart_btn = st.button("生成图表解读", type="primary")
        with col_ai2:
            st.caption("提示：生成会调用外部API，速度取决于网络。")

        if gen_chart_btn:
            chart_context = _build_chart_context(df, analysis)
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


def _build_chart_context(df: pd.DataFrame, analysis: dict) -> dict:
    timeseries = analysis.get('timeseries', {})
    flows = analysis.get('flows', {})
    indicators = analysis.get('indicators', {})
    anomalies = analysis.get('anomalies', {})

    df_chart = df.copy()
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
        df_chart['净流入额'] = df_chart.apply(calc_net, axis=1)
        df_chart['累计净流入'] = df_chart['净流入额'].cumsum()
        cum_flow_last = float(df_chart['累计净流入'].iloc[-1])
    else:
        cum_flow_last = 0.0

    total_net = flows.get('large_order_net_inflow', 0) + flows.get('retail_net_inflow', 0)

    return {
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
