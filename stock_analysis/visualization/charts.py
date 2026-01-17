"""
可视化图表生成函数
使用 Plotly 创建交互式图表
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
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
    def create_large_orders_scatter(large_orders: List[Dict], df: pd.DataFrame) -> go.Figure:
        """
        创建大单散点图（在价格图上标记大单）
        """
        fig = go.Figure()
        
        # 价格线
        fig.add_trace(go.Scatter(
            x=df['时间'],
            y=df['收盘'],
            mode='lines',
            name='价格',
            line=dict(color='lightgray', width=1),
            opacity=0.5
        ))
        
        # 大单散点
        if large_orders:
            buy_orders = [o for o in large_orders if o.get('type') == '买盘']
            sell_orders = [o for o in large_orders if o.get('type') == '卖盘']
            
            if buy_orders:
                fig.add_trace(go.Scatter(
                    x=[o['time'] for o in buy_orders],
                    y=[o['price'] for o in buy_orders],
                    mode='markers',
                    name='大买单',
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
                    name='大卖单',
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
            title="大单追踪",
            height=400,
            hovermode='closest',
            template='plotly_white',
            showlegend=True
        )
        
        fig.update_xaxes(title_text="时间")
        fig.update_yaxes(title_text="价格 (¥)")
        
        return fig
