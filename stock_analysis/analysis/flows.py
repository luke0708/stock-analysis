"""
资金流向分析器 - 增强版
优化算法并添加详细说明
"""
import pandas as pd
import numpy as np

class FlowAnalyzer:
    """
    资金流向分析器
    
    算法说明 (Level-2 增强算法):
    1. **数据基础**: 获取逐笔成交记录（时间、价格、成交量、买卖方向）
    2. **资金分级**: 
       - **主力资金**: 单笔成交额 ≥ 20万元
       - **散户资金**: 单笔成交额 < 20万元
    3. **流向计算**:
       - 主力流入 = ∑(主力级别 & 主动买入)
       - 主力流出 = ∑(主力级别 & 主动卖出)
       - 主力净流入 = 主力流入 - 主力流出
    
    注意事项：
    - 此阈值(20万)为通用参考标准，不同软件可能有细微差异
    """
    
    def __init__(self, large_order_threshold: float = 200000):
        """
        Args:
            large_order_threshold: 大单阈值（元），默认20万 (Level-2 常用标准)
        """
        self.large_order_threshold = large_order_threshold
    
    def calculate_flows(self, df: pd.DataFrame) -> dict:
        """
        计算资金流向
        
        Returns:
            包含以下字段的字典：
            - total_turnover: 总成交额
            - large_order_net_inflow: 主力净流入
            - retail_net_inflow: 散户净流入
            - ...
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
                # Fallback: 根据价格变动推测 (Level-1 approximation)
                if 'price_change' in df.columns:
                    df['性质'] = df['price_change'].apply(
                        lambda x: '买盘' if x > 0 else ('卖盘' if x < 0 else '中性盘')
                    )
        
        # 1. 划分资金类型 (根据 20万 阈值)
        # 主力资金: >= 200,000
        mask_main = df['成交额(元)'] >= self.large_order_threshold
        # 散户资金: < 200,000
        mask_retail = ~mask_main
        
        main_orders = df[mask_main]
        retail_orders = df[mask_retail]
        
        # 2. 分类汇总 (计算流入流出)
        def calc_net(sub_df):
            # 主动买入
            inflow = sub_df[sub_df['性质'].astype(str).str.contains('买')]['成交额(元)'].sum()
            # 主动卖出
            outflow = sub_df[sub_df['性质'].astype(str).str.contains('卖')]['成交额(元)'].sum()
            net = inflow - outflow
            return float(inflow), float(outflow), float(net)
        
        main_in, main_out, main_net = calc_net(main_orders)
        retail_in, retail_out, retail_net = calc_net(retail_orders)
        
        return {
            "total_turnover": float(df['成交额(元)'].sum()),
            
            # 主力资金
            "large_order_net_inflow": main_net,
            "large_buy_amount": main_in,
            "large_sell_amount": main_out,
            "large_order_count": len(main_orders),
            
            # 散户资金
            "retail_net_inflow": retail_net,
            "retail_buy_amount": retail_in,
            "retail_sell_amount": retail_out,
            "retail_order_count": len(retail_orders),
            
            # 统计
            "large_order_ratio": len(main_orders) / len(df) * 100 if len(df) > 0 else 0,
        }
    
    def get_algorithm_description(self) -> str:
        """获取算法说明"""
        t_val = self.large_order_threshold / 10000
        return f"""
### 资金流向算法 (Level-2 增强版)

#### 📊 资金划分标准
根据单笔成交金额进行划分：
- **主力资金**: 单笔成交额 ≥ **{t_val:.0f}万元**
- **散户资金**: 单笔成交额 < **{t_val:.0f}万元**

#### 🧮 计算公式
1. **主力净流入** = 主力主动买入额 - 主力主动卖出额
2. **散户净流入** = 散户主动买入额 - 散户主动卖出额

#### 📝 说明
- **数据源**: 逐笔成交数据 (Tick Data)
- **买卖判定**: 根据每一笔交易的主动性方向（主动买/主动卖）统计
- 这是业内通用的资金流向计算逻辑，能较好地反映大资金的进出意愿。
"""
