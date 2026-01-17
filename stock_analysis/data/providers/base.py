from abc import ABC, abstractmethod
import pandas as pd
from datetime import date
from typing import Optional

class StockDataProvider(ABC):
    
    @abstractmethod
    def get_stock_info(self, code: str) -> dict:
        """Get basic info like name, code"""
        pass
        
    @abstractmethod
    def get_realtime_data(self, code: str) -> pd.DataFrame:
        """Get today's tick/minute data"""
        pass
        
    @abstractmethod
    def get_history_data(self, code: str, start_date: date, end_date: date) -> pd.DataFrame:
        """Get historical daily data"""
        pass
