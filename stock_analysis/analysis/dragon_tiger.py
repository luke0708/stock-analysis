"""
龙虎榜分析器
追踪主力资金进出、机构席位动向
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List

class DragonTigerAnalyzer:
    """龙虎榜分析器"""
    
    @staticmethod
    def get_recent_lhb(days=3) -> pd.DataFrame:
        """
        获取最近N天的龙虎榜数据 (EastMoney Direct API)
        
        Args:
            days: 获取最近几天的数据
            
        Returns:
            DataFrame包含龙虎榜记录
        """
        # 尝试使用直连 API 获取最近数据
        # 直连API通常只支持特定参数，这里模拟抓取最新一期
        try:
            import requests
            import time
            from datetime import datetime
            
            # EastMoney API (DataCenter)
            # URL: https://datacenter-web.eastmoney.com/api/data/v1/get
            # Params: reportName=RPT_DAILYBILLBOARD_DETAILS, columns=ALL, sortColumns=TRADE_DATE, -1 (desc)
            
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                "reportName": "RPT_DAILYBILLBOARD_DETAILS",
                "columns": "ALL",
                "source": "WEB",
                "sortColumns": "TRADE_DATE,SECURITY_CODE",
                "sortTypes": "-1,1",
                "pageSize": "50", # Fetch more
                "pageNumber": "1",
                "_": str(int(time.time()*1000))
            }
            # 如果指定了日期过滤，可以加 filter 参数，但这里获取最近N条更简单
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://data.eastmoney.com/"
            }
            
            resp = requests.get(url, params=params, headers=headers, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success'):
                    rows = data.get('result', {}).get('data', [])
                    
                    # Convert to DataFrame
                    df = pd.DataFrame(rows)
                    if not df.empty:
                        # 映射列名以匹配 AkShare 格式 (方便下游兼容)
                        # AkShare: 序号, 代码, 名称, 涨跌幅, 收盘价, 换手率, 龙虎榜净买额, 市场总成交额, 净买额占总成交比, 成交额, 流通市值, 上榜原因, 上榜日
                        # API: SECURITY_CODE, SECURITY_NAME_ABBR, CHANGE_RATE, CLOSE_PRICE, TURNOVERRATE, NET_BUY_AMT, AMOUNT, EXPLANATION, TRADE_DATE
                        
                        rename_map = {
                            'SECURITY_CODE': '代码',
                            'SECURITY_NAME_ABBR': '名称',
                            'CHANGE_RATE': '涨跌幅',
                            'CLOSE_PRICE': '收盘价',
                            'NET_BUY_AMT': '净买额', # AkShare uses '龙虎榜净买额'? Let's check.
                            'AMOUNT': '成交额',
                            'EXPLANATION': '上榜原因',
                            'TRADE_DATE': '上榜日',
                            # 补充字段
                            'BUY_AMT': '买入额',
                            'SELL_AMT': '卖出额'
                        }
                        df = df.rename(columns=rename_map)
                        # 格式化日期
                        df['上榜日'] = pd.to_datetime(df['上榜日']).dt.strftime('%Y-%m-%d')
                        
                        # 过滤最近几天
                        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                        df = df[df['上榜日'] >= cutoff_date]
                        
                        return df
            
            # Fallback
            return DragonTigerAnalyzer._fetch_akshare_lhb(days)
        except Exception as e:
            print(f"Direct LHB API failed: {e}")
            return DragonTigerAnalyzer._fetch_akshare_lhb(days)

    @staticmethod
    def _fetch_akshare_lhb(days):
        """Fallback to AkShare"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            return ak.stock_lhb_detail_em(start_date=start_str, end_date=end_str)
        except:
            return pd.DataFrame()
    
    @staticmethod
    def get_lhb_statistics(df: pd.DataFrame) -> Dict:
        """
        统计龙虎榜数据
        
        Args:
            df: 龙虎榜DataFrame
            
        Returns:
            统计信息字典
        """
        if df.empty:
            return {}
        
        try:
            stats = {
                'total_records': len(df),
                'unique_stocks': df['名称'].nunique() if '名称' in df.columns else 0,
                'buy_amount_total': df['买入额'].sum() if '买入额' in df.columns else 0,
                'sell_amount_total': df['卖出额'].sum() if '卖出额' in df.columns else 0,
            }
            
            # 计算净买入
            if '买入额' in df.columns and '卖出额' in df.columns:
                stats['net_buy'] = stats['buy_amount_total'] - stats['sell_amount_total']
            
            # 上榜原因统计
            if '上榜原因' in df.columns:
                reason_counts = df['上榜原因'].value_counts().head(5).to_dict()
                stats['top_reasons'] = reason_counts
            
            return stats
        except Exception as e:
            print(f"统计龙虎榜失败: {e}")
            return {}
    
    @staticmethod
    def get_stock_lhb_history(stock_code: str) -> pd.DataFrame:
        """
        获取个股历史龙虎榜记录
        
        Args:
            stock_code: 股票代码
            
        Returns:
            该股票的龙虎榜历史
        """
        try:
            # 获取最近30天的数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            
            df_all = ak.stock_lhb_detail_em(start_date=start_str, end_date=end_str)
            
            if df_all.empty:
                return pd.DataFrame()
            
            # 筛选该股票
            if '代码' in df_all.columns:
                df_stock = df_all[df_all['代码'] == stock_code]
                return df_stock
            
            return pd.DataFrame()
        except Exception as e:
            print(f"获取个股龙虎榜失败: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def analyze_institution_activity(df: pd.DataFrame) -> Dict:
        """
        分析机构活动
        
        Args:
            df: 龙虎榜DataFrame
            
        Returns:
            机构活动分析
        """
        if df.empty or '营业部名称' not in df.columns:
            return {}
        
        try:
            # 识别机构席位（包含"机构专用"）
            institution_df = df[df['营业部名称'].str.contains('机构', na=False)]
            
            stats = {
                'institution_count': len(institution_df),
                'institution_buy': institution_df['买入额'].sum() if '买入额' in institution_df.columns else 0,
                'institution_sell': institution_df['卖出额'].sum() if '卖出额' in institution_df.columns else 0,
            }
            
            if stats['institution_buy'] > 0 and stats['institution_sell'] > 0:
                stats['institution_net'] = stats['institution_buy'] - stats['institution_sell']
                stats['institution_sentiment'] = '买入' if stats['institution_net'] > 0 else '卖出'
            
            return stats
        except Exception as e:
            print(f"分析机构活动失败: {e}")
            return {}


def format_lhb_summary(lhb_df: pd.DataFrame, stats: Dict) -> str:
    """生成龙虎榜摘要"""
    if lhb_df.empty:
        return "最近无龙虎榜数据"
    
    summary = f"""
    龙虎榜摘要 💰
    ━━━━━━━━━━━━━━━━━━━━
    统计周期: 最近3天
    上榜股票: {stats.get('unique_stocks', 0)} 只
    总记录数: {stats.get('total_records', 0)} 条
    
    资金流向:
    买入总额: ¥{stats.get('buy_amount_total', 0) / 1e8:.2f} 亿
    卖出总额: ¥{stats.get('sell_amount_total', 0) / 1e8:.2f} 亿
    净买入: ¥{stats.get('net_buy', 0) / 1e8:.2f} 亿
    """
    
    # 添加热门上榜原因
    if 'top_reasons' in stats and stats['top_reasons']:
        summary += "\n    热门上榜原因:\n"
        for reason, count in list(stats['top_reasons'].items())[:3]:
            summary += f"    - {reason}: {count}次\n"
    
    return summary.strip()
