import akshare as ak
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional
from .base import StockDataProvider

class AkShareProvider(StockDataProvider):
    def get_realtime_data(self, code: str) -> pd.DataFrame:
        """Alias for convenience, defaults to today"""
        today = date.today().strftime("%Y%m%d")
        return self.get_tick_data(code, today)

    def _normalize_tick_raw(self, df: pd.DataFrame, date_str: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df_copy = df.copy()
        col_map = {
            '成交时间': '时间',
            '时间': '时间',
            'time': '时间',
            '成交价格': '成交价格',
            '价格': '成交价格',
            '最新价': '成交价格',
            'price': '成交价格',
            '成交量': '成交量',
            'vol': '成交量',
            'volume': '成交量',
            '成交额': '成交额',
            '成交金额': '成交额',
            'amount': '成交额',
            '性质': '性质',
            'type': '性质',
            '买卖盘性质': '性质',
        }
        df_copy = df_copy.rename(columns=col_map)

        if '时间' not in df_copy.columns:
            return pd.DataFrame()

        time_series = df_copy['时间'].astype(str).str.strip()
        date_prefix = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        has_date = time_series.str.contains(r"\d{4}[-/]\d{2}[-/]\d{2}")
        time_full = time_series.where(has_date, date_prefix + " " + time_series)
        df_copy['时间'] = pd.to_datetime(time_full, errors='coerce')

        if '成交价格' in df_copy.columns:
            df_copy['成交价格'] = pd.to_numeric(df_copy['成交价格'], errors='coerce')
        if '成交量' in df_copy.columns:
            df_copy['成交量'] = pd.to_numeric(df_copy['成交量'], errors='coerce').fillna(0)
        if '成交额' in df_copy.columns:
            df_copy['成交额'] = pd.to_numeric(df_copy['成交额'], errors='coerce').fillna(0)

        if '成交价格' in df_copy.columns:
            df_copy = df_copy.dropna(subset=['时间', '成交价格'])
        else:
            df_copy = df_copy.dropna(subset=['时间'])
        if df_copy.empty:
            return pd.DataFrame()

        if '成交额' not in df_copy.columns:
            if '成交量' in df_copy.columns and '成交价格' in df_copy.columns:
                df_copy['成交额'] = df_copy['成交量'] * df_copy['成交价格']
            else:
                df_copy['成交额'] = 0

        return df_copy

    def _normalize_realtime_tick(self, df: pd.DataFrame, date_str: str) -> pd.DataFrame:
        tick_df = self._normalize_tick_raw(df, date_str)
        if tick_df.empty or '成交价格' not in tick_df.columns:
            return pd.DataFrame()

        tick_df['分钟'] = tick_df['时间'].dt.floor('min')
        grouped = tick_df.groupby('分钟', sort=True)

        minute_df = grouped['成交价格'].agg(['first', 'last', 'max', 'min'])
        minute_df = minute_df.rename(columns={
            'first': '开盘',
            'last': '收盘',
            'max': '最高',
            'min': '最低',
        })

        if '成交量' in tick_df.columns:
            minute_df['成交量'] = grouped['成交量'].sum()
        else:
            minute_df['成交量'] = 0
        minute_df['成交额'] = grouped['成交额'].sum()

        minute_df = minute_df.reset_index().rename(columns={'分钟': '时间'})
        minute_df['成交额(元)'] = minute_df['成交额']

        minute_df['price_change'] = minute_df['收盘'].diff().fillna(0)

        def get_type_from_momentum(change):
            if change > 0:
                return '买盘'
            if change < 0:
                return '卖盘'
            return '中性盘'

        minute_df['性质'] = minute_df['price_change'].apply(get_type_from_momentum)
        minute_df.attrs['actual_date'] = date_str
        minute_df.attrs['source_granularity'] = 'tick'
        minute_df.attrs['raw_tick'] = tick_df
        return minute_df

    def get_tick_data(self, code: str, date_str: str = None) -> pd.DataFrame:
        """
        Unified method to get tick data.
        :param code: Stock code (e.g. 300661)
        :param date_str: YYYYMMDD string. If None, defaults to today.
        """
        if not date_str:
            date_str = date.today().strftime("%Y%m%d")
            
        today_str = date.today().strftime("%Y%m%d")
        
        # 1. If date is today, try Realtime API first
        if date_str == today_str:
            try:
                print(f"Fetching Realtime Data for {code}...")
                prefix = "sh" if code.startswith("6") else "sz"
                symbol = f"{prefix}{code}"
                df = ak.stock_zh_a_tick_tx_js(symbol=symbol)

                if df is not None and not df.empty:
                    normalized_df = self._normalize_realtime_tick(df, date_str)
                    if not normalized_df.empty:
                        print(f"✅ Realtime tick converted to {len(normalized_df)} minute bars.")
                        return normalized_df
                    print("Realtime tick data lacks required fields after normalization.")
                else:
                    print("Realtime data empty (possibly before market or weekend).")
            except Exception as e:
                print(f"Realtime fetch failed: {e}")
        
        # 2. Fallback or Historical Request
        # If today_str != date_str OR realtime failed, we go here.
        # However, if it's today and realtime failed, we might want to find "Latest Valid Trading Day" 
        # But if the user EXPLICITLY asked for a date (date_str), we should honor it, even if empty.
        
        # If user didn't specify date (or passed today) and realtime failed, we try to find last trading day
        target_date = date_str
        if date_str == today_str:
            # Automagically find last trading day
            target_date = self._get_last_trading_day(code)
            if not target_date:
                return pd.DataFrame()
            print(f"Fallback: Switching target date to last trading day: {target_date}")
            
        df = self._fetch_historical_tick(code, target_date)
        if df.empty:
            fallback_date = self._get_last_trading_day_before(code, target_date)
            if fallback_date and fallback_date != target_date:
                print(f"Fallback: Switching target date to last trading day: {fallback_date}")
                df = self._fetch_historical_tick(code, fallback_date)
                if not df.empty:
                    df.attrs['requested_date'] = target_date
                    df.attrs['actual_date'] = fallback_date
                    df.attrs['fallback_reason'] = "previous_trading_day"
                    return df

            latest_date = self._get_last_trading_day(code)
            if latest_date and latest_date not in {target_date, fallback_date}:
                print(f"Fallback: Switching target date to latest trading day: {latest_date}")
                df_latest = self._fetch_historical_tick(code, latest_date)
                if not df_latest.empty:
                    df_latest.attrs['requested_date'] = target_date
                    df_latest.attrs['actual_date'] = latest_date
                    df_latest.attrs['fallback_reason'] = "latest_available"
                    return df_latest

            empty_df = pd.DataFrame()
            empty_df.attrs['requested_date'] = target_date
            empty_df.attrs['fallback_date'] = fallback_date
            empty_df.attrs['fallback_failed'] = True
            return empty_df
        return df

    def _get_last_trading_day(self, code: str) -> Optional[str]:
        try:
             # Fetch last 10 days daily bars to find the latest date
             daily_df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20230101", adjust="qfq")
             if daily_df.empty:
                 return None
             last_date = str(daily_df.iloc[-1]['日期']).replace("-", "").replace("/", "")
             return last_date
        except Exception as e:
            print(f"Error finding last trading day: {e}")
            return None

    def _get_last_trading_day_before(self, code: str, date_str: str) -> Optional[str]:
        try:
            target_date = datetime.strptime(date_str, "%Y%m%d").date()
            start_date = (target_date - timedelta(days=30)).strftime("%Y%m%d")
            end_date = target_date.strftime("%Y%m%d")

            daily_df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                adjust="qfq"
            )
            if daily_df.empty or '日期' not in daily_df.columns:
                return None

            daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
            daily_df = daily_df.dropna(subset=['日期']).sort_values('日期')
            daily_df = daily_df[daily_df['日期'].dt.date <= target_date]
            if daily_df.empty:
                return None

            last_date = daily_df.iloc[-1]['日期'].strftime("%Y%m%d")
            return last_date
        except Exception as e:
            print(f"Error finding last trading day before {date_str}: {e}")
            return None

    def _fetch_historical_tick(self, code: str, date_str: str) -> pd.DataFrame:
        try:
            print(f"Downloading historical data (1-min bars) for {code} on {date_str}...")
            # Use EastMoney Minute Data (Robust)
            # period="1" means 1 minute
            # start_date, end_date need "YYYY-MM-DD HH:MM:SS"?? 
            # stock_zh_a_hist_min_em params: symbol, start_date, end_date, period, adjust
            # It expects specific format usually "2024-01-01 09:30:00"
            
            # Format date_str "20240101" -> "2024-01-01"
            d_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            start_dt = f"{d_fmt} 09:00:00"
            end_dt =   f"{d_fmt} 17:00:00"
            
            df = ak.stock_zh_a_hist_min_em(symbol=code, start_date=start_dt, end_date=end_dt, period="1", adjust="qfq")
            
            if df.empty:
                print(f"Minute data empty for {date_str}")
                return pd.DataFrame()
                
            # 映射列名以确保包含所需字段
            # akshare 的列名可能是 '时间', '开盘', '收盘', '最高', '最低', '成交量', '成交额'
            # 建立一个映射字典
            col_map = {
                '开盘': '开盘', 'open': '开盘',
                '收盘': '收盘', 'close': '收盘',
                '最高': '最高', 'high': '最高',
                '最低': '最低', 'low': '最低',
                '成交量': '成交量', 'volume': '成交量',
                '成交额': '成交额', 'amount': '成交额',
                '时间': '时间', 'time': '时间'
            }
            
            # 使用 rename 做宽容重命名
            df = df.rename(columns=col_map)
            
            # 确保必要的列存在
            required_cols = ['开盘', '收盘', '最高', '最低', '成交量', '成交额']
            missing_cols = [c for c in required_cols if c not in df.columns]
            
            if missing_cols:
                print(f"⚠️ Missing columns: {missing_cols}. Columns found: {df.columns.tolist()}")
                # 尝试用现有列填充缺失列 (Fallback 策略)
                if '收盘' in df.columns:
                    for col in missing_cols:
                        if col in ['开盘', '最高', '最低']:
                            df[col] = df['收盘']
                else:
                    return pd.DataFrame() # 无法恢复

            # 标准化 '成交额(元)' 列名
            df['成交额(元)'] = df['成交额']
            
            # 修复 0 值 (EM 分钟数据开头常见)
            cols_to_fix = ['开盘', '最高', '最低']
            for col in cols_to_fix:
                if col in df.columns:
                     df.loc[df[col] == 0, col] = df.loc[df[col] == 0, '收盘']
            
            # Simulate '性质' (Type) based on Price Momentum (Close - Prev Close)
            # Using candle color (Close > Open) is okay, but Minute bars are long.
            # Using price change from previous minute is often a better proxy for flow direction.
            
            df['price_change'] = df['收盘'].diff()
            df['price_change'] = df['price_change'].fillna(0) # First row neutral
            
            def get_type_from_momentum(change):
                if change > 0: return '买盘'
                if change < 0: return '卖盘'
                return '中性盘'
                
            df['性质'] = df['price_change'].apply(get_type_from_momentum)
            
            print(f"✅ Successfully fetched {len(df)} 1-min bars as historical data.")
            return df

        except Exception as e:
            print(f"Historical minute fetch failed for {date_str}: {e}")
            return pd.DataFrame()

    def get_stock_info(self, code: str) -> dict:
        return {"code": code, "name": "Unknown"}
        
    def get_history_data(self, code: str, start_date: date, end_date: date) -> pd.DataFrame:
        pass # Not used in main flow currently
