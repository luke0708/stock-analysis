"""
未来功能占位页 (Mockups)
展示即将推出的功能预览图，让用户更有实感
"""
import streamlit as st
import pandas as pd
import numpy as np
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from stock_analysis.data.stock_list import get_stock_provider
from stock_analysis.analysis.ai_client import get_deepseek_key, call_deepseek
from stock_analysis.data.news_provider import StockNewsProvider


@st.cache_data(ttl=300)
def _load_stock_news(stock_code: str, limit: int) -> pd.DataFrame:
    return StockNewsProvider.get_stock_news(stock_code, limit=limit)


def _build_news_payload(news_df: Optional[pd.DataFrame], stock_name: str) -> Dict:
    if news_df is None or news_df.empty:
        return {
            "has_news": False,
            "source": "AkShare",
            "stock_name": stock_name,
            "items": [],
        }

    items = []
    for _, row in news_df.head(6).iterrows():
        items.append({
            "time": row.get("发布时间", ""),
            "title": row.get("新闻标题", ""),
            "summary": row.get("新闻内容", ""),
        })

    return {
        "has_news": True,
        "source": "AkShare",
        "stock_name": stock_name,
        "items": items,
        "latest_time": items[0]["time"] if items else None,
    }

def show_multi_stock_compare():
    st.header("⚖️ 多股票对比分析 (Coming Soon)")
    st.info("🚧 此功能将在 v1.2 版本上线")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("功能预览")
        st.markdown("""
        - **多维叠加**: 同时查看最多 5 只股票的走势
        - **相对收益**: 以某日为基准查看相对涨跌幅
        - **资金流对比**: 横向比较谁的主力介入更深
        """)
        
    with col2:
        # Mock chart
        dates = pd.date_range(end=pd.Timestamp.now(), periods=100)
        # Generate trend data (cumulative sum) + ensure no infinities
        np.random.seed(42)  # Fixed seed for stability
        data = pd.DataFrame(
            np.random.randn(100, 3).cumsum(0),
            index=dates,
            columns=['贵州茅台 (Mock)', '宁德时代 (Mock)', '招商银行 (Mock)']
        )
        # Add offset to avoid 0/negative if using log scale (though line_chart defaults to linear)
        data = data + 100 
        
        st.line_chart(data)

def show_backtesting():
    st.header("🧪 策略回测实验室 (Coming Soon)")
    st.warning("🚧 此功能将在 v1.3 版本上线")
    
    st.markdown("### 预设策略配置")
    c1, c2, c3 = st.columns(3)
    c1.selectbox("交易策略", ["双均线交叉", "RSI超买超卖", "网格交易"])
    c2.date_input("回测开始", value=pd.to_datetime("2023-01-01"))
    c3.number_input("初始资金", value=100000)
    
    st.button("开始回测 (演示按钮)", disabled=True)
    
    st.markdown("### 预期回测报告")
    st.write("📈 年化收益率: 15.2% | 📉 最大回撤: -8.5% | 🎯 胜率: 58%")
    
def show_global_markets():
    st.header("🌍 全球市场概览 (Coming Soon)")
    st.success("🚧 长期规划功能 (v2.2)")
    
    cols = st.columns(4)
    cols[0].metric("纳斯达克", "14,890.30", "+1.2%")
    cols[1].metric("恒生指数", "16,500.00", "-0.5%")
    cols[2].metric("日经225", "35,000.00", "+0.8%")
    cols[3].metric("标普500", "4,780.00", "+0.9%")
    
    st.caption("*以上数据仅为静态演示*")

def show_ai_analysis():
    st.header("🤖 AI 智能投顾")
    st.caption("专注于A股资金流向与日内交易解读，输出为结构化结论")

    api_key, api_key_name = get_deepseek_key()
    if not api_key:
        st.warning("未检测到 DeepSeek API Key，请在 .env 中配置后再使用。")
        st.code("DEEPSEEK_API_KEY=你的key", language="bash")
        return

    st.caption(f"当前使用环境变量: {api_key_name}")

    if "df" not in st.session_state or st.session_state.df is None:
        st.info("请先在“个股资金流向”页面完成一次分析，以便生成更准确的 AI 解读。")
        return

    if "ai_history" not in st.session_state:
        st.session_state.ai_history = []
    if "ai_last" not in st.session_state:
        st.session_state.ai_last = None
    if "ai_news_df" not in st.session_state:
        st.session_state.ai_news_df = None
    if "ai_news_stock" not in st.session_state:
        st.session_state.ai_news_stock = ""
    if "ai_news_limit" not in st.session_state:
        st.session_state.ai_news_limit = 0

    with st.expander("ℹ️ 输入数据说明", expanded=False):
        st.write(
            "模型输入来自最近一次个股分析结果，包含价格、资金流、技术指标与异动统计。"
            "原始数据已经过 DataCleaner 清洗（修复缺失值/异常值、标准化类型）。"
            "模型输出高度依赖这些结构化数据，因此切换日期或股票会显著影响解读。"
        )

    st.markdown("### 🎯 分析目标")
    focus = st.radio(
        "请选择分析侧重点",
        ["资金流向解读", "盘中趋势与节奏", "风险与异动", "主力行为复盘"],
        horizontal=True,
        help="切换侧重点会改变提示词，但需要点击“生成解读”才会更新结果。"
    )

    style = st.radio(
        "输出风格",
        ["简洁", "专业", "交易员风格"],
        horizontal=True,
        help="简洁=要点短句；专业=分小标题；交易员=更强调盘中节奏。"
    )

    col1, col2 = st.columns(2)
    with col1:
        avoid_advice = st.checkbox(
            "避免买卖指令",
            value=True,
            help="仅做分析，不直接给出买/卖指令。"
        )
        only_data = st.checkbox(
            "只基于给定数据",
            value=True,
            help="只使用当前分析结果，不引入外部信息。"
        )
    with col2:
        highlight_numbers = st.checkbox(
            "突出关键数值",
            value=True,
            help="必须引用关键数据作为论据。"
        )
        add_watchlist = st.checkbox(
            "给出观察清单",
            value=True,
            help="列出后续关注的触发条件或关键变量。"
        )

    temperature = st.slider(
        "输出多样性 (temperature)",
        min_value=0.0,
        max_value=0.8,
        value=0.2,
        step=0.1,
        help="数值越低越稳定、越接近确定输出；数值越高越多样化。"
    )

    user_question = st.text_area(
        "补充问题（可选）",
        placeholder="例如：今天主力吸筹是否明显？短线有哪些风险点？",
        help="补充具体问题会改变解读重点；若涉及新闻，请开启下方“包含最新相关新闻”。"
    )

    st.markdown("### 📰 新闻补充（可选）")
    include_news = st.checkbox(
        "包含最新相关新闻",
        value=False,
        help="从 AkShare 拉取相关新闻，可能有延迟或缺失。"
    )
    news_limit = st.slider(
        "新闻条数",
        min_value=3,
        max_value=12,
        value=6,
        step=1,
        disabled=not include_news
    )
    news_df = None
    stock_code = st.session_state.get("last_stock_code", "")
    if include_news:
        col_n1, col_n2 = st.columns([1, 3])
        with col_n1:
            fetch_news = st.button("拉取新闻")
        with col_n2:
            st.caption("提示：仅供分析参考，新闻覆盖可能不完整。")

        if fetch_news:
            with st.spinner("正在拉取相关新闻..."):
                news_df = _load_stock_news(stock_code, limit=news_limit)
                st.session_state.ai_news_df = news_df
                st.session_state.ai_news_stock = stock_code
                st.session_state.ai_news_limit = news_limit

        if (
            st.session_state.ai_news_df is not None
            and st.session_state.ai_news_stock == stock_code
            and st.session_state.ai_news_limit == news_limit
        ):
            news_df = st.session_state.ai_news_df

        if news_df is not None:
            if news_df.empty:
                st.info("暂未获取到相关新闻。")
            else:
                for _, row in news_df.head(5).iterrows():
                    title = row.get("新闻标题", "")
                    time = row.get("发布时间", "")
                    st.markdown(f"- [{time}] {title}")

    if user_question:
        news_keywords = ["新闻", "公告", "消息", "政策", "事件", "报道"]
        if any(k in user_question for k in news_keywords) and not include_news:
            st.warning("检测到新闻类问题，建议勾选“包含最新相关新闻”并拉取新闻。")

    with st.expander("📌 输入给模型的数据预览", expanded=False):
        context = _build_context(news_df=news_df, include_news=include_news)
        st.json(_json_safe(context))

    col_g1, col_g2 = st.columns([1, 3])
    with col_g1:
        generate_btn = st.button("生成解读", type="primary")
    with col_g2:
        st.caption("提示：生成会调用外部API，速度取决于网络。")

    if generate_btn:
        if include_news and news_df is None:
            with st.spinner("正在拉取相关新闻..."):
                news_df = _load_stock_news(stock_code, limit=news_limit)
                st.session_state.ai_news_df = news_df
                st.session_state.ai_news_stock = stock_code
                st.session_state.ai_news_limit = news_limit

        context = _build_context(news_df=news_df, include_news=include_news)
        stock_info = context.get("stock", {})
        session_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{stock_info.get('code', '')}"
        system_prompt, user_prompt = _build_prompts(
            context=context,
            focus=focus,
            style=style,
            avoid_advice=avoid_advice,
            only_data=only_data,
            highlight_numbers=highlight_numbers,
            add_watchlist=add_watchlist,
            user_question=user_question
        )
        params_summary = _summarize_settings(
            focus=focus,
            style=style,
            avoid_advice=avoid_advice,
            only_data=only_data,
            highlight_numbers=highlight_numbers,
            add_watchlist=add_watchlist,
            user_question=user_question
        )
        with st.spinner("正在生成AI解读..."):
            try:
                response = call_deepseek(
                    api_key=api_key,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature
                )
                entry = {
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "focus": focus,
                    "style": style,
                    "constraints": params_summary,
                    "user_question": user_question,
                    "temperature": temperature,
                    "response": response,
                    "system_prompt": system_prompt,
                    "context": _json_safe(context),
                    "stock_code": stock_info.get("code", ""),
                    "stock_name": stock_info.get("name", ""),
                    "requested_date": stock_info.get("requested_date"),
                    "actual_date": stock_info.get("actual_date"),
                    "session_id": session_id,
                    "followups": []
                }
                st.session_state.ai_history.append(entry)
                st.session_state.ai_last = entry
            except Exception as exc:
                st.error(f"请求失败: {exc}")
                return

    if st.session_state.ai_last:
        st.markdown("### ✅ 最新解读")
        stock_label = f"{st.session_state.ai_last.get('stock_code', '')} {st.session_state.ai_last.get('stock_name', '')}".strip()
        date_label = st.session_state.ai_last.get("actual_date") or st.session_state.ai_last.get("requested_date") or "未知日期"
        st.caption(
            f"{st.session_state.ai_last['ts']} | "
            f"{st.session_state.ai_last['focus']} | "
            f"{st.session_state.ai_last['style']} | "
            f"temp {st.session_state.ai_last['temperature']:.1f} | "
            f"标的: {stock_label or '未知'} | "
            f"日期: {date_label} | "
            f"会话: {st.session_state.ai_last.get('session_id', '--')}"
        )
        st.write(st.session_state.ai_last["response"])

        st.markdown("### 💬 继续追问")
        st.caption("追问会基于“最新解读”的同一份数据快照与提示词继续回答。")
        st.caption(f"当前会话: {st.session_state.ai_last.get('session_id', '--')}")
        followup = st.text_input("基于当前解读继续提问", key="ai_followup")
        followup_btn = st.button("发送追问")
        if followup_btn:
            if not followup.strip():
                st.warning("请输入追问内容。")
            else:
                with st.spinner("正在追问..."):
                    try:
                        follow_prompt = _build_followup_prompt(
                            context=st.session_state.ai_last["context"],
                            focus=st.session_state.ai_last["focus"],
                            constraints=st.session_state.ai_last["constraints"],
                            previous_answer=st.session_state.ai_last["response"],
                            followup=followup
                        )
                        follow_response = call_deepseek(
                            api_key=api_key,
                            system_prompt=st.session_state.ai_last["system_prompt"],
                            user_prompt=follow_prompt,
                            temperature=st.session_state.ai_last.get("temperature", 0.2)
                        )
                        st.session_state.ai_last["followups"].append(
                            {"q": followup, "a": follow_response}
                        )
                    except Exception as exc:
                        st.error(f"追问失败: {exc}")
                        return

        if st.session_state.ai_last["followups"]:
            st.markdown("#### 🧵 追问记录")
            for item in st.session_state.ai_last["followups"][-5:]:
                st.markdown(f"**Q**: {item['q']}")
                st.markdown(f"**A**: {item['a']}")

    if st.session_state.ai_history:
        with st.expander("🗂️ 历史解读", expanded=False):
            for item in reversed(st.session_state.ai_history[-5:]):
                stock_label = f"{item.get('stock_code', '')} {item.get('stock_name', '')}".strip()
                date_label = item.get("actual_date") or item.get("requested_date") or "未知日期"
                st.markdown(
                    f"**{item['ts']} | {item['focus']} | {item['style']} | "
                    f"{stock_label or '未知标的'} | {date_label} | 会话 {item.get('session_id', '--')}**"
                )
                if item.get("user_question"):
                    st.caption(f"补充问题: {item['user_question']}")
                st.write(item["response"])


def _build_context(
    news_df: Optional[pd.DataFrame] = None,
    include_news: bool = False
) -> Dict:
    df = st.session_state.df
    analysis = st.session_state.all_analysis
    quality = st.session_state.quality_report
    stock_code = st.session_state.get("last_stock_code", "")

    stock_provider = get_stock_provider()
    stock_name = stock_code
    try:
        res = stock_provider.search(stock_code, limit=1)
        if not res.empty:
            stock_name = res.iloc[0]["名称"]
    except Exception:
        pass

    actual_date = df.attrs.get("actual_date")
    requested_date = df.attrs.get("requested_date")

    flows = analysis.get("flows", {})
    timeseries = analysis.get("timeseries", {})
    indicators = analysis.get("indicators", {})
    anomalies = analysis.get("anomalies", {})
    large_orders = anomalies.get("large_orders", [])
    large_orders_sorted = sorted(large_orders, key=lambda x: x.get("amount", 0), reverse=True)
    top_orders = [
        {
            "time": str(o.get("time", "")),
            "amount": float(o.get("amount", 0)),
            "price": float(o.get("price", 0)),
            "type": o.get("type", "未知"),
            "ratio": float(o.get("ratio", 0)),
        }
        for o in large_orders_sorted[:3]
    ]

    context = {
        "stock": {
            "code": stock_code,
            "name": stock_name,
            "requested_date": requested_date,
            "actual_date": actual_date,
            "data_quality_score": quality.get("quality_score", 0),
        },
        "price": {
            "open": timeseries.get("open_price"),
            "close": timeseries.get("close_price"),
            "high": timeseries.get("high_price"),
            "low": timeseries.get("low_price"),
            "change": timeseries.get("price_change"),
            "change_pct": timeseries.get("price_change_pct"),
            "amplitude": timeseries.get("amplitude"),
        },
        "liquidity": {
            "turnover_total": timeseries.get("turnover_total"),
            "volume_total": timeseries.get("volume_total"),
            "avg_price": timeseries.get("avg_price"),
        },
        "flow": {
            "large_net": flows.get("large_order_net_inflow"),
            "retail_net": flows.get("retail_net_inflow"),
            "large_ratio": flows.get("large_order_ratio"),
            "large_buy": flows.get("large_buy_amount"),
            "large_sell": flows.get("large_sell_amount"),
            "quality": flows.get("flow_quality", {}),
        },
        "indicators": {
            "vwap": indicators.get("vwap"),
            "price_vs_vwap": indicators.get("price_vs_vwap"),
            "ma5": indicators.get("ma5"),
            "ma10": indicators.get("ma10"),
            "is_above_vwap": indicators.get("is_above_vwap"),
            "is_above_ma5": indicators.get("is_above_ma5"),
            "is_above_ma10": indicators.get("is_above_ma10"),
        },
        "anomalies": {
            "large_order_count": anomalies.get("summary", {}).get("large_order_count", 0),
            "price_spike_count": anomalies.get("summary", {}).get("price_spike_count", 0),
            "volume_surge_count": anomalies.get("summary", {}).get("volume_surge_count", 0),
            "top_large_orders": top_orders,
        },
    }
    if include_news:
        context["news"] = _build_news_payload(news_df, stock_name)
    return context


def _build_prompts(
    context: Dict,
    focus: str,
    style: str,
    avoid_advice: bool,
    only_data: bool,
    highlight_numbers: bool,
    add_watchlist: bool,
    user_question: str
) -> Tuple[str, str]:
    constraints = []
    if avoid_advice:
        constraints.append("不要给出明确买卖指令或收益承诺")
    if only_data:
        constraints.append("仅基于提供的数据进行判断，不要编造")
    if highlight_numbers:
        constraints.append("必须引用关键数值作为依据")
    if add_watchlist:
        constraints.append("给出可观察的触发条件或关键变量")
    news_payload = context.get("news")
    if news_payload is not None:
        if news_payload.get("has_news"):
            constraints.append("如有新闻条目，仅基于新闻内容推断潜在影响，避免夸大")
        else:
            constraints.append("若未提供新闻数据需明确说明无法判断新闻影响")

    style_map = {
        "简洁": "4-6条要点，句子短",
        "专业": "分小标题+要点",
        "交易员风格": "强调盘中节奏、资金方向，语气紧凑"
    }

    focus_map = {
        "资金流向解读": [
            "主力/散户净流入方向与强度",
            "大单占比与主力买卖额差异",
            "累计净流入是否持续"
        ],
        "盘中趋势与节奏": [
            "开收/高低位置与振幅",
            "VWAP/均线偏离与盘中节奏",
            "上涨分钟占比"
        ],
        "风险与异动": [
            "价格跳跃次数与方向",
            "成交量异常放大",
            "大单异常集中时段"
        ],
        "主力行为复盘": [
            "主力净流入与价格走势是否一致",
            "主力买卖额差异",
            "主力占比与关键时段"
        ],
    }

    system_prompt = (
        "你是专注于A股日内资金流向分析的助手，只能围绕交易与金融话题回答。"
        "回复必须结构化，语言简洁，避免发散。"
    )

    user_prompt = {
        "分析目标": focus,
        "输出风格": style_map.get(style, style),
        "约束": constraints,
        "重点关注": focus_map.get(focus, []),
        "补充问题": user_question or "无",
        "数据快照": _json_safe(context),
        "输出格式": [
            "概览(1-2句)",
            "关键依据(列出关键数值)",
            "风险/不确定性",
            "观察清单(触发条件)"
        ],
    }

    return system_prompt, json.dumps(user_prompt, ensure_ascii=False, indent=2)


def _summarize_settings(
    focus: str,
    style: str,
    avoid_advice: bool,
    only_data: bool,
    highlight_numbers: bool,
    add_watchlist: bool,
    user_question: str
) -> List[str]:
    tags = [focus, style]
    if avoid_advice:
        tags.append("无买卖指令")
    if only_data:
        tags.append("仅基于数据")
    if highlight_numbers:
        tags.append("强调数值")
    if add_watchlist:
        tags.append("给观察清单")
    if user_question:
        tags.append("含补充问题")
    return tags


def _build_followup_prompt(
    context: Dict,
    focus: str,
    constraints: List[str],
    previous_answer: str,
    followup: str
) -> str:
    focus_map = {
        "资金流向解读": ["主力/散户净流入", "累计净流入", "大单占比"],
        "盘中趋势与节奏": ["盘中节奏", "VWAP/均线偏离", "振幅"],
        "风险与异动": ["价格跳跃", "成交量激增", "大单异常"],
        "主力行为复盘": ["主力净流入与价格一致性", "主力买卖额差异"],
    }
    payload = {
        "任务": "基于已有解读继续回答追问，保持金融交易语境",
        "分析目标": focus,
        "约束": constraints,
        "重点关注": focus_map.get(focus, []),
        "已有解读": previous_answer,
        "追问": followup,
        "数据快照": context,
        "输出要求": [
            "直接回答问题",
            "引用关键数据",
            "不扩展到无关话题"
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)
