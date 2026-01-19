"""
买卖盘强度分析器
分析买卖盘力量对比和强度变化
"""
import pandas as pd
from typing import Dict

class OrderStrengthAnalyzer:
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        分析买卖盘强度
        
        Returns:
            包含买卖盘强度指标的字典
        """
        if df.empty or '性质' not in df.columns:
            return {}
        
        result = {}
        
        # 统计买卖盘数量
        buy_orders = df[df['性质'] == '买盘']
        sell_orders = df[df['性质'] == '卖盘']
        neutral_orders = df[df['性质'] == '中性盘']
        
        result['buy_count'] = len(buy_orders)
        result['sell_count'] = len(sell_orders)
        result['neutral_count'] = len(neutral_orders)
        
        # 买卖盘成交额
        result['buy_turnover'] = float(buy_orders['成交额(元)'].sum())
        result['sell_turnover'] = float(sell_orders['成交额(元)'].sum())
        result['neutral_turnover'] = float(neutral_orders['成交额(元)'].sum())
        
        # 买卖盘比例
        total_count = len(df)
        result['buy_ratio'] = (result['buy_count'] / total_count * 100) if total_count > 0 else 0
        result['sell_ratio'] = (result['sell_count'] / total_count * 100) if total_count > 0 else 0
        
        # 买卖盘力度 (成交额比例)
        total_turnover = result['buy_turnover'] + result['sell_turnover']
        if total_turnover > 0:
            result['buy_strength'] = result['buy_turnover'] / total_turnover * 100
            result['sell_strength'] = result['sell_turnover'] / total_turnover * 100
        else:
            result['buy_strength'] = 50.0
            result['sell_strength'] = 50.0
        
        # 净买入强度 (类似 RSI 的概念)
        result['net_buy_strength'] = result['buy_strength'] - 50  # -50 到 +50
        
        # 平均单笔成交额
        result['avg_buy_amount'] = result['buy_turnover'] / result['buy_count'] if result['buy_count'] > 0 else 0
        result['avg_sell_amount'] = result['sell_turnover'] / result['sell_count'] if result['sell_count'] > 0 else 0
        
        # 判断优势方
        if result['buy_strength'] > result['sell_strength'] + 5:
            result['advantage'] = '买盘占优'
            result['advantage_emoji'] = '🟢'
        elif result['sell_strength'] > result['buy_strength'] + 5:
            result['advantage'] = '卖盘占优'
            result['advantage_emoji'] = '🔴'
        else:
            result['advantage'] = '势均力敌'
            result['advantage_emoji'] = '🟡'
        
        return result
    
    def get_minutely_strength(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        获取每分钟的买卖盘强度时序数据
        用于绘制买卖盘力度随时间变化的图表
        """
        if df.empty or '时间' not in df.columns or '性质' not in df.columns:
            return pd.DataFrame()
        if '成交额(元)' not in df.columns:
            return pd.DataFrame()
        
        result_df = df.copy()
        
        # 为每一行计算买卖盘标记
        result_df['买盘额'] = result_df.apply(
            lambda x: x['成交额(元)'] if x['性质'] == '买盘' else 0, axis=1
        )
        result_df['卖盘额'] = result_df.apply(
            lambda x: x['成交额(元)'] if x['性质'] == '卖盘' else 0, axis=1
        )
        
        return result_df[['时间', '买盘额', '卖盘额']]

def format_strength_summary(analysis: Dict) -> str:
    """生成买卖盘强度摘要"""
    if not analysis:
        return "暂无数据"
    
    summary = f"""
    买卖盘强度分析 {analysis.get('advantage_emoji', '')}
    ━━━━━━━━━━━━━━━━━━━━
    {analysis.get('advantage', '未知')}
    
    买盘笔数: {analysis['buy_count']} ({analysis['buy_ratio']:.1f}%)
    卖盘笔数: {analysis['sell_count']} ({analysis['sell_ratio']:.1f}%)
    
    买盘成交额: ¥{analysis['buy_turnover']:,.0f}
    卖盘成交额: ¥{analysis['sell_turnover']:,.0f}
    
    买盘强度: {analysis['buy_strength']:.1f}%
    卖盘强度: {analysis['sell_strength']:.1f}%
    
    平均买单: ¥{analysis['avg_buy_amount']:,.0f}
    平均卖单: ¥{analysis['avg_sell_amount']:,.0f}
    """
    return summary.strip()
