import akshare as ak
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Optional
from .base import StockDataProvider

# 通达信行情服务器（2026-05 实测可用，稳定性优于 Eastmoney HTTP）
_TDX_SERVERS = [
    ('180.153.18.170', 7709),  # 上海，推荐首选
    ('119.147.212.81', 7709),  # 广东
    ('124.74.236.50',  7709),  # 上海备用
]

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

    def _pytdx_daily_bars(self, code: str, count: int = 1):
        """用 pytdx 拉最近 count 根日线，失败返回空列表。"""
        from pytdx.hq import TdxHq_API
        market = 1 if code.startswith(("6", "5", "9")) else 0
        for host, port in _TDX_SERVERS:
            try:
                api = TdxHq_API(raise_exception=True)
                api.connect(host, port)
                data = api.get_security_bars(9, market, code, 0, count)
                api.disconnect()
                if data:
                    return data
            except Exception:
                continue
        return []

    def _get_last_trading_day(self, code: str) -> Optional[str]:
        # pytdx: 只取 1 根日线，避免拉全量 Eastmoney 历史
        try:
            data = self._pytdx_daily_bars(code, 1)
            if data:
                return data[-1]['datetime'][:10].replace('-', '')
        except Exception:
            pass
        # fallback: Eastmoney
        try:
            daily_df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20230101", adjust="qfq")
            if not daily_df.empty:
                return str(daily_df.iloc[-1]['日期']).replace("-", "").replace("/", "")
        except Exception as e:
            print(f"Error finding last trading day: {e}")
        return None

    def _get_last_trading_day_before(self, code: str, date_str: str) -> Optional[str]:
        target_date = datetime.strptime(date_str, "%Y%m%d").date()
        # pytdx: 按日历天数估算所需日线数，过滤出 <= target_date 的最近一天
        try:
            days_span = (date.today() - target_date).days + 5
            bars_needed = min(int(days_span * 5 / 7) + 10, 60)
            data = self._pytdx_daily_bars(code, bars_needed)
            if data:
                df = pd.DataFrame(data)
                df['_d'] = pd.to_datetime(df['datetime'].str[:10]).dt.date
                before = df[df['_d'] <= target_date].sort_values('_d')
                if not before.empty:
                    return before.iloc[-1]['_d'].strftime('%Y%m%d')
        except Exception:
            pass
        # fallback: Eastmoney
        try:
            start_d = (target_date - timedelta(days=30)).strftime("%Y%m%d")
            daily_df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_d, adjust="qfq")
            if daily_df.empty or '日期' not in daily_df.columns:
                return None
            daily_df['日期'] = pd.to_datetime(daily_df['日期'], errors='coerce')
            daily_df = daily_df.dropna(subset=['日期']).sort_values('日期')
            daily_df = daily_df[daily_df['日期'].dt.date <= target_date]
            if daily_df.empty:
                return None
            return daily_df.iloc[-1]['日期'].strftime("%Y%m%d")
        except Exception as e:
            print(f"Error finding last trading day before {date_str}: {e}")
        return None

    def _fetch_historical_tick(self, code: str, date_str: str) -> pd.DataFrame:
        print(f"Downloading historical data (1-min bars) for {code} on {date_str}...")
        raw_df = pd.DataFrame()

        # Method 1: Eastmoney 1-min bars
        try:
            d_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            temp = ak.stock_zh_a_hist_min_em(
                symbol=code,
                start_date=f"{d_fmt} 09:00:00",
                end_date=f"{d_fmt} 17:00:00",
                period="1", adjust="qfq",
            )
            if temp is not None and not temp.empty:
                raw_df = temp
        except Exception as e:
            print(f"⚠️ Eastmoney 1-min failed for {date_str}: {e}")

        # Method 2: pytdx 1-min bars fallback（返回已处理好的 df，直接用）
        if raw_df.empty:
            return self._fetch_historical_tick_pytdx(code, date_str)

        # 处理 Eastmoney 数据
        col_map = {
            '开盘': '开盘', 'open': '开盘',
            '收盘': '收盘', 'close': '收盘',
            '最高': '最高', 'high': '最高',
            '最低': '最低', 'low': '最低',
            '成交量': '成交量', 'volume': '成交量',
            '成交额': '成交额', 'amount': '成交额',
            '时间': '时间', 'time': '时间',
        }
        df = raw_df.rename(columns=col_map)

        required_cols = ['开盘', '收盘', '最高', '最低', '成交量', '成交额']
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            print(f"⚠️ Missing columns: {missing_cols}. Columns found: {df.columns.tolist()}")
            if '收盘' in df.columns:
                for col in missing_cols:
                    if col in ['开盘', '最高', '最低']:
                        df[col] = df['收盘']
            else:
                return pd.DataFrame()

        df['成交额(元)'] = df['成交额']
        for col in ['开盘', '最高', '最低']:
            if col in df.columns:
                df.loc[df[col] == 0, col] = df.loc[df[col] == 0, '收盘']

        df['price_change'] = df['收盘'].diff().fillna(0)
        df['性质'] = df['price_change'].apply(
            lambda c: '买盘' if c > 0 else ('卖盘' if c < 0 else '中性盘')
        )
        print(f"✅ Successfully fetched {len(df)} 1-min bars as historical data.")
        return df

    def _fetch_historical_tick_pytdx(self, code: str, date_str: str) -> pd.DataFrame:
        """pytdx fallback：按偏移量拉历史 1 分钟线，处理后返回与 Eastmoney 路径相同格式。"""
        try:
            from pytdx.hq import TdxHq_API
            target_date = datetime.strptime(date_str, "%Y%m%d").date()
            market = 1 if code.startswith(("6", "5", "9")) else 0

            for host, port in _TDX_SERVERS:
                try:
                    api = TdxHq_API(raise_exception=True)
                    api.connect(host, port)

                    # Step 1: 用日线确认 target_date 距今几个交易日
                    days_span = (date.today() - target_date).days + 5
                    daily_data = api.get_security_bars(9, market, code, 0, min(int(days_span * 5 / 7) + 10, 60))
                    if not daily_data:
                        api.disconnect()
                        continue

                    df_daily = pd.DataFrame(daily_data)
                    df_daily['_d'] = pd.to_datetime(df_daily['datetime'].str[:10]).dt.date
                    dates = sorted(df_daily['_d'].tolist())
                    if target_date not in dates:
                        api.disconnect()
                        continue

                    # 每天 240 根 1-min 线，offset = 距最近交易日的天数 * 240
                    offset = (len(dates) - 1 - dates.index(target_date)) * 240
                    min_data = api.get_security_bars(8, market, code, offset, 260)
                    api.disconnect()

                    if not min_data:
                        continue

                    df = pd.DataFrame(min_data)
                    df = df[df['datetime'].str[:10] == str(target_date)].copy()
                    if df.empty:
                        continue

                    df = df.rename(columns={
                        'open': '开盘', 'close': '收盘', 'high': '最高', 'low': '最低',
                        'vol': '成交量', 'amount': '成交额',
                    })
                    df['时间'] = df['datetime'].str[11:]
                    df['成交额(元)'] = df['成交额']
                    for col in ['开盘', '最高', '最低']:
                        if col in df.columns:
                            df.loc[df[col] == 0, col] = df.loc[df[col] == 0, '收盘']

                    df['price_change'] = df['收盘'].diff().fillna(0)
                    df['性质'] = df['price_change'].apply(
                        lambda c: '买盘' if c > 0 else ('卖盘' if c < 0 else '中性盘')
                    )
                    print(f"✅ Historical 1-min bars via pytdx for {code} on {date_str} ({len(df)} rows)")
                    return df.reset_index(drop=True)

                except Exception as e:
                    print(f"⚠️ pytdx min fallback {host} failed: {e}")
                    continue
        except Exception as e:
            print(f"❌ pytdx historical tick fallback error: {e}")

        print(f"Minute data empty for {date_str}")
        return pd.DataFrame()

    def get_stock_info(self, code: str) -> dict:
        return {"code": code, "name": "Unknown"}
        
    def get_history_data(self, code: str, start_date: date, end_date: date) -> pd.DataFrame:
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        df = pd.DataFrame()
        import time
        
        # Method 1: akshare Eastmoney with retries
        for attempt in range(3):
            try:
                temp_df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_str,
                    end_date=end_str,
                    adjust="qfq",
                )
                if temp_df is not None and not temp_df.empty:
                    df = temp_df
                    print(f"✅ Successfully fetched daily history for {code} via Eastmoney (Attempt {attempt + 1})")
                    break
            except Exception as exc:
                print(f"⚠️ Daily history fetch failed via Eastmoney (attempt {attempt+1}/3): {exc}")
                time.sleep(1)

        # Method 2: pytdx 通达信直连（TCP，无 HTTP 限流问题）
        if df.empty:
            print(f"⚠️ Falling back to pytdx (通达信) for {code} daily history...")
            try:
                from pytdx.hq import TdxHq_API
                # SH: 6/5/9 开头；其余为 SZ
                market = 1 if code.startswith(("6", "5", "9")) else 0
                # 从 start_date 到今天估算所需交易日数（加 buffer）
                days_span = max((date.today() - start_date).days, 1)
                bars_needed = min(int(days_span * 5 / 7) + 20, 800)

                tdx_raw = []
                for host, port in _TDX_SERVERS:
                    try:
                        api = TdxHq_API(raise_exception=True)
                        api.connect(host, port)
                        tdx_raw = api.get_security_bars(9, market, code, 0, bars_needed)
                        api.disconnect()
                        if tdx_raw:
                            break
                    except Exception as _e:
                        print(f"⚠️ pytdx {host} 失败: {_e}")

                if tdx_raw:
                    temp_df = pd.DataFrame(tdx_raw)
                    temp_df["日期"] = pd.to_datetime(temp_df["datetime"].str[:10])
                    temp_df = temp_df[
                        (temp_df["日期"].dt.date >= start_date) &
                        (temp_df["日期"].dt.date <= end_date)
                    ]
                    temp_df = temp_df.rename(columns={
                        "open": "开盘", "close": "收盘",
                        "high": "最高", "low": "最低",
                        "vol": "成交量", "amount": "成交额",
                    })
                    if not temp_df.empty:
                        df = temp_df
                        print(f"✅ Successfully fetched daily history for {code} via pytdx")
            except Exception as exc:
                print(f"❌ Fallback to pytdx failed for {code}: {exc}")

        # Method 3: yfinance Fallback
        if df.empty:
            print(f"⚠️ Falling back to yfinance for {code} daily history...")
            try:
                import yfinance as yf
                yf_symbol = f"{code}.SS" if code.startswith("6") or code.startswith("4") or code.startswith("8") else f"{code}.SZ"
                yf_end = end_date + timedelta(days=1)
                temp_df = yf.download(yf_symbol, start=start_date.strftime("%Y-%m-%d"), end=yf_end.strftime("%Y-%m-%d"), progress=False, auto_adjust=True)
                if temp_df is not None and not temp_df.empty:
                    temp_df = temp_df.reset_index()
                    if isinstance(temp_df.columns, pd.MultiIndex):
                        temp_df.columns = temp_df.columns.get_level_values(0)
                    temp_df = temp_df.rename(columns={
                        "Date": "日期",
                        "Open": "开盘",
                        "Close": "收盘",
                        "High": "最高",
                        "Low": "最低",
                        "Volume": "成交量",
                    })
                    if "成交量" in temp_df.columns and "收盘" in temp_df.columns:
                        temp_df["成交额"] = temp_df["成交量"] * temp_df["收盘"]
                    else:
                        temp_df["成交额"] = 0
                    df = temp_df
                    print(f"✅ Successfully fetched daily history for {code} via yfinance")
            except Exception as exc:
                print(f"❌ Fallback to yfinance failed for {code}: {exc}")

        # Method 4: akshare Tencent Fallback
        if df.empty:
            print(f"⚠️ Falling back to akshare Tencent for {code} daily history...")
            try:
                prefix = "sh" if code.startswith("6") or code.startswith("4") or code.startswith("8") else "sz"
                temp_df = ak.stock_zh_a_daily(symbol=f"{prefix}{code}", start_date=start_str, end_date=end_str)
                if temp_df is not None and not temp_df.empty:
                    df = temp_df
                    print(f"✅ Successfully fetched daily history for {code} via Tencent")
            except Exception as exc:
                print(f"❌ Fallback to akshare Tencent failed for {code}: {exc}")

        if df is None or df.empty:
            print(f"❌ All methods failed to fetch daily history for {code}")
            return pd.DataFrame()

        col_map = {
            "date": "日期",
            "开盘": "开盘",
            "收盘": "收盘",
            "最高": "最高",
            "最低": "最低",
            "成交量": "成交量",
            "成交额": "成交额",
            "volume": "成交量",
            "amount": "成交额",
        }
        df = df.rename(columns=col_map)
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
            df = df.dropna(subset=["日期"]).sort_values("日期")

        for col in ["开盘", "收盘", "最高", "最低", "成交量", "成交额"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
