"""
缓存管理工具
管理session state和临时文件
"""
import streamlit as st
from pathlib import Path
import shutil

class CacheManager:
    """缓存管理器"""
    
    @staticmethod
    def clear_session_cache():
        """清除session state缓存"""
        keys_to_clear = ['df', 'raw_df', 'tick_context', 'actual_source', 'quality_report', 'all_analysis']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
    @staticmethod
    def get_cache_size() -> dict:
        """获取缓存大小信息"""
        info = {}
        
        # Session state项目数
        info['session_items'] = len(st.session_state)
        
        # 检查是否有数据
        info['has_data'] = st.session_state.get('df') is not None
        if info['has_data']:
            df = st.session_state.get('df')
            info['data_rows'] = len(df)
            info['data_columns'] = len(df.columns)
            # 估算内存（非常粗略）
            info['estimated_memory_mb'] = (df.memory_usage(deep=True).sum() / 1024 / 1024)
        
        return info
    
    @staticmethod
    def clear_exported_files(keep_recent=5):
        """
        清理导出的CSV文件
        
        Args:
            keep_recent: 保留最近N个文件
        """
        export_dir = Path("exported_data")
        if not export_dir.exists():
            return 0
        
        files = list(export_dir.glob("*.csv"))
        files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        deleted = 0
        for file in files[keep_recent:]:
            file.unlink()
            deleted += 1
        
        return deleted

class DataImporter:
    """数据导入器"""
    
    @staticmethod
    def import_from_csv(uploaded_file) -> tuple:
        """
        从上传的CSV文件导入数据
        
        Returns:
            (df, success, message)
        """
        import pandas as pd
        
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')

            col_map = {
                '成交时间': '时间',
                'time': '时间',
                'datetime': '时间',
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
            df = df.rename(columns=col_map)

            # 分钟数据验证
            minute_required = ['时间', '开盘', '收盘', '最高', '最低', '成交量', '成交额']
            minute_missing = [col for col in minute_required if col not in df.columns]

            if not minute_missing:
                df['时间'] = pd.to_datetime(df['时间'], errors='coerce')
                return df, True, f"成功导入 {len(df)} 条数据"

            # Tick 数据验证
            has_time = '时间' in df.columns
            has_price = '成交价格' in df.columns
            has_volume = '成交量' in df.columns
            has_amount = any(col in df.columns for col in ['成交额', '成交金额', '成交额(元)'])

            if has_time and has_price and (has_volume or has_amount):
                time_series = df['时间'].astype(str).str.strip()
                has_date = time_series.str.contains(r"\\d{4}[-/]\\d{2}[-/]\\d{2}")
                if has_date.any():
                    df['时间'] = pd.to_datetime(time_series, errors='coerce')
                df.attrs['data_type'] = 'tick'
                return df, True, f"成功导入 {len(df)} 条数据 (Tick)"

            tick_hint = "若导入逐笔Tick，请包含: 时间, 成交价格, 成交量/成交额(或成交金额), 性质(可选)"
            return None, False, f"缺少必要列: {', '.join(minute_missing)}。{tick_hint}"
            
        except Exception as e:
            return None, False, f"导入失败: {str(e)}"
