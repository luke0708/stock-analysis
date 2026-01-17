"""
数据清洗模块
负责清洗和验证股票分钟数据的质量
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

class DataCleaner:
    def __init__(self):
        self.quality_issues = []
    
    def clean(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """
        清洗数据并返回清洗后的数据和质量报告
        
        Args:
            df: 原始数据DataFrame
            
        Returns:
            (cleaned_df, quality_report)
        """
        if df.empty:
            return df, {"status": "empty", "issues": []}
        
        self.quality_issues = []
        original_len = len(df)
        
        # 1. 修复缺失值
        df = self._fix_missing_values(df)
        
        # 2. 修复异常值
        df = self._fix_anomalies(df)
        
        # 3. 标准化数据
        df = self._standardize_data(df)
        
        # 4. 生成质量报告
        report = self._generate_report(original_len, len(df))
        
        return df, report
    
    def _fix_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """处理缺失值"""
        # 检测缺失值
        missing_cols = df.columns[df.isnull().any()].tolist()
        if missing_cols:
            self.quality_issues.append({
                'type': 'missing_values',
                'columns': missing_cols,
                'count': df.isnull().sum().sum()
            })
            
            # 前向填充价格列
            price_cols = ['开盘', '收盘', '最高', '最低', '均价']
            for col in price_cols:
                if col in df.columns:
                    df[col] = df[col].fillna(method='ffill').fillna(method='bfill')
            
            # 成交量和成交额填0
            volume_cols = ['成交量', '成交额', '成交额(元)']
            for col in volume_cols:
                if col in df.columns:
                    df[col] = df[col].fillna(0)
        
        return df
    
    def _fix_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """修复异常值"""
        # 1. 修复 Open/High/Low = 0 的情况
        zero_open = (df['开盘'] == 0).sum()
        if zero_open > 0:
            self.quality_issues.append({
                'type': 'zero_price',
                'field': '开盘',
                'count': zero_open
            })
            # 用收盘价填充
            df.loc[df['开盘'] == 0, '开盘'] = df.loc[df['开盘'] == 0, '收盘']
        
        # 修复最高价、最低价为0
        for col in ['最高', '最低']:
            zero_count = (df[col] == 0).sum()
            if zero_count > 0:
                self.quality_issues.append({
                    'type': 'zero_price',
                    'field': col,
                    'count': zero_count
                })
                df.loc[df[col] == 0, col] = df.loc[df[col] == 0, '收盘']
        
        # 2. 确保价格逻辑性: 最高价 >= 最低价
        invalid_hl = df['最高'] < df['最低']
        if invalid_hl.any():
            count = invalid_hl.sum()
            self.quality_issues.append({
                'type': 'invalid_range',
                'issue': '最高价 < 最低价',
                'count': count
            })
            # 交换最高最低
            df.loc[invalid_hl, ['最高', '最低']] = df.loc[invalid_hl, ['最低', '最高']].values
        
        # 3. 检测价格异常跳跃 (超过10%)
        if '收盘' in df.columns and len(df) > 1:
            price_change = df['收盘'].pct_change().abs()
            spikes = price_change > 0.10
            if spikes.any():
                spike_count = spikes.sum()
                self.quality_issues.append({
                    'type': 'price_spike',
                    'threshold': '10%',
                    'count': spike_count
                })
        
        # 4. 检测成交量异常 (为0或异常大)
        if '成交量' in df.columns and len(df) > 1:
            zero_volume = (df['成交量'] == 0).sum()
            if zero_volume > 0:
                self.quality_issues.append({
                    'type': 'zero_volume',
                    'count': zero_volume
                })
            
            # 检测异常大成交量 (超过均值10倍)
            mean_vol = df['成交量'].mean()
            huge_volume = df['成交量'] > (mean_vol * 10)
            if huge_volume.any():
                self.quality_issues.append({
                    'type': 'huge_volume',
                    'count': huge_volume.sum(),
                    'threshold': '10x平均值'
                })
        
        return df
    
    def _standardize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化数据格式"""
        # 确保时间列是datetime类型
        if '时间' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['时间']):
            df['时间'] = pd.to_datetime(df['时间'])
        
        # 确保数值列是float/int类型
        numeric_cols = ['开盘', '收盘', '最高', '最低', '成交量', '成交额', '均价']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 按时间排序
        if '时间' in df.columns:
            df = df.sort_values('时间').reset_index(drop=True)
        
        return df
    
    def _generate_report(self, original_len: int, cleaned_len: int) -> Dict:
        """生成数据质量报告"""
        report = {
            'original_records': original_len,
            'cleaned_records': cleaned_len,
            'issues_found': len(self.quality_issues),
            'issues': self.quality_issues,
            'quality_score': self._calculate_quality_score()
        }
        return report
    
    def _calculate_quality_score(self) -> float:
        """
        计算数据质量评分 (0-100)
        每个问题扣分，不同类型问题权重不同
        """
        score = 100.0
        
        severity_weights = {
            'missing_values': 10,
            'zero_price': 15,
            'invalid_range': 20,
            'price_spike': 5,
            'zero_volume': 3,
            'huge_volume': 5
        }
        
        for issue in self.quality_issues:
            issue_type = issue['type']
            weight = severity_weights.get(issue_type, 5)
            count = issue.get('count', 1)
            
            # 每个问题根据严重程度和数量扣分
            deduction = min(weight * (count / 10), weight * 2)  # 最多扣两倍权重
            score -= deduction
        
        return max(0.0, score)  # 确保不低于0

def get_quality_summary(report: Dict) -> str:
    """生成人类可读的质量摘要"""
    score = report['quality_score']
    
    if score >= 90:
        status = "优秀 ✅"
        color = "green"
    elif score >= 75:
        status = "良好 ⚠️"
        color = "yellow"
    elif score >= 60:
        status = "一般 ⚠️"
        color = "orange"
    else:
        status = "较差 ❌"
        color = "red"
    
    summary = f"数据质量: {status} (评分: {score:.1f}/100)\n"
    summary += f"原始记录: {report['original_records']} 条\n"
    summary += f"清洗后: {report['cleaned_records']} 条\n"
    summary += f"发现问题: {report['issues_found']} 个\n"
    
    if report['issues']:
        summary += "\n问题详情:\n"
        for issue in report['issues']:
            summary += f"  - {issue['type']}: {issue.get('count', 'N/A')} 处\n"
    
    return summary
