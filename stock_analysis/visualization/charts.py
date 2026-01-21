"""
可视化图表生成函数
使用 Plotly 创建交互式图表
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List

class ChartGenerator:
    """图表生成器"""
    
    @staticmethod
    def create_candlestick_chart(df: pd.DataFrame, stock_code: str = "") -> go.Figure:
        """
        创建分时K线图with VWAP和成交量
        
        Args:
            df: 包含OHLC、VWAP和成交量的DataFrame
            stock_code: 股票代码
            
        Returns:
            Plotly Figure对象
        """
        # 创建子图：主图(K线) + 副图(成交量)
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=(f'{stock_code} 分时走势', '成交量'),
            row_heights=[0.7, 0.3]
        )
        
        # K线图
        fig.add_trace(
            go.Candlestick(
                x=df['时间'],
                open=df['开盘'],
                high=df['最高'],
                low=df['最低'],
                close=df['收盘'],
                name='K线',
                increasing_line_color='#ff4d4f',  # 红色上涨
                decreasing_line_color='#52c41a'   # 绿色下跌
            ),
            row=1, col=1
        )
        
        # VWAP线
        if 'VWAP' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['时间'],
                    y=df['VWAP'],
                    mode='lines',
                    name='VWAP',
                    line=dict(color='#1890ff', width=2, dash='dash')
                ),
                row=1, col=1
            )
        
        # MA5线
        if 'MA5' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['时间'],
                    y=df['MA5'],
                    mode='lines',
                    name='MA5',
                    line=dict(color='#faad14', width=1)
                ),
                row=1, col=1
            )
        
        # 成交量柱状图（根据涨跌着色）
        colors = ['#ff4d4f' if close >= open_ else '#52c41a' 
                 for close, open_ in zip(df['收盘'], df['开盘'])]
        
        fig.add_trace(
            go.Bar(
                x=df['时间'],
                y=df['成交量'],
                name='成交量',
                marker_color=colors,
                opacity=0.6
            ),
            row=2, col=1
        )
        
        # 更新布局
        fig.update_layout(
            title=f'{stock_code} 实时分析',
            xaxis_rangeslider_visible=False,
            height=700,
            hovermode='x unified',
            template='plotly_white',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        fig.update_xaxes(title_text="时间", row=2, col=1)
        fig.update_yaxes(title_text="价格 (¥)", row=1, col=1)
        fig.update_yaxes(title_text="成交量 (手)", row=2, col=1)
        
        return fig
    
    @staticmethod
    def create_flow_waterfall(flow_data: Dict) -> go.Figure:
        """
        创建资金流向瀑布图
        
        Args:
            flow_data: 资金流向数据
        """
        fig = go.Figure(go.Waterfall(
            name="资金流向",
            orientation="v",
            measure=["relative", "relative", "total"],
            x=["主力净流入", "散户净流入", "总计"],
            y=[
                flow_data.get('large_order_net_inflow', 0),
                flow_data.get('retail_net_inflow', 0),
                0
            ],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            increasing={"marker": {"color": "#ff4d4f"}},
            decreasing={"marker": {"color": "#52c41a"}},
            totals={"marker": {"color": "#1890ff"}}
        ))
        
        fig.update_layout(
            title="资金流向分析",
            showlegend=False,
            height=400,
            template='plotly_white'
        )
        
        fig.update_yaxes(title_text="金额 (¥)")
        
        return fig
    
    @staticmethod
    def create_order_strength_chart(df: pd.DataFrame) -> go.Figure:
        """
        创建买卖盘力度堆叠柱状图
        
        Args:
            df: 包含买盘额和卖盘额的DataFrame
        """
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=df['时间'],
            y=df['买盘额'],
            name='买盘',
            marker_color='#ff4d4f',
            opacity=0.8
        ))
        
        fig.add_trace(go.Bar(
            x=df['时间'],
            y=-df['卖盘额'],  # 负值放在下方
            name='卖盘',
            marker_color='#52c41a',
            opacity=0.8
        ))
        
        fig.update_layout(
            title="买卖盘力度对比",
            barmode='relative',
            height=400,
            hovermode='x unified',
            template='plotly_white',
            showlegend=True
        )
        
        fig.update_xaxes(title_text="时间")
        fig.update_yaxes(title_text="成交额 (¥)")
        
        # 添加0轴参考线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        return fig

    @staticmethod
    def create_ofi_trend_chart(df: pd.DataFrame) -> go.Figure:
        """
        创建订单流失衡（OFI）走势
        """
        df_copy = df.copy()
        if df_copy.empty or '时间' not in df_copy.columns or 'ofi' not in df_copy.columns:
            return go.Figure()

        df_copy['时间'] = pd.to_datetime(df_copy['时间'], errors='coerce')
        df_copy = df_copy.dropna(subset=['时间'])

        clip_val = df_copy['ofi'].abs().quantile(0.95)
        if pd.isna(clip_val) or clip_val == 0:
            clip_val = 1
        df_copy['ofi_clip'] = df_copy['ofi'].clip(-clip_val, clip_val)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_copy['时间'],
            y=df_copy['ofi_clip'],
            mode='lines+markers',
            name='OFI',
            line=dict(color='#5c7cfa', width=2),
            marker=dict(size=4)
        ))

        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(
            title="订单流失衡 (OFI) 走势",
            height=350,
            hovermode='x unified',
            template='plotly_white',
            showlegend=False
        )
        fig.update_yaxes(title_text="OFI")
        fig.update_xaxes(title_text="时间")
        return fig

    @staticmethod
    def create_trade_density_chart(df: pd.DataFrame) -> go.Figure:
        """
        创建成交密度与短时波动图
        """
        if df.empty or '时间' not in df.columns:
            return go.Figure()

        df_copy = df.copy()
        df_copy['时间'] = pd.to_datetime(df_copy['时间'], errors='coerce')
        df_copy = df_copy.dropna(subset=['时间'])

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        if 'trade_count' in df_copy.columns:
            fig.add_trace(
                go.Bar(
                    x=df_copy['时间'],
                    y=df_copy['trade_count'],
                    name='成交笔数',
                    marker_color='rgba(120,120,120,0.5)'
                ),
                secondary_y=False
            )

        if 'range_pct' in df_copy.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_copy['时间'],
                    y=df_copy['range_pct'],
                    name='波动率(%)',
                    line=dict(color='#ff922b', width=2)
                ),
                secondary_y=True
            )

        fig.update_layout(
            title="成交密度与短时波动",
            height=350,
            hovermode='x unified',
            template='plotly_white',
            showlegend=False
        )
        fig.update_yaxes(title_text="成交笔数", secondary_y=False)
        fig.update_yaxes(title_text="波动率(%)", secondary_y=True)
        fig.update_xaxes(title_text="时间")
        return fig
    
    @staticmethod
    def create_cumulative_change_chart(df: pd.DataFrame) -> go.Figure:
        """
        创建累计涨跌幅曲线图
        """
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['时间'],
            y=df['累计涨跌幅'],
            mode='lines',
            name='累计涨跌幅',
            fill='tozeroy',
            line=dict(color='#1890ff', width=2),
            fillcolor='rgba(24, 144, 255, 0.2)'
        ))
        
        fig.update_layout(
            title="累计涨跌幅走势",
            height=350,
            hovermode='x unified',
            template='plotly_white',
            showlegend=False
        )
        
        fig.update_xaxes(title_text="时间")
        fig.update_yaxes(title_text="涨跌幅 (%)")
        
        # 添加0轴参考线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        
        return fig

    @staticmethod
    def create_comparison_price_chart(
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        name_a: str,
        name_b: str
    ) -> go.Figure:
        """
        创建多股涨幅叠加对比图
        """
        def normalize_price(df: pd.DataFrame) -> pd.DataFrame:
            df_copy = df.copy()
            if '时间' not in df_copy.columns:
                for time_col in ['成交时间', 'time', 'datetime', '时间戳']:
                    if time_col in df_copy.columns:
                        df_copy = df_copy.rename(columns={time_col: '时间'})
                        break

            if '时间' in df_copy.columns:
                df_copy['时间'] = pd.to_datetime(df_copy['时间'], errors='coerce')
                df_copy = df_copy.dropna(subset=['时间']).sort_values('时间')

            price_col = None
            for col in ['收盘', '成交价格', '价格', '最新价']:
                if col in df_copy.columns:
                    price_col = col
                    break

            base_col = '开盘' if '开盘' in df_copy.columns else price_col
            if price_col is None or base_col is None or df_copy.empty:
                return pd.DataFrame(columns=['时间', '涨幅'])

            base_price = df_copy[base_col].iloc[0]
            if base_price == 0:
                df_copy['涨幅'] = 0.0
            else:
                df_copy['涨幅'] = (df_copy[price_col] - base_price) / base_price * 100

            return df_copy[['时间', '涨幅']]

        series_a = normalize_price(df_a)
        series_b = normalize_price(df_b)

        fig = go.Figure()
        if not series_a.empty:
            fig.add_trace(go.Scatter(
                x=series_a['时间'],
                y=series_a['涨幅'],
                name=name_a,
                line=dict(color='#ff4d4f', width=2)
            ))
        if not series_b.empty:
            fig.add_trace(go.Scatter(
                x=series_b['时间'],
                y=series_b['涨幅'],
                name=name_b,
                line=dict(color='#1890ff', width=2)
            ))

        fig.update_layout(
            title="日内涨幅走势叠加 (%)",
            hovermode="x unified",
            template="plotly_white"
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")

        return fig

    @staticmethod
    def create_comparison_flow_chart(
        df_a: pd.DataFrame,
        df_b: pd.DataFrame,
        name_a: str,
        name_b: str
    ) -> go.Figure:
        """
        创建累计资金净流入对比图（双轴）
        """
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        if {'时间', '累计净流入'}.issubset(df_a.columns):
            fig.add_trace(
                go.Scatter(
                    x=df_a['时间'],
                    y=df_a['累计净流入'],
                    name=f"{name_a} 资金流",
                    line=dict(color='#ff4d4f')
                ),
                secondary_y=False
            )

        if {'时间', '累计净流入'}.issubset(df_b.columns):
            fig.add_trace(
                go.Scatter(
                    x=df_b['时间'],
                    y=df_b['累计净流入'],
                    name=f"{name_b} 资金流",
                    line=dict(color='#1890ff', dash='dot')
                ),
                secondary_y=True
            )

        fig.update_layout(
            title="累计资金净流入对比 (双轴)",
            hovermode="x unified",
            template="plotly_white",
            legend=dict(orientation="h", y=1.1)
        )
        fig.update_yaxes(title_text=f"{name_a} (元)", secondary_y=False, title_font=dict(color="#ff4d4f"))
        fig.update_yaxes(title_text=f"{name_b} (元)", secondary_y=True, title_font=dict(color="#1890ff"))

        return fig
    
    @staticmethod
    def create_large_orders_scatter(large_orders: List[Dict], df: pd.DataFrame) -> go.Figure:
        """
        创建显著成交散点图（在价格图上标记成交峰值）
        """
        fig = go.Figure()
        
        # 价格线
        fig.add_trace(go.Scatter(
            x=df['时间'],
            y=df['收盘'],
            mode='lines',
            name='价格',
            line=dict(color='#1f2937', width=1.2),
            opacity=0.8
        ))
        
        # 显著成交散点
        if large_orders:
            buy_orders = [o for o in large_orders if o.get('type') == '买盘']
            sell_orders = [o for o in large_orders if o.get('type') == '卖盘']
            
            if buy_orders:
                fig.add_trace(go.Scatter(
                    x=[o['time'] for o in buy_orders],
                    y=[o['price'] for o in buy_orders],
                    mode='markers',
                    name='显著买成交',
                    marker=dict(
                        color='#ff4d4f',
                        size=[min(o['ratio'] * 5, 30) for o in buy_orders],
                        symbol='triangle-up',
                        line=dict(width=1, color='white')
                    ),
                    text=[f"¥{o['amount']:,.0f}<br>{o['ratio']:.1f}x平均" for o in buy_orders],
                    hovertemplate='%{text}<extra></extra>'
                ))
            
            if sell_orders:
                fig.add_trace(go.Scatter(
                    x=[o['time'] for o in sell_orders],
                    y=[o['price'] for o in sell_orders],
                    mode='markers',
                    name='显著卖成交',
                    marker=dict(
                        color='#52c41a',
                        size=[min(o['ratio'] * 5, 30) for o in sell_orders],
                        symbol='triangle-down',
                        line=dict(width=1, color='white')
                    ),
                    text=[f"¥{o['amount']:,.0f}<br>{o['ratio']:.1f}x平均" for o in sell_orders],
                    hovertemplate='%{text}<extra></extra>'
                ))
        
        fig.update_layout(
            title="显著成交追踪",
            height=400,
            hovermode='closest',
            template='plotly_white',
            showlegend=True
        )
        
        fig.update_xaxes(title_text="时间")
        fig.update_yaxes(title_text="价格 (¥)")
        
        return fig
    @staticmethod
    def create_cumulative_flow_chart(df: pd.DataFrame) -> go.Figure:
        """
        创建全天累计资金流曲线图 (A-1)
        
        Args:
            df: 包含'净流入额'和'累计净流入'的DataFrame
        """
        fig = go.Figure()

        y_col = '累计净流入_ema' if '累计净流入_ema' in df.columns else '累计净流入'
        
        # 填充区域颜色根据正负变化 (Plotly fill property limit, simplified here)
        # 简单处理：绿色填充如果<0，红色如果>0 (需要更复杂逻辑，这里简化为红色填充全部)
        # 用 Gradient 或者 color array 线
        
        fig.add_trace(go.Scatter(
            x=df['时间'],
            y=df[y_col],
            mode='lines',
            name='累计净流入(平滑)' if y_col != '累计净流入' else '累计净流入',
            line=dict(color='#ff4d4f', width=2),
            fill='tozeroy',
            fillcolor='rgba(255, 77, 79, 0.1)' # 浅红填充
        ))

        auction_marker = df.attrs.get("auction_marker")
        if auction_marker:
            fig.add_trace(go.Scatter(
                x=[auction_marker.get("time")],
                y=[auction_marker.get("value", 0)],
                mode="markers+text",
                text=["▲"],
                textposition="top center",
                marker=dict(color="#faad14", size=10),
                name="集合竞价"
            ))
        
        # 增加零轴
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        fig.update_layout(
            title="全天累计资金净流入趋势",
            height=350,
            hovermode='x unified',
            template='plotly_white',
            yaxis_title="累计净流入 (元)"
        )
        return fig

    @staticmethod
    def create_intraday_heatmap(df: pd.DataFrame, resample_minutes=10) -> go.Figure:
        """
        创建日内分时资金流热力图 (专业版 - 资金流比率 + 市场阶段标注)
        
        Args:
            df: 包含'时间'和'净流入额'的DataFrame
            resample_minutes: 聚合时间窗口(分钟)，推荐10或15
        """
        try:
            # 步骤1: 时间处理
            df_copy = df.copy()
            
            # 确保时间列存在
            if '时间' not in df_copy.columns:
                raise ValueError("数据缺少'时间'列")
            
            # 时间列已经是 datetime64，直接使用
            df_copy = df_copy.set_index('时间')
            
            # 过滤交易时段 (9:30-11:30, 13:00-15:00)
            df_trading = pd.concat([
                df_copy.between_time('09:30', '11:30'),
                df_copy.between_time('13:00', '15:00')
            ])
            
            # 步骤2 & 3: 时间窗口聚合 (关键！)
            # 创建时间窗口（floor到最近的N分钟）
            df_trading['时间窗口'] = df_trading.index.floor(f'{resample_minutes}min')
            
            # 聚合计算
            heatmap_data = df_trading.groupby('时间窗口').agg({
                '净流入额': 'sum',      # 净流入总额
                '成交额(元)': 'sum'     # 成交活跃度
            }).reset_index()
            
            # 步骤4: 计算资金流比率（归一化，可比性强）
            heatmap_data['资金流比率'] = heatmap_data['净流入额'] / heatmap_data['成交额(元)'].replace(0, 1)

            # 格式化时段标签
            heatmap_data['时段'] = heatmap_data['时间窗口'].dt.strftime('%H:%M')

            close_marker = df.attrs.get("close_auction_marker")
            close_label = None
            if close_marker and close_marker.get("time"):
                marker_time = pd.to_datetime(close_marker.get("time"), errors="coerce")
                if pd.notna(marker_time):
                    time_window = marker_time.floor(f"{resample_minutes}min")
                    close_label = time_window.strftime("%H:%M")
                    if close_label not in heatmap_data["时段"].values:
                        net_inflow = close_marker.get("net_inflow", 0.0) or 0.0
                        turnover = close_marker.get("turnover", 0.0) or 0.0
                        ratio = net_inflow / (turnover if turnover else 1)
                        extra_row = {
                            "时间窗口": time_window,
                            "净流入额": net_inflow,
                            "成交额(元)": turnover,
                            "资金流比率": ratio,
                            "时段": close_label,
                        }
                        heatmap_data = pd.concat(
                            [heatmap_data, pd.DataFrame([extra_row])],
                            ignore_index=True,
                        ).sort_values("时间窗口")
            
            # 步骤5: 绘制专业热力图（使用go.Heatmap）
            # 计算合理的色阶范围（使用95分位数避免极值）
            ratio_95 = heatmap_data['资金流比率'].abs().quantile(0.95)
            color_range = [-ratio_95, ratio_95]
            
            fig = go.Figure()
            
            # 🔍 修正极端值（100%通常是除以0导致的）
            heatmap_data['资金流比率_显示'] = heatmap_data['资金流比率'].clip(-0.95, 0.95)  # 限制在±95%
            
            # 计算色阶范围
            ratio_95 = heatmap_data['资金流比率_显示'].abs().quantile(0.95)
            color_range = [-ratio_95, ratio_95]
            
            # 使用柱状图，但用颜色表示强度（热力图风格的柱状图）
            fig.add_trace(go.Bar(
                x=heatmap_data['时段'],
                y=heatmap_data['资金流比率_显示'] * 100,  # 转为百分比
                marker=dict(
                    color=heatmap_data['资金流比率_显示'] * 100,
                    colorscale='RdBu_r',  # 红(流入)-白-蓝(流出)
                    cmin=color_range[0] * 100,
                    cmax=color_range[1] * 100,
                    cmid=0,
                    colorbar=dict(
                        title="流入比率(%)",
                        tickformat=".1f",
                        len=0.7
                    ),
                    line=dict(width=0)  # 去掉边框
                ),
                customdata=np.column_stack((
                    heatmap_data['净流入额'],
                    heatmap_data['成交额(元)'],
                    heatmap_data['资金流比率'] * 100  # 原始值
                )),
                hovertemplate="<br>".join([
                    "<b>%{x}</b>",
                    "资金流比率: %{customdata[2]:.2f}%",
                    "净流入: ¥%{customdata[0]:,.0f}",
                    "区间成交额: ¥%{customdata[1]:,.0f}",
                    "<extra></extra>"
                ])
            ))

            if close_label:
                fig.add_annotation(
                    x=close_label,
                    y=0,
                    text="集合竞价",
                    showarrow=True,
                    arrowhead=2,
                    ax=0,
                    ay=-30,
                    font=dict(color="#faad14", size=10),
                )
            
            # 调整布局
            fig.update_layout(
                title=f"日内资金流热力 ({resample_minutes}分钟窗口, 色彩归一化)",
                height=300,
                template='plotly_white',
                yaxis_title="资金流比率 (%)",
                xaxis_title="交易时段",
                yaxis_tickformat=".1f",
                bargap=0.05,
                showlegend=False
            )
            
            # 零线参考
            fig.add_hline(y=0, line_dash="solid", line_color="black", line_width=1, opacity=0.3)
            
            return fig
            
        except Exception as e:
            import traceback
            print(f"热力图生成失败: {e}")
            print("完整错误堆栈:")
            traceback.print_exc()
            # Fallback: 简化版
            colors = ['#ff4d4f' if v > 0 else '#52c41a' for v in df.get('净流入额', [])]
            fig = go.Figure(go.Bar(
                x=df.get('时间', []), 
                y=df.get('净流入额', []), 
                marker_color=colors
            ))
            fig.update_layout(title="日内资金流(Fallback)", height=350)
            return fig

    @staticmethod
    def create_stacked_area_flow(df: pd.DataFrame, flow_data: dict, resample_minutes=30) -> go.Figure:
        """
        创建买/卖盘净流构成堆叠面积图

        Args:
            df: 包含逐笔数据的DataFrame
            flow_data: 资金流向汇总数据（用于fallback）
            resample_minutes: 聚合窗口(分钟)
        """
        try:
            df_copy = df.copy()

            amount_col = None
            if "成交额(元)" in df_copy.columns:
                amount_col = "成交额(元)"
            elif "成交额" in df_copy.columns:
                amount_col = "成交额"
            elif "amount" in df_copy.columns:
                amount_col = "amount"

            if {"时间", "buy_amount", "sell_amount"}.issubset(df_copy.columns):
                df_copy["买盘净流入"] = pd.to_numeric(
                    df_copy["buy_amount"], errors="coerce"
                ).fillna(0.0)
                df_copy["卖盘净流出"] = -pd.to_numeric(
                    df_copy["sell_amount"], errors="coerce"
                ).fillna(0.0)
            else:
                if amount_col is None or "性质" not in df_copy.columns:
                    raise KeyError("missing required tick columns")

                amt = pd.to_numeric(df_copy[amount_col], errors="coerce").fillna(0.0)
                nature = df_copy["性质"].astype(str)
                buy_mask = nature.str.contains("买")
                sell_mask = nature.str.contains("卖")

                df_copy["买盘净流入"] = 0.0
                df_copy["卖盘净流出"] = 0.0
                df_copy.loc[buy_mask, "买盘净流入"] = amt[buy_mask]
                df_copy.loc[sell_mask, "卖盘净流出"] = -amt[sell_mask]

            df_copy["时间"] = pd.to_datetime(
                df_copy["时间"], format="%H:%M:%S", errors="coerce"
            )
            df_copy = df_copy.dropna(subset=["时间"])

            base_date = pd.Timestamp("2026-01-01")
            df_copy["datetime"] = df_copy["时间"].apply(
                lambda x: base_date
                + pd.Timedelta(hours=x.hour, minutes=x.minute, seconds=x.second)
            )
            df_copy = df_copy.set_index("datetime")

            flow_agg = df_copy[["买盘净流入", "卖盘净流出"]].resample(
                f"{resample_minutes}min"
            ).sum()
            flow_agg = flow_agg.reset_index()
            flow_agg["时段"] = flow_agg["datetime"].dt.strftime("%H:%M")
            flow_agg["总计净流入"] = flow_agg["买盘净流入"] + flow_agg["卖盘净流出"]

            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=flow_agg["时段"],
                    y=flow_agg["买盘净流入"],
                    mode="none",
                    fill="tozeroy",
                    name="买盘净流入",
                    fillcolor="rgba(255, 77, 79, 0.6)",
                    hovertemplate="买盘净流入: ¥%{y:,.0f}<extra></extra>",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=flow_agg["时段"],
                    y=flow_agg["卖盘净流出"],
                    mode="none",
                    fill="tozeroy",
                    name="卖盘净流出",
                    fillcolor="rgba(82, 196, 26, 0.6)",
                    hovertemplate="卖盘净流出: ¥%{y:,.0f}<extra></extra>",
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=flow_agg["时段"],
                    y=flow_agg["总计净流入"],
                    mode="lines",
                    line=dict(color="#1890ff", width=2, dash="dash"),
                    name="总计净流入",
                    hovertemplate="总计净流入: ¥%{y:,.0f}<extra></extra>",
                )
            )

            max_abs = flow_agg["总计净流入"].abs().max() if not flow_agg.empty else 0
            if max_abs > 0:
                max_idx = flow_agg["总计净流入"].abs().idxmax()
                max_row = flow_agg.loc[max_idx]
                if max_row["总计净流入"] > 0:
                    annotation_text = "⬆️ 净流入峰值"
                    arrow_color = "#ff4d4f"
                else:
                    annotation_text = "⬇️ 净流出峰值"
                    arrow_color = "#52c41a"

                fig.add_annotation(
                    x=max_row["时段"],
                    y=max_row["总计净流入"],
                    text=annotation_text,
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=2,
                    arrowcolor=arrow_color,
                    ax=0,
                    ay=-60,
                    bgcolor="white",
                    bordercolor=arrow_color,
                    borderwidth=2,
                    font=dict(size=10, color=arrow_color),
                )

            y_min = min(
                flow_agg[["买盘净流入", "卖盘净流出", "总计净流入"]].min().min(), 0
            )
            y_max = max(
                flow_agg[["买盘净流入", "卖盘净流出", "总计净流入"]].max().max(), 0
            )
            y_range_padding = max((y_max - y_min) * 0.1, 1)
            y_axis_range = [y_min - y_range_padding, y_max + y_range_padding]

            fig.update_layout(
                title=f"买卖盘净流构成 ({resample_minutes}分钟)",
                height=400,
                template="plotly_white",
                yaxis_title="净流入 (元)",
                yaxis_range=y_axis_range,
                xaxis_title="时段",
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )

            fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

            return fig

        except Exception as e:
            print(f"堆叠面积图生成失败: {e}")
            buy_amount = flow_data.get("buy_amount")
            sell_amount = flow_data.get("sell_amount")
            if buy_amount is None:
                buy_amount = flow_data.get("large_buy_amount", 0) + flow_data.get(
                    "retail_buy_amount", 0
                )
            if sell_amount is None:
                sell_amount = flow_data.get("large_sell_amount", 0) + flow_data.get(
                    "retail_sell_amount", 0
                )
            net_inflow = flow_data.get("net_inflow", buy_amount - sell_amount)
            fig = go.Figure(
                go.Waterfall(
                    name="资金流向",
                    x=["买盘", "卖盘", "总计"],
                    y=[buy_amount, -sell_amount, net_inflow],
                    measure=["relative", "relative", "total"],
                    increasing={"marker": {"color": "#ff4d4f"}},
                    decreasing={"marker": {"color": "#52c41a"}},
                )
            )
            fig.update_layout(title="资金流向(Fallback)", height=400)
            return fig
