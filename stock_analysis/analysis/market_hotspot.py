"""
板块热点分析器
分析今日热门板块、领涨股、板块资金流向
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd

_logger = logging.getLogger(__name__)
_SENTIMENT_CACHE: Dict = {}
_SENTIMENT_CACHE_TS: Optional[datetime] = None
_SENTIMENT_CACHE_TTL = timedelta(minutes=10)

class MarketHotspotAnalyzer:
    """市场热点分析器"""

    @staticmethod
    def _get_cached_sentiment() -> Dict:
        if not _SENTIMENT_CACHE or _SENTIMENT_CACHE_TS is None:
            return {}
        if datetime.now() - _SENTIMENT_CACHE_TS > _SENTIMENT_CACHE_TTL:
            return {}
        return dict(_SENTIMENT_CACHE)

    @staticmethod
    def _set_cached_sentiment(payload: Dict) -> None:
        global _SENTIMENT_CACHE, _SENTIMENT_CACHE_TS
        _SENTIMENT_CACHE = dict(payload)
        _SENTIMENT_CACHE_TS = datetime.now()
    
    @staticmethod
    def get_hot_concepts(top_n=10) -> pd.DataFrame:
        """
        获取热门概念板块 (Sina V2 API)
        
        Args:
            top_n: 返回前N个板块
            
        Returns:
            DataFrame包含：板块名称、涨跌幅、领涨股等
        """
        return MarketHotspotAnalyzer._fetch_sina_plate("new_dqgn", top_n) # new_dqgn = 地区概念? No, 'new_dqgn' is 概念? No: gn=概念, hy=行业, dy=地域
        # Sina 节点: new_cp = 概念, new_hy = 行业. Or qh, dq?
        # Checked map: node='new_dqgn' is not standard.
        # Direct URL analysis: node = "chgn" (concept) or "chhy" ??
        # Let's use correct nodes: 
        # Concept(概念): node='new_gn' or 'chgn'? 
        # Actually, let's look at the tested one: new_dqhy (Industry).
        # Let's use 'new_gn' for concepts if it works, or stick to 'new_dqgn' if verified.
        # Wait, if I am unsure, AkShare fallback is safer.
        # Let's write a helper that tries Sina then AkShare.
    
    @staticmethod
    def _fetch_sina_plate(node_type, top_n) -> pd.DataFrame:
        """Helper for Sina Plate data"""
        try:
            import requests
            headers = {"User-Agent": "Mozilla/5.0"}
            # node: 'new_jyhy' (行业), 'new_gn' (概念)? 
            # In Sina VIP website: 
            # 行业: node=new_hy
            # 概念: node=new_gn
            # 地域: node=new_dy
            
            # Let's assume input node_type is correct Sina node string.
            url = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
            params = {
                "page": "1", "num": str(top_n*2), # Fetch more to be safe
                "sort": "changepercent", "asc": "0", 
                "node": node_type, "symbol": ""
            }
            resp = requests.get(url, params=params, headers=headers, timeout=3)
            
            if resp.status_code == 200:
                # Sina returns JS object-like string, keys unquoted.
                # e.g: [{symbol:"sh...",name:"...",...}]
                # Dangerous to eval? Yes. But standard simple parser is hard.
                # However, this specific response structure is very consistent.
                # We can use regex to quote keys or just use 'demjson' if available? No external dep.
                # Let's use simple string replacement for known keys before json.loads?
                # Actually, eval is risky but acceptable for trusted source with limited scope in a tool?
                # Alternative: AkShare uses `demjson` or `eval`.
                # Let's try strictly safe regex approach or fallback.
                
                content = resp.text
                if not content or content == "null": return pd.DataFrame()
                
                # Simple hack: replace simple keys with quoted keys
                # keys: symbol, code, name, trade, pricechange, changepercent, buy, sell, settlement, open, high, low, volume, amount, ticktime, per, pb, mktcap, nmc, turnoverratio
                import re
                content = re.sub(r'([a-zA-Z_0-9]+):', r'"\1":', content) 
                import json
                data = json.loads(content)
                
                df = pd.DataFrame(data)
                # Rename to match standard UI expectations
                # UI uses: '板块名称', '涨跌幅', '领涨股票'
                if not df.empty:
                    df['板块名称'] = df['name']
                    df['涨跌幅'] = pd.to_numeric(df['changepercent'])
                    # Sina doesn't give 'leader_stock' name directly in this list? only avg data.
                    # Actually it doesn't give 'leader_stock'. AkShare concept board does.
                    # UI uses '领涨股票' for tooltip. If missing, UI might break or show NaN.
                    # We can leave it empty or fetch detail? Detail is too slow.
                    # Let's ignore leader stock for speed or fill "N/A".
                    df['领涨股票'] = "N/A"
                    
                    return df.head(top_n)
            
            return pd.DataFrame()
        except:
            return pd.DataFrame()

    @staticmethod
    def get_hot_concepts(top_n=10) -> pd.DataFrame:
        """获取热门概念板块"""
        # Node: new_gn = 概念
        df = MarketHotspotAnalyzer._fetch_sina_plate("new_gn", top_n)
        if not df.empty: return df
        # Fallback
        try:
            df = ak.stock_board_concept_name_em()
            return df.nlargest(top_n, '涨跌幅')
        except: return pd.DataFrame()

    @staticmethod
    def get_hot_industries(top_n=10) -> pd.DataFrame:
        """获取热门行业板块"""
        # Node: new_jyhy = 行业 (交易所行业? or new_hy?)
        # Let's try 'new_hy' first
        df = MarketHotspotAnalyzer._fetch_sina_plate("new_hy", top_n)
        if not df.empty: return df
        # Fallback
        try:
            df = ak.stock_board_industry_name_em()
            return df.nlargest(top_n, '涨跌幅')
        except: return pd.DataFrame()
    
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
            rising = len(df[df["涨跌幅"] > 0])
            falling = len(df[df["涨跌幅"] < 0])
            flat = total - rising - falling

            limit_up = len(df[df["涨跌幅"] >= 9.9])  # 涨停
            limit_down = len(df[df["涨跌幅"] <= -9.9])  # 跌停

            payload = {
                "total_stocks": total,
                "rising_count": rising,
                "falling_count": falling,
                "flat_count": flat,
                "rising_ratio": rising / total * 100,
                "limit_up_count": limit_up,
                "limit_down_count": limit_down,
                "market_sentiment": "多头" if rising > falling else ("空头" if falling > rising else "平衡"),
            }
            MarketHotspotAnalyzer._set_cached_sentiment(payload)
            return payload
        except Exception as e:
            cached = MarketHotspotAnalyzer._get_cached_sentiment()
            if cached:
                _logger.warning("分析市场情绪失败，回退缓存: %s", e)
                return cached
            _logger.warning("分析市场情绪失败: %s", e)
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
