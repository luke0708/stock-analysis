from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
import pandas as pd

class StockQuote(BaseModel):
    code: str
    name: str
    time: datetime
    price: float
    open: float
    high: float
    low: float
    volume: int
    amount: float
    
class TradeRecord(BaseModel):
    time: str
    price: float
    volume: int
    type: str  # 买盘/卖盘/中性盘
    amount: float
    
    @property
    def is_large_order(self, threshold: float = 1000000) -> bool:
        return self.amount >= threshold

class AnalysisResult(BaseModel):
    code: str
    timestamp: datetime
    main_inflow: float  # 主力流入
    retail_inflow: float # 散户流入
    large_order_count: int
