import tushare as ts
import pandas as pd
from datetime import date, datetime
from typing import Optional
from .base import StockDataProvider
from stock_analysis.core.config import settings

class TushareProvider(StockDataProvider):
    def __init__(self):
        if not settings.TUSHARE_TOKEN:
            raise ValueError("Tushare Token 未配置！请设置环境变量 TUSHARE_TOKEN 或在启动界面输入")
        ts.set_token(settings.TUSHARE_TOKEN)
        self.pro = ts.pro_api()
    
    def _normalize_code(self, code: str) -> str:
        """Convert code to Tushare format: 300661 -> 300661.SZ"""
        if code.startswith('6'):
            return f"{code}.SH"
        else:
            return f"{code}.SZ"
    
    def get_stock_info(self, code: str) -> dict:
        try:
            ts_code = self._normalize_code(code)
            df = self.pro.stock_basic(ts_code=ts_code, fields='ts_code,name,industry')
            if not df.empty:
                return {"code": code, "name": df.iloc[0]['name'], "industry": df.iloc[0].get('industry', '')}
        except:
            pass
        return {"code": code, "name": "Unknown"}
    
    def get_realtime_data(self, code: str) -> pd.DataFrame:
        """Alias for today's data"""
        today = date.today().strftime("%Y%m%d")
        return self.get_tick_data(code, today)
    
    def get_tick_data(self, code: str, date_str: str = None) -> pd.DataFrame:
        """
        获取分钟级数据（Tushare 免费账户不支持 tick，使用1分钟代替）
        """
        if not date_str:
            date_str = date.today().strftime("%Y%m%d")
        
        try:
            ts_code = self._normalize_code(code)
            
            # Tushare 日期格式：20260115
            # 时间范围：09:30-15:00
            print(f"📥 Fetching 1-min data from Tushare for {ts_code} on {date_str}...")
            
            # stk_mins: 获取股票分钟数据
            # freq: 1min, 5min, 15min, 30min, 60min
            df = ts.pro_bar(ts_code=ts_code, 
                           freq='1min', 
                           start_date=date_str,
                           end_date=date_str,
                           adj='qfq')  # 前复权
            
            if df is None or df.empty:
                print(f"⚠️ No data for {date_str}, trying to fetch last trading day...")
                return self._get_last_trading_day_data(code)
            
            # Tushare 列名：trade_time, open, high, low, close, vol, amount
            # 需要转换为我们的标准格式
            df = self._normalize_tushare_data(df)
            
            print(f"✅ Successfully fetched {len(df)} records from Tushare")
            return df
            
        except Exception as e:
            print(f"❌ Tushare fetch failed: {e}")
            return pd.DataFrame()
    
    def _normalize_tushare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """将 Tushare 数据转换为标准格式"""
        # Tushare 返回的是倒序，需要正序
        df = df.sort_values('trade_time').reset_index(drop=True)
        
        # 重命名列以匹配 FlowAnalyzer 期望
        df = df.rename(columns={
            'trade_time': '时间',
            'open': '开盘',
            'close': '收盘',
            'high': '最高',
            'low': '最低',
            'vol': '成交量',
            'amount': '成交额'
        })
        
        # 成交额单位转换（Tushare 是千元，转为元）
        df['成交额(元)'] = df['成交额'] * 1000
        
        # 模拟买卖盘性质（基于价格动量）
        df['price_change'] = df['收盘'].diff().fillna(0)
        
        def get_type(change):
            if change > 0: return '买盘'
            if change < 0: return '卖盘'
            return '中性盘'
        
        df['性质'] = df['price_change'].apply(get_type)
        
        return df
    
    def _get_last_trading_day_data(self, code: str) -> pd.DataFrame:
        """获取最近交易日数据"""
        try:
            ts_code = self._normalize_code(code)
            # 获取最近10天的日K线，找到最后一个交易日
            df_daily = self.pro.daily(ts_code=ts_code, start_date='20230101')
            
            if df_daily.empty:
                return pd.DataFrame()
            
            last_date = df_daily.iloc[0]['trade_date']
            print(f"🔄 Fallback to last trading day: {last_date}")
            
            # 递归调用获取那天的分钟数据
            return self.get_tick_data(code, last_date)
            
        except Exception as e:
            print(f"Fallback failed: {e}")
            return pd.DataFrame()
    
    def get_history_data(self, code: str, start_date: date, end_date: date) -> pd.DataFrame:
        """获取日K数据"""
        try:
            ts_code = self._normalize_code(code)
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            
            df = self.pro.daily(ts_code=ts_code, start_date=start_str, end_date=end_str)
            return df
        except Exception as e:
            print(f"History data failed: {e}")
            return pd.DataFrame()
