"""
股票新闻获取器
获取个股相关新闻和公告
"""
import akshare as ak
import pandas as pd
from typing import List, Dict

class StockNewsProvider:
    """股票新闻提供者"""
    
    @staticmethod
    def get_stock_news(stock_code: str, limit=10) -> pd.DataFrame:
        """
        获取个股新闻
        
        Args:
            stock_code: 股票代码
            limit: 返回新闻数量
            
        Returns:
            DataFrame包含新闻列表
        """
        try:
            df = ak.stock_news_em(symbol=stock_code)
            if not df.empty and len(df) > limit:
                df = df.head(limit)
            return df
        except Exception as e:
            print(f"获取股票新闻失败 ({stock_code}): {e}")
            return pd.DataFrame()
    
    @staticmethod
    def get_market_news(limit=20) -> pd.DataFrame:
        """
        获取市场要闻 (使用新浪直连 API 替代 AkShare 以提升速度)
        
        Args:
            limit: 返回新闻数量
            
        Returns:
            DataFrame: 包含新闻列表, columns=['发布时间', '新闻标题', '新闻内容']
        """
        try:
            import requests
            import time
            from datetime import datetime
            
            # 新浪财经滚动新闻 API (直连)
            # pageid=153 (个股), lid=2509 (全部)
            sina_url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&k=&num={}&page=1".format(limit)
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            resp = requests.get(sina_url, headers=headers, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('result', {}).get('data', [])
                
                news_list = []
                for item in items:
                    # 转换时间戳
                    ctime = item.get('ctime', '')
                    try:
                        time_str = datetime.fromtimestamp(int(ctime)).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        time_str = str(ctime)
                        
                    news_list.append({
                        '发布时间': time_str,
                        '新闻标题': item.get('title', ''),
                        '新闻内容': item.get('intro', '') or item.get('title', '') # Intro is summary
                    })
                
                return pd.DataFrame(news_list)
            else:
                print(f"Sina API status: {resp.status_code}")
                # Fallback to AkShare if direct fail
                df = ak.stock_news_em(symbol="全部")
                if not df.empty and len(df) > limit:
                    df = df.head(limit)
                return df
                
        except Exception as e:
            print(f"获取市场新闻失败 (Direct): {e}")
            # Fallback
            try:
                df = ak.stock_news_em(symbol="全部")
                return df.head(limit) if not df.empty else pd.DataFrame()
            except:
                return pd.DataFrame()
    
    @staticmethod
    def format_news_item(news_row) -> str:
        """
        格式化单条新闻为可读文本
        
        Args:
            news_row: 新闻行数据
            
        Returns:
            格式化后的新闻文本
        """
        try:
            title = news_row.get('新闻标题', 'N/A')
            time = news_row.get('发布时间', 'N/A')
            content = news_row.get('新闻内容', '')
            
            # 截取内容前100字
            if content and len(content) > 100:
                content = content[:100] + '...'
            
            formatted = f"**[{time}] {title}**"
            if content:
                formatted += f"\n{content}"
            
            return formatted
        except Exception as e:
            return "新闻格式化失败"
    
    @staticmethod
    def get_news_summary(news_df: pd.DataFrame) -> Dict:
        """
        生成新闻摘要统计
        
        Args:
            news_df: 新闻DataFrame
            
        Returns:
            新闻统计信息
        """
        if news_df.empty:
            return {
                'total_count': 0,
                'latest_time': None,
                'has_news': False
            }
        
        return {
            'total_count': len(news_df),
            'latest_time': news_df.iloc[0]['发布时间'] if '发布时间' in news_df.columns else None,
            'has_news': True,
            'titles': news_df['新闻标题'].head(5).tolist() if '新闻标题' in news_df.columns else []
        }


def format_news_summary(news_df: pd.DataFrame, stock_name: str = "") -> str:
    """生成新闻摘要文本"""
    if news_df.empty:
        return f"{stock_name} 暂无最新新闻"
    
    summary = f"""
    {stock_name} 相关新闻 📰
    ━━━━━━━━━━━━━━━━━━━━
    最新 {len(news_df)} 条:
    """
    
    for idx, row in news_df.head(5).iterrows():
        time = row.get('发布时间', 'N/A')
        title = row.get('新闻标题', 'N/A')
        summary += f"\n    [{time}] {title}"
    
    return summary.strip()
