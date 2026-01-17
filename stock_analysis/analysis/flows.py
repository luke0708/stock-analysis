"""
资金流向分析器 - 增强版
优化算法并添加详细说明
"""
import pandas as pd
import numpy as np

class FlowAnalyzer:
    """
    资金流向分析器
    
    算法说明：
    1. **大单定义**：成交额 >= 10万元的订单视为主力大单
    2. **散户定义**：成交额 < 10万元的订单视为散户小单
    3. **净流入计算**：买入额 - 卖出额
    
    注意事项：
    - 本算法为简化版本，实际市场中主力散户识别更复杂
    - 仅供参考，不构成投资建议
    """
    
    def __init__(self, large_order_threshold: float = 100000):
        """
        Args:
            large_order_threshold: 大单阈值（元），默认10万
        """
        self.large_order_threshold = large_order_threshold
    
    def calculate_flows(self, df: pd.DataFrame) -> dict:
        """
        计算资金流向
        
        Returns:
            包含以下字段的字典：
            - total_turnover: 总成交额
            - large_order_net_inflow: 主力净流入（大单买入-大单卖出）
            - retail_net_inflow: 散户净流入（小单买入-小单卖出）
            - large_order_count: 大单笔数
            - retail_order_count: 散户笔数
            - large_buy_amount: 主力买入总额
            - large_sell_amount: 主力卖出总额
            - retail_buy_amount: 散户买入总额
            - retail_sell_amount: 散户卖出总额
        """
        if df.empty:
            return {}
        
        # 确保有必要的列
        if '成交额(元)' not in df.columns:
            if 'amount' in df.columns:
                df['成交额(元)'] = df['amount']
            else:
                return {"error": "Missing transaction amount data"}
        
        if '性质' not in df.columns:
            if 'type' in df.columns:
                df['性质'] = df['type']
            else:
                # 如果没有性质，根据价格变动推测
                if 'price_change' in df.columns:
                    df['性质'] = df['price_change'].apply(
                        lambda x: '买盘' if x > 0 else ('卖盘' if x < 0 else '中性盘')
                    )
        
        # 1. 按订单大小分类
        large_orders = df[df['成交额(元)'] >= self.large_order_threshold]
        small_orders = df[df['成交额(元)'] < self.large_order_threshold]
        
        # 2. 计算各类资金
        def calc_flows(sub_df):
            buy_amount = sub_df[sub_df['性质'] == '买盘']['成交额(元)'].sum()
            sell_amount = sub_df[sub_df['性质'] == '卖盘']['成交额(元)'].sum()
            net_inflow = buy_amount - sell_amount
            return float(buy_amount), float(sell_amount), float(net_inflow)
        
        large_buy, large_sell, large_net = calc_flows(large_orders)
        retail_buy, retail_sell, retail_net = calc_flows(small_orders)
        
        return {
            "total_turnover": float(df['成交额(元)'].sum()),
            
            # 主力资金
            "large_order_net_inflow": large_net,
            "large_buy_amount": large_buy,
            "large_sell_amount": large_sell,
            "large_order_count": len(large_orders),
            
            # 散户资金
            "retail_net_inflow": retail_net,
            "retail_buy_amount": retail_buy,
            "retail_sell_amount": retail_sell,
            "retail_order_count": len(small_orders),
            
            # 占比
            "large_order_ratio": len(large_orders) / len(df) * 100 if len(df) > 0 else 0,
            "retail_order_ratio": len(small_orders) / len(df) * 100 if len(df) > 0 else 0,
        }
    
    def get_algorithm_description(self) -> str:
        """获取算法说明"""
        return f"""
### 资金流向分析算法说明

#### 📊 分类标准
- **主力大单**: 单笔成交额 ≥ ¥{self.large_order_threshold:,.0f}
- **散户小单**: 单笔成交额 < ¥{self.large_order_threshold:,.0f}

#### 🧮 计算公式
1. **主力净流入** = 主力买入总额 - 主力卖出总额
2. **散户净流入** = 散户买入总额 - 散户卖出总额

#### 📝 注意事项
- 买卖性质根据价格变动方向判断（上涨=买盘，下跌=卖盘）
- 本算法为**简化模型**，实际市场识别更复杂
- 数据来源：分钟级成交数据
- 仅供参考学习，不构成投资建议

#### 💡 如何理解
- **主力净流入为正**: 大资金在积极买入，可能看好后市
- **主力净流入为负**: 大资金在卖出，需警惕
- **散户行为**: 通常与主力相反，可作为参考对比
"""
