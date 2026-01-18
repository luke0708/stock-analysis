"""
资金流向分析器 - 增强版
优化算法并添加详细说明
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict

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

    def _get_time_column(self, df: pd.DataFrame) -> Optional[str]:
        for time_col in ['时间', '成交时间', 'time', 'datetime', '时间戳']:
            if time_col in df.columns:
                return time_col
        return None

    def _infer_granularity(self, df: pd.DataFrame) -> str:
        time_col = self._get_time_column(df)
        if time_col:
            time_series = pd.to_datetime(df[time_col], errors='coerce').dropna().sort_values()
            if len(time_series) >= 2:
                deltas = time_series.diff().dt.total_seconds().dropna()
                if not deltas.empty:
                    median_sec = float(deltas.median())
                    if median_sec >= 45:
                        return "minute"
                    if median_sec <= 5:
                        return "tick"
        row_count = len(df)
        if row_count >= 1200:
            return "tick"
        if 100 <= row_count <= 400:
            return "minute"
        return "unknown"

    def _normalize_flow_columns(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[str], Dict]:
        df_copy = df.copy()
        meta: Dict = {
            "direction_source": "unknown",
            "data_granularity": "unknown",
        }

        if '成交额(元)' not in df_copy.columns:
            if 'amount' in df_copy.columns:
                df_copy['成交额(元)'] = df_copy['amount']
            elif '成交额' in df_copy.columns:
                df_copy['成交额(元)'] = df_copy['成交额']
            elif '成交金额' in df_copy.columns:
                df_copy['成交额(元)'] = df_copy['成交金额']
            else:
                return df_copy, "Missing transaction amount data"

        df_copy['成交额(元)'] = pd.to_numeric(df_copy['成交额(元)'], errors='coerce').fillna(0)

        if '性质' not in df_copy.columns:
            if 'type' in df_copy.columns:
                df_copy['性质'] = df_copy['type']
                meta["direction_source"] = "字段映射"
            elif '买卖盘性质' in df_copy.columns:
                df_copy['性质'] = df_copy['买卖盘性质']
                meta["direction_source"] = "字段映射"
            elif 'price_change' in df_copy.columns:
                df_copy['性质'] = df_copy['price_change'].apply(
                    lambda x: '买盘' if x > 0 else ('卖盘' if x < 0 else '中性盘')
                )
                meta["direction_source"] = "价格变化推断"
            elif '收盘' in df_copy.columns:
                df_copy['price_change'] = df_copy['收盘'].diff().fillna(0)
                df_copy['性质'] = df_copy['price_change'].apply(
                    lambda x: '买盘' if x > 0 else ('卖盘' if x < 0 else '中性盘')
                )
                meta["direction_source"] = "价格变化推断"
            elif '成交价格' in df_copy.columns:
                df_copy['price_change'] = df_copy['成交价格'].diff().fillna(0)
                df_copy['性质'] = df_copy['price_change'].apply(
                    lambda x: '买盘' if x > 0 else ('卖盘' if x < 0 else '中性盘')
                )
                meta["direction_source"] = "价格变化推断"
            else:
                df_copy['性质'] = '中性盘'
                meta["direction_source"] = "默认中性"
        else:
            meta["direction_source"] = "原始买卖方向"

        meta["data_granularity"] = self._infer_granularity(df_copy)
        return df_copy, None, meta

    def _get_large_order_threshold(self, df: pd.DataFrame, granularity: str) -> Tuple[float, str]:
        if granularity == "minute":
            quantile_threshold = float(df['成交额(元)'].quantile(0.9))
            if np.isnan(quantile_threshold):
                return self.large_order_threshold, "fixed_fallback"
            return max(self.large_order_threshold, quantile_threshold), "quantile_90_or_fixed"
        return self.large_order_threshold, "fixed"

    def calculate_flow_series(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成逐笔净流入与累计净流入序列（用于图表对比）
        """
        if df.empty:
            return df.copy()

        df_flow, error, _meta = self._normalize_flow_columns(df)
        if error:
            return pd.DataFrame()

        if '时间' not in df_flow.columns:
            for time_col in ['成交时间', 'time', 'datetime', '时间戳']:
                if time_col in df_flow.columns:
                    df_flow = df_flow.rename(columns={time_col: '时间'})
                    break

        if '时间' in df_flow.columns:
            df_flow['时间'] = pd.to_datetime(df_flow['时间'], errors='coerce')
            df_flow = df_flow.dropna(subset=['时间']).sort_values('时间')

        nature = df_flow['性质'].astype(str)
        df_flow['净流入额'] = 0.0
        df_flow.loc[nature.str.contains('买'), '净流入额'] = df_flow['成交额(元)']
        df_flow.loc[nature.str.contains('卖'), '净流入额'] = -df_flow['成交额(元)']
        df_flow['累计净流入'] = df_flow['净流入额'].cumsum()

        return df_flow
    
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

        df, error, meta = self._normalize_flow_columns(df)
        if error:
            return {"error": error}

        granularity = meta.get("data_granularity", "unknown")
        threshold, threshold_note = self._get_large_order_threshold(df, granularity)

        # 1. 划分资金类型 (根据阈值)
        # 主力资金: >= threshold
        mask_main = df['成交额(元)'] >= threshold
        # 散户资金: < threshold
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
            "flow_quality": {
                "direction_source": meta.get("direction_source", "unknown"),
                "data_granularity": granularity,
                "large_order_threshold": float(threshold),
                "large_order_threshold_note": threshold_note,
            },
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
