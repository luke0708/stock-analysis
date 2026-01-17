"""
技术指标计算器
计算常用技术指标：VWAP、移动平均线等
"""
import pandas as pd
import numpy as np
from typing import Dict

class IndicatorCalculator:
    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有技术指标并添加到DataFrame
        
        Returns:
            添加了指标列的DataFrame
        """
        if df.empty:
            return df
        
        df = df.copy()
        
        # 1. VWAP (Volume Weighted Average Price)
        df['VWAP'] = self._calculate_vwap(df)
        
        # 2. 移动平均线
        df['MA5'] = df['收盘'].rolling(window=5, min_periods=1).mean()
        df['MA10'] = df['收盘'].rolling(window=10, min_periods=1).mean()
        
        # 3. 成交量移动平均
        df['VOL_MA5'] = df['成交量'].rolling(window=5, min_periods=1).mean()
        
        # 4. 价格强度 (相对VWAP的偏离度)
        df['价格强度'] = ((df['收盘'] - df['VWAP']) / df['VWAP'] * 100)
        
        # 5. 累计涨跌幅
        df['累计涨跌幅'] = ((df['收盘'] - df.iloc[0]['开盘']) / df.iloc[0]['开盘'] * 100)
        
        return df
    
    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """
        计算VWAP (成交量加权平均价)
        VWAP = Σ(价格 × 成交量) / Σ(成交量)
        """
        # 使用收盘价和成交量计算
        cum_pv = (df['收盘'] * df['成交量']).cumsum()
        cum_v = df['成交量'].cumsum()
        
        # 避免除以0
        vwap = cum_pv / cum_v.replace(0, 1)
        
        return vwap
    
    def get_summary(self, df: pd.DataFrame) -> Dict:
        """获取指标摘要"""
        if df.empty or 'VWAP' not in df.columns:
            return {}
        
        latest = df.iloc[-1]
        
        return {
            'vwap': float(latest['VWAP']),
            'ma5': float(latest['MA5']),
            'ma10': float(latest['MA10']),
            'price_vs_vwap': float(latest['价格强度']),
            'is_above_vwap': latest['收盘'] > latest['VWAP'],
            'is_above_ma5': latest['收盘'] > latest['MA5'],
            'is_above_ma10': latest['收盘'] > latest['MA10'],
        }
