"""
存储管理模块
负责本地数据的持久化，如自选股、用户配置等
使用 JSON 文件存储，方便查看和迁移
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Optional

class StorageManager:
    """本地存储管理器"""
    
    def __init__(self, storage_dir="exported_data"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.watchlist_file = self.storage_dir / "watchlist.json"
        
    def load_watchlist(self) -> List[Dict]:
        """加载自选股列表"""
        if not self.watchlist_file.exists():
            return []
            
        try:
            with open(self.watchlist_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('stocks', [])
        except Exception as e:
            print(f"加载自选股失败: {e}")
            return []
            
    def save_watchlist(self, stocks: List[Dict]):
        """保存自选股列表"""
        try:
            data = {
                'updated_at': str(import_datetime.now()),
                'stocks': stocks
            }
            with open(self.watchlist_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存自选股失败: {e}")
            
    def add_to_watchlist(self, code: str, name: str):
        """添加股票到自选"""
        stocks = self.load_watchlist()
        # 检查是否已存在
        for s in stocks:
            if s['code'] == code:
                return # 已存在
        
        stocks.append({
            'code': code,
            'name': name,
            'added_at': str(import_datetime.now())
        })
        self.save_watchlist(stocks)
        
    def remove_from_watchlist(self, code: str):
        """从自选移除"""
        stocks = self.load_watchlist()
        stocks = [s for s in stocks if s['code'] != code]
        self.save_watchlist(stocks)
        
    def get_watchlist_codes(self) -> List[str]:
        """获取所有自选股代码"""
        stocks = self.load_watchlist()
        return [s['code'] for s in stocks]
    
    def get_watchlist(self) -> List[Dict]:
        """获取自选股列表 (alias for load_watchlist)"""
        return self.load_watchlist()

from datetime import datetime as import_datetime
