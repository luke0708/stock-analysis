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
        keys_to_clear = ['df', 'actual_source', 'quality_report', 'all_analysis']
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
            
            # 验证必要的列
            required_cols = ['时间', '开盘', '收盘', '最高', '最低', '成交量', '成交额']
            missing = [col for col in required_cols if col not in df.columns]
            
            if missing:
                return None, False, f"缺少必要列: {', '.join(missing)}"
            
            # 确保时间列是datetime类型
            df['时间'] = pd.to_datetime(df['时间'])
            
            return df, True, f"成功导入 {len(df)} 条数据"
            
        except Exception as e:
            return None, False, f"导入失败: {str(e)}"
