"""
分时走势分析器
分析股票的分时价格和成交量走势
"""
import pandas as pd
from typing import Dict

class TimeSeriesAnalyzer:
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        分析分时走势数据
        
        Returns:
            包含各项分时指标的字典
        """
        if df.empty:
            return {}
        
        result = {}
        
        # 基础价格指标
        result['open_price'] = float(df.iloc[0]['开盘'])
        result['close_price'] = float(df.iloc[-1]['收盘'])
        result['high_price'] = float(df['最高'].max())
        result['low_price'] = float(df['最低'].min())
        
        # 涨跌数据
        result['price_change'] = result['close_price'] - result['open_price']
        result['price_change_pct'] = (result['price_change'] / result['open_price']) * 100
        
        # 振幅
        result['amplitude'] = ((result['high_price'] - result['low_price']) / result['open_price']) * 100
        
        # 成交数据
        result['volume_total'] = int(df['成交量'].sum())
        result['turnover_total'] = float(df['成交额(元)'].sum())
        result['avg_price'] = float(df['均价'].mean()) if '均价' in df.columns else result['turnover_total'] / result['volume_total'] if result['volume_total'] > 0 else 0
        
        # 成交活跃度 (平均每分钟成交量)
        result['avg_volume_per_minute'] = result['volume_total'] / len(df)
        
        # 分时统计
        result['total_minutes'] = len(df)
        result['rising_minutes'] = int((df['收盘'] > df['开盘']).sum())
        result['falling_minutes'] = int((df['收盘'] < df['开盘']).sum())
        result['flat_minutes'] = result['total_minutes'] - result['rising_minutes'] - result['falling_minutes']
        
        # 涨跌比例
        result['rising_ratio'] = result['rising_minutes'] / result['total_minutes'] * 100
        
        return result

def format_timeseries_summary(analysis: Dict) -> str:
    """生成分时走势摘要文本"""
    if not analysis:
        return "暂无数据"
    
    change_symbol = "📈" if analysis['price_change'] >= 0 else "📉"
    
    summary = f"""
    分时走势分析 {change_symbol}
    ━━━━━━━━━━━━━━━━━━━━
    开盘价: ¥{analysis['open_price']:.2f}
    收盘价: ¥{analysis['close_price']:.2f}
    最高价: ¥{analysis['high_price']:.2f}
    最低价: ¥{analysis['low_price']:.2f}
    
    涨跌幅: {analysis['price_change_pct']:+.2f}%
    振  幅: {analysis['amplitude']:.2f}%
    
    总成交量: {analysis['volume_total']:,} 手
    总成交额: ¥{analysis['turnover_total']:,.0f}
    均  价: ¥{analysis['avg_price']:.2f}
    
    上涨分钟: {analysis['rising_minutes']} ({analysis['rising_ratio']:.1f}%)
    下跌分钟: {analysis['falling_minutes']}
    """
    return summary.strip()
