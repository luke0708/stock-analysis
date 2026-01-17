"""
异常检测器
检测大单、价格跳跃、成交量激增等异常事件
"""
import pandas as pd
from typing import Dict, List

class AnomalyDetector:
    def __init__(self, large_order_threshold_ratio=3.0, price_spike_threshold=0.03):
        """
        Args:
            large_order_threshold_ratio: 大单阈值倍数（相对于平均成交额）
            price_spike_threshold: 价格跳跃阈值（百分比）
        """
        self.large_order_threshold_ratio = large_order_threshold_ratio
        self.price_spike_threshold = price_spike_threshold
    
    def detect_all(self, df: pd.DataFrame) -> Dict:
        """
        检测所有异常
        
        Returns:
            包含各类异常的字典
        """
        if df.empty:
            return {}
        
        result = {
            'large_orders': self._detect_large_orders(df),
            'price_spikes': self._detect_price_spikes(df),
            'volume_surges': self._detect_volume_surges(df),
            'continuous_trends': self._detect_continuous_trends(df)
        }
        
        # 统计
        result['summary'] = {
            'large_order_count': len(result['large_orders']),
            'price_spike_count': len(result['price_spikes']),
            'volume_surge_count': len(result['volume_surges']),
            'longest_rise_streak': result['continuous_trends']['longest_rise'],
            'longest_fall_streak': result['continuous_trends']['longest_fall']
        }
        
        return result
    
    def _detect_large_orders(self, df: pd.DataFrame) -> List[Dict]:
        """检测大单"""
        avg_turnover = df['成交额(元)'].mean()
        threshold = avg_turnover * self.large_order_threshold_ratio
        
        large_orders = df[df['成交额(元)'] > threshold].copy()
        
        results = []
        for idx, row in large_orders.iterrows():
            results.append({
                'time': row['时间'],
                'amount': float(row['成交额(元)']),
                'volume': int(row['成交量']),
                'price': float(row['收盘']),
                'type': row.get('性质', '未知'),
                'ratio': float(row['成交额(元)'] / avg_turnover)
            })
        
        return results
    
    def _detect_price_spikes(self, df: pd.DataFrame) -> List[Dict]:
        """检测价格异常跳跃"""
        if len(df) < 2:
            return []
        
        df_copy = df.copy()
        df_copy['price_change_pct'] = df_copy['收盘'].pct_change().abs()
        
        spikes = df_copy[df_copy['price_change_pct'] > self.price_spike_threshold].copy()
        
        results = []
        for idx, row in spikes.iterrows():
            if pd.notna(row['price_change_pct']):
                results.append({
                    'time': row['时间'],
                    'price': float(row['收盘']),
                    'change_pct': float(row['price_change_pct'] * 100),
                    'direction': '上涨' if row['收盘'] > row['开盘'] else '下跌'
                })
        
        return results
    
    def _detect_volume_surges(self, df: pd.DataFrame) -> List[Dict]:
        """检测成交量异常激增"""
        avg_volume = df['成交量'].mean()
        threshold = avg_volume * 5  # 5倍平均成交量
        
        surges = df[df['成交量'] > threshold].copy()
        
        results = []
        for idx, row in surges.iterrows():
            results.append({
                'time': row['时间'],
                'volume': int(row['成交量']),
                'ratio': float(row['成交量'] / avg_volume),
                'price': float(row['收盘'])
            })
        
        return results
    
    def _detect_continuous_trends(self, df: pd.DataFrame) -> Dict:
        """检测连续上涨/下跌"""
        if len(df) < 2:
            return {'longest_rise': 0, 'longest_fall': 0, 'current_streak': 0}
        
        df_copy = df.copy()
        df_copy['is_rising'] = df_copy['收盘'] > df_copy['开盘']
        
        # 计算连续涨跌
        longest_rise = 0
        longest_fall = 0
        current_streak = 0
        current_type = None
        
        for is_rising in df_copy['is_rising']:
            if is_rising:
                if current_type == 'rise':
                    current_streak += 1
                else:
                    longest_fall = max(longest_fall, current_streak)
                    current_streak = 1
                    current_type = 'rise'
            else:
                if current_type == 'fall':
                    current_streak += 1
                else:
                    longest_rise = max(longest_rise, current_streak)
                    current_streak = 1
                    current_type = 'fall'
        
        # 更新最后一次
        if current_type == 'rise':
            longest_rise = max(longest_rise, current_streak)
        else:
            longest_fall = max(longest_fall, current_streak)
        
        return {
            'longest_rise': longest_rise,
            'longest_fall': longest_fall,
            'current_streak': current_streak,
            'current_type': current_type
        }
