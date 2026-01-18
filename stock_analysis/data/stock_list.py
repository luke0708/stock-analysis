"""
股票列表管理模块
负责获取A股全量列表、缓存、以及拼音模糊搜索
"""
import akshare as ak
import pandas as pd
import streamlit as st
import os
from pypinyin import pinyin, Style, lazy_pinyin
from pathlib import Path
from datetime import datetime

class StockListProvider:
    """股票列表和搜索服务"""
    
    _instance = None
    _stock_df = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StockListProvider, cls).__new__(cls)
        return cls._instance
    
    def get_all_stocks(self, fresh=False) -> pd.DataFrame:
        """获取所有A股列表（带缓存）"""
        # 如果内存中已有且不是强制刷新
        if self._stock_df is not None and not fresh:
            return self._stock_df
            
        # 尝试从本地缓存文件读取 (每天更新一次)
        cache_dir = Path("exported_data/cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")
        cache_file = cache_dir / f"stock_list_{today}.csv"
        
        if cache_file.exists() and not fresh:
            try:
                self._stock_df = pd.read_csv(cache_file, dtype={'代码': str})
                return self._stock_df
            except:
                pass
                
        # 重新获取
        try:
            # 优化：使用更轻量的接口获取列表 (仅代码和名称)
            # stock_info_a_code_name 比 stock_zh_a_spot_em 快很多
            try:
                df = ak.stock_info_a_code_name()
            except:
                # Fallback to full spot if code_name fails
                df = ak.stock_zh_a_spot_em()
            
            # 确保列名一致
            if 'code' in df.columns:
                df = df.rename(columns={'code': '代码', 'name': '名称'})
            
            # 只保留需要的列
            if '代码' in df.columns and '名称' in df.columns:
                df = df[['代码', '名称']]
            
            # 生成拼音
            df['拼音'] = df['名称'].apply(lambda x: ''.join(lazy_pinyin(x)))
            df['拼音首字母'] = df['名称'].apply(lambda x: ''.join([p[0] for p in pinyin(x, style=Style.FIRST_LETTER)]))
            
            # 保存缓存
            try:
                # 清理旧缓存
                for f in cache_dir.glob("stock_list_*.csv"):
                    f.unlink()
                df.to_csv(cache_file, index=False)
            except:
                pass
                
            self._stock_df = df
            return df
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            # 如果失败尝试读取任何旧缓存
            try:
                cached_files = list(cache_dir.glob("stock_list_*.csv"))
                if cached_files:
                    self._stock_df = pd.read_csv(cached_files[0], dtype={'代码': str})
                    return self._stock_df
            except:
                pass
            return pd.DataFrame(columns=['代码', '名称', '拼音', '拼音首字母'])

    def search(self, query: str, limit=20) -> pd.DataFrame:
        """
        搜索股票
        支持：代码、名称、拼音全拼、拼音首字母
        """
        if not query:
            return pd.DataFrame()
            
        df = self.get_all_stocks()
        if df.empty:
            return df
            
        query = query.lower().strip()
        
        # 1. 代码匹配 (前缀)
        mask_code = df['代码'].str.startswith(query)
        
        # 2. 名称匹配 (包含)
        mask_name = df['名称'].str.contains(query, case=False)
        
        # 3. 拼音匹配
        mask_pinyin = df['拼音'].str.contains(query, case=False)
        mask_abbr = df['拼音首字母'].str.contains(query, case=False)
        
        # 合并结果
        result = df[mask_code | mask_name | mask_pinyin | mask_abbr]
        
        return result.head(limit)

# Streamlit 缓存包装
@st.cache_data(ttl=3600*12) # 12小时缓存
def get_stock_provider():
    return StockListProvider()
