"""
实时预警页面
"""
import streamlit as st
from datetime import datetime, time as dt_time
from typing import Dict, List

from stock_analysis.data.providers.akshare_provider import AkShareProvider
from stock_analysis.analysis.flows import FlowAnalyzer
from stock_analysis.data.stock_list import get_stock_provider

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # pragma: no cover - optional dependency
    st_autorefresh = None


def show_alert_page():
    st.header("🔔 实时预警")
    st.caption("基于资金流向与大单阈值的简易预警（交易时段内有效）")

    if st_autorefresh is None:
        st.warning("缺少依赖 `streamlit-autorefresh`，请先在虚拟环境中安装。")
        st.code("pip install streamlit-autorefresh", language="bash")
        return

    if "alert_codes" not in st.session_state:
        st.session_state.alert_codes = "300661,600519"

    col_a, col_b = st.columns([3, 2])
    with col_a:
        codes_input = st.text_input("监控列表（逗号分隔）", value=st.session_state.alert_codes)
        st.session_state.alert_codes = codes_input
    with col_b:
        auto_refresh = st.toggle("自动刷新", value=False)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        interval_sec = st.slider("刷新间隔(秒)", 5, 300, 30)
    with col2:
        net_threshold = st.number_input("净流入阈值(万元)", min_value=0.0, value=1000.0, step=100.0)
    with col3:
        large_order_threshold = st.number_input("大单阈值(万元)", min_value=10.0, value=200.0, step=10.0)
    with col4:
        consecutive_required = st.slider("连续触发次数", 1, 5, 2)

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        use_net = st.checkbox("启用净流入阈值", value=True)
    with col_c2:
        use_large = st.checkbox("启用大单阈值", value=True)

    if not use_net and not use_large:
        st.warning("请至少启用一个预警条件。")
        return

    codes = _parse_codes(codes_input)
    if not codes:
        st.info("请输入至少一只股票代码。")
        return

    max_codes = 6
    if len(codes) > max_codes:
        st.warning(f"监控数量过多，将只取前 {max_codes} 只以避免请求过慢。")
        codes = codes[:max_codes]

    if interval_sec < 15 and len(codes) > 3:
        st.warning("刷新过快且监控数量较多，可能导致数据源限流或失败。")

    is_trading, session_label = _get_trading_status(datetime.now())
    st.caption(f"交易时段: {session_label}")

    if auto_refresh:
        if is_trading:
            st_autorefresh(interval=interval_sec * 1000, key="alert_refresh")
        else:
            st.warning("当前非交易时段，已自动暂停刷新。")
            if st.button("手动刷新"):
                st.rerun()

    provider = AkShareProvider()
    flow_analyzer = FlowAnalyzer(large_order_threshold=large_order_threshold * 10000)
    name_cache = _get_name_cache()
    streaks = st.session_state.setdefault("alert_streaks", {})

    progress = st.progress(0, text="正在拉取数据...")
    results = []
    details: Dict[str, Dict] = {}

    for idx, code in enumerate(codes, start=1):
        df = provider.get_realtime_data(code)
        name = _get_stock_name(code, name_cache)
        if df.empty:
            results.append({
                "代码": code,
                "名称": name,
                "状态": "无数据",
                "连续触发": "0",
                "总净流入(亿)": "--",
                "大单数": "--",
            })
            progress.progress(int(idx / len(codes) * 100), text=f"完成 {idx}/{len(codes)}")
            continue

        flow_summary = flow_analyzer.calculate_flows(df)
        net_inflow = flow_summary.get("large_order_net_inflow", 0) + flow_summary.get("retail_net_inflow", 0)
        large_count = int(flow_summary.get("large_order_count", 0))

        trigger_reasons = []
        if use_net and net_inflow >= net_threshold * 10000:
            trigger_reasons.append(f"净流入 {net_inflow/1e8:.2f}亿")
        if use_large and large_count > 0:
            trigger_reasons.append(f"大单 {large_count} 笔")

        triggered = len(trigger_reasons) > 0
        prev_streak = streaks.get(code, 0)
        streaks[code] = prev_streak + 1 if triggered else 0

        if triggered:
            if streaks[code] >= consecutive_required:
                status = "触发"
            else:
                status = f"观察中({streaks[code]}/{consecutive_required})"
        else:
            status = "未触发"

        results.append({
            "代码": code,
            "名称": name,
            "状态": status,
            "连续触发": f"{streaks[code]}/{consecutive_required}",
            "总净流入(亿)": f"{net_inflow/1e8:.2f}",
            "大单数": f"{large_count}",
        })

        details[code] = {
            "df": df,
            "flow_summary": flow_summary,
            "net_inflow": net_inflow,
            "trigger_reasons": trigger_reasons,
        }

        progress.progress(int(idx / len(codes) * 100), text=f"完成 {idx}/{len(codes)}")

    progress.empty()

    st.markdown("---")
    st.subheader("📌 预警结果")
    updated_time = datetime.now().strftime("%H:%M:%S")
    st.caption(f"更新时间: {updated_time}")

    st.dataframe(
        results,
        use_container_width=True,
        height=260
    )

    detail_code = st.selectbox("查看详情", [r["代码"] for r in results])
    detail = details.get(detail_code)
    if detail:
        flow_summary = detail["flow_summary"]
        net_inflow = detail["net_inflow"]
        trigger_reasons = detail["trigger_reasons"]

        if trigger_reasons:
            st.success(" | ".join(trigger_reasons))
        else:
            st.info("未触发预警条件")

        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("主力净流入", f"¥{flow_summary.get('large_order_net_inflow', 0)/1e8:.2f}亿")
        with col_s2:
            st.metric("散户净流入", f"¥{flow_summary.get('retail_net_inflow', 0)/1e8:.2f}亿")
        with col_s3:
            st.metric("大单数量", f"{flow_summary.get('large_order_count', 0)}")

    st.caption("提示：免费数据源建议刷新间隔≥30秒，监控数量≤5。")


def _get_trading_status(now: datetime) -> tuple[bool, str]:
    if now.weekday() >= 5:
        return False, "休市"

    t = now.time()
    morning_start = dt_time(9, 30)
    morning_end = dt_time(11, 30)
    afternoon_start = dt_time(13, 0)
    afternoon_end = dt_time(15, 0)

    if morning_start <= t <= morning_end:
        return True, "上午盘 09:30-11:30"
    if afternoon_start <= t <= afternoon_end:
        return True, "下午盘 13:00-15:00"
    return False, "非交易时段"


def _parse_codes(raw: str) -> List[str]:
    items = [c.strip() for c in raw.split(",")]
    items = [c for c in items if c]
    unique = []
    for code in items:
        if code not in unique:
            unique.append(code)
    return unique


def _get_name_cache() -> Dict[str, str]:
    if "alert_name_cache" not in st.session_state:
        st.session_state.alert_name_cache = {}
    return st.session_state.alert_name_cache


def _get_stock_name(code: str, cache: Dict[str, str]) -> str:
    if code in cache:
        return cache[code]
    provider = get_stock_provider()
    name = code
    try:
        res = provider.search(code, limit=1)
        if not res.empty:
            name = res.iloc[0]["名称"]
    except Exception:
        pass
    cache[code] = name
    return name
