"""
板块热点分析器
分析今日热门板块、领涨股、板块资金流向
"""
import akshare as ak
import pandas as pd
from typing import Dict, List

class MarketHotspotAnalyzer:
    """市场热点分析器"""
    
    @staticmethod
    def get_hot_concepts(top_n=10) -> pd.DataFrame:
        """
        获取热门概念板块
        
        Args:
            top_n: 返回前N个板块
            
        Returns:
            DataFrame包含：板块名称、涨跌幅、领涨股等
        """
        try:
            df = ak.stock_board_concept_name_em()
            # 按涨跌幅排序
            df_sorted = df.nlargest(top_n, '涨跌幅')
            return df_sorted
        except Exception as e:
            print(f"获取概念板块失败: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def get_hot_industries(top_n=10) -> pd.DataFrame:
        """
        获取热门行业板块
        
        Args:
            top_n: 返回前N个板块
            
        Returns:
            DataFrame包含：板块名称、涨跌幅、领涨股等
        """
        try:
            df = ak.stock_board_industry_name_em()
            # 按涨跌幅排序
            df_sorted = df.nlargest(top_n, '涨跌幅')
            return df_sorted
        except Exception as e:
            print(f"获取行业板块失败: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def get_concept_constituents(concept_name: str) -> pd.DataFrame:
        """
        获取概念板块的成分股
        
        Args:
            concept_name: 概念名称，如"锂电池"
            
        Returns:
            DataFrame包含成分股列表
        """
        try:
            df = ak.stock_board_concept_cons_em(symbol=concept_name)
            return df
        except Exception as e:
            print(f"获取概念成分股失败: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def get_industry_constituents(industry_name: str) -> pd.DataFrame:
        """
        获取行业板块的成分股
        
        Args:
            industry_name: 行业名称，如"半导体"
            
        Returns:
            DataFrame包含成分股列表
        """
        try:
            df = ak.stock_board_industry_cons_em(symbol=industry_name)
            return df
        except Exception as e:
            print(f"获取行业成分股失败: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def get_top_gainers(top_n=20) -> pd.DataFrame:
        """
        获取今日涨幅榜
        
        Args:
            top_n: 返回前N只股票
            
        Returns:
            DataFrame包含：代码、名称、涨跌幅等
        """
        try:
            df = ak.stock_zh_a_spot_em()
            # 过滤ST和北交所
            df_filtered = df[~df['名称'].str.contains('ST|N')]
            # 按涨跌幅排序
            top_gainers = df_filtered.nlargest(top_n, '涨跌幅')
            return top_gainers[['代码', '名称', '涨跌幅', '涨跌额', '最新价', '成交量', '成交额']]
        except Exception as e:
            print(f"获取涨幅榜失败: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def analyze_market_sentiment() -> Dict:
        """
        分析市场整体情绪
        
        Returns:
            包含市场统计数据的字典
        """
        try:
            df = ak.stock_zh_a_spot_em()
            
            total = len(df)
            rising = len(df[df['涨跌幅'] > 0])
            falling = len(df[df['涨跌幅'] < 0])
            flat = total - rising - falling
            
            limit_up = len(df[df['涨跌幅'] >= 9.9])  # 涨停
            limit_down = len(df[df['涨跌幅'] <= -9.9])  # 跌停
            
            return {
                'total_stocks': total,
                'rising_count': rising,
                'falling_count': falling,
                'flat_count': flat,
                'rising_ratio': rising / total * 100,
                'limit_up_count': limit_up,
                'limit_down_count': limit_down,
                'market_sentiment': '多头' if rising > falling else ('空头' if falling > rising else '平衡')
            }
        except Exception as e:
            print(f"分析市场情绪失败: {e}")
            return {}


def format_hotspot_summary(concepts: pd.DataFrame, industries: pd.DataFrame, sentiment: Dict) -> str:
    """生成热点摘要文本"""
    summary = f"""
    市场热点摘要 🔥
    ━━━━━━━━━━━━━━━━━━━━
    市场情绪: {sentiment.get('market_sentiment', '未知')}
    
    上涨/下跌: {sentiment.get('rising_count', 0)} / {sentiment.get('falling_count', 0)}
    涨停: {sentiment.get('limit_up_count', 0)} | 跌停: {sentiment.get('limit_down_count', 0)}
    
    🔥 最热概念:
    """
    
    if not concepts.empty:
        for idx, row in concepts.head(5).iterrows():
            summary += f"    {row['板块名称']}: {row['涨跌幅']:.2f}% (领涨：{row['领涨股票']})\n"
    
    summary += "\n    📊 最热行业:\n"
    if not industries.empty:
        for idx, row in industries.head(5).iterrows():
            summary += f"    {row['板块名称']}: {row['涨跌幅']:.2f}%\n"
    
    return summary.strip()
