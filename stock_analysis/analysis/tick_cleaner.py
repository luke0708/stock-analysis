import logging
from datetime import date
from typing import List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class TickDataCleaner:
    """Tick 数据清洗器，仅处理当日实时场景。"""

    def __init__(self, trading_start: str = "09:30", trading_end: str = "15:00"):
        self.trading_start = trading_start
        self.trading_end = trading_end

    def clean(
        self, df: pd.DataFrame, current_date: date
    ) -> Tuple[pd.DataFrame, List[str], pd.DataFrame, float]:
        quality_flags: List[str] = []
        if df is None or df.empty:
            return pd.DataFrame(), ["empty_tick"], pd.DataFrame(), 0.0

        df_clean = df.copy()
        df_clean.columns = df_clean.columns.astype(str).str.strip()

        def _to_numeric(series: pd.Series) -> pd.Series:
            s = series.astype(str).str.replace(",", "", regex=False)
            s = s.str.replace("，", "", regex=False).str.strip()
            multiplier = pd.Series(1.0, index=s.index)
            if s.str.contains("万").any():
                multiplier[s.str.endswith("万")] = 1e4
                s = s.str.replace("万", "", regex=False)
            if s.str.contains("亿").any():
                multiplier[s.str.endswith("亿")] = 1e8
                s = s.str.replace("亿", "", regex=False)
            return pd.to_numeric(s, errors="coerce") * multiplier

        col_map = {
            "成交时间": "时间",
            "time": "时间",
            "datetime": "时间",
            "成交价格": "成交价格",
            "价格": "成交价格",
            "最新价": "成交价格",
            "price": "成交价格",
            "成交量": "成交量",
            "vol": "成交量",
            "volume": "成交量",
            "成交额": "成交额",
            "成交金额": "成交额",
            "amount": "成交额",
            "性质": "性质",
            "type": "性质",
            "买卖盘性质": "性质",
        }
        df_clean = df_clean.rename(columns=col_map)

        if "时间" not in df_clean.columns:
            return pd.DataFrame(), ["missing_time"], pd.DataFrame(), 0.0

        time_series = df_clean["时间"].astype(str).str.strip()
        current_date_str = current_date.strftime("%Y-%m-%d")
        has_date = time_series.str.contains(r"\d{4}[-/]\d{2}[-/]\d{2}")
        df_clean["时间"] = time_series.where(
            has_date,
            current_date_str + " " + time_series,
        )
        df_clean["时间"] = pd.to_datetime(df_clean["时间"], errors="coerce")
        before_len = len(df_clean)
        df_clean = df_clean.dropna(subset=["时间"])
        if len(df_clean) < before_len:
            quality_flags.append("invalid_time")

        for col in ["成交价格", "成交量", "成交额", "成交金额"]:
            if col in df_clean.columns:
                df_clean[col] = _to_numeric(df_clean[col])

        if "成交价格" not in df_clean.columns:
            quality_flags.append("missing_price")
            return pd.DataFrame(), quality_flags, pd.DataFrame(), 0.0

        df_clean = df_clean[df_clean["成交价格"] > 0]
        if "成交量" in df_clean.columns:
            df_clean = df_clean[df_clean["成交量"] >= 0]
            df_clean["成交量(手)"] = df_clean["成交量"]
            df_clean["成交量"] = df_clean["成交量"] * 100
            quality_flags.append("volume_assumed_hands")
            quality_flags.append("volume_unit_shares")
        else:
            quality_flags.append("missing_volume")
            df_clean["成交量"] = 0

        if "成交额(元)" not in df_clean.columns:
            if "成交额" in df_clean.columns:
                df_clean["成交额(元)"] = df_clean["成交额"]
            elif "成交金额" in df_clean.columns:
                df_clean["成交额(元)"] = df_clean["成交金额"]
            else:
                df_clean["成交额(元)"] = pd.NA

        if "成交额(元)" in df_clean.columns:
            df_clean["成交额(元)"] = _to_numeric(df_clean["成交额(元)"])

        if "成交额(元)" in df_clean.columns and "成交价格" in df_clean.columns:
            computed_amount = df_clean["成交价格"] * df_clean["成交量"]
            fill_mask = df_clean["成交额(元)"].isna()
            df_clean.loc[fill_mask, "成交额(元)"] = computed_amount[fill_mask]
            zero_mask = df_clean["成交额(元)"] <= 0
            df_clean.loc[zero_mask & (computed_amount > 0), "成交额(元)"] = computed_amount[zero_mask]

        if "成交额(元)" in df_clean.columns:
            df_clean["成交额(元)"] = df_clean["成交额(元)"].fillna(0)
        else:
            quality_flags.append("missing_amount")
            df_clean["成交额(元)"] = 0

        inferred_ratio = 0.0
        if "性质" not in df_clean.columns:
            quality_flags.append("missing_nature")
            df_clean["性质"] = pd.NA
        else:
            nature_series = df_clean["性质"].astype("string").str.strip()
            nature_map = {
                "买盘": "买盘",
                "买": "买盘",
                "B": "买盘",
                "b": "买盘",
                "卖盘": "卖盘",
                "卖": "卖盘",
                "S": "卖盘",
                "s": "卖盘",
                "中性盘": "中性盘",
                "中性": "中性盘",
                "N": "中性盘",
                "n": "中性盘",
                "nan": pd.NA,
                "NaN": pd.NA,
                "None": pd.NA,
                "<NA>": pd.NA,
                "": pd.NA,
            }
            nature_series = nature_series.replace(nature_map)
            nature_series = nature_series.where(nature_series != "", pd.NA)

            nature_numeric = pd.to_numeric(nature_series, errors="coerce")
            if nature_numeric.notna().any():
                nature_series.loc[nature_numeric > 0] = "买盘"
                nature_series.loc[nature_numeric < 0] = "卖盘"
                nature_series.loc[nature_numeric == 0] = "中性盘"

            valid_natures = {"买盘", "卖盘", "中性盘"}
            unknown_mask = ~nature_series.isin(valid_natures) & nature_series.notna()
            if unknown_mask.any():
                contains_buy = nature_series.str.contains("买", na=False)
                contains_sell = nature_series.str.contains("卖", na=False)
                nature_series.loc[unknown_mask & contains_buy] = "买盘"
                nature_series.loc[unknown_mask & contains_sell] = "卖盘"

            unknown_mask = ~nature_series.isin(valid_natures) & nature_series.notna()
            nature_series.loc[unknown_mask] = pd.NA
            df_clean["性质"] = nature_series

            if len(df_clean) > 0:
                valid_ratio = df_clean["性质"].isin(valid_natures).sum() / len(df_clean)
                if valid_ratio < 0.5:
                    quality_flags.append("nature_low_quality")
                    logger.warning("性质字段有效率偏低: %.1f%%", valid_ratio * 100)

        df_clean = df_clean.sort_values("时间")
        df_clean["性质来源"] = "raw"
        nature_series = df_clean["性质"]
        missing_mask = nature_series.isna()
        valid_mask = df_clean["性质"].isin(["买盘", "卖盘", "中性盘"])
        valid_ratio = valid_mask.sum() / len(df_clean) if len(df_clean) > 0 else 0.0
        
        # 修复：只对真正缺失的部分进行推断，不覆盖已有的有效性质
        # 即使有效率低，也只推断那些 NA 或无效的，不能把有效的也覆盖掉
        if valid_ratio < 0.5:
            logger.warning("性质字段有效率偏低: %.1f%%, 将对缺失部分进行推断", valid_ratio * 100)
            quality_flags.append("nature_low_quality_infer")
        
        if missing_mask.any():
            price_delta_col = None
            for col in ["价格变动", "price_change", "price_delta"]:
                if col in df_clean.columns:
                    price_delta_col = col
                    break

            if price_delta_col:
                df_clean[price_delta_col] = pd.to_numeric(df_clean[price_delta_col], errors="coerce").fillna(0)
                inferred = pd.Series("中性盘", index=df_clean.index)
                inferred.loc[df_clean[price_delta_col] > 0] = "买盘"
                inferred.loc[df_clean[price_delta_col] < 0] = "卖盘"
                df_clean.loc[missing_mask, "性质"] = inferred[missing_mask]
                df_clean.loc[missing_mask, "性质来源"] = "inferred"
                inferred_ratio = float(missing_mask.sum() / len(df_clean)) if len(df_clean) > 0 else 0.0
                quality_flags.append("inferred_nature_price_delta")
            elif "成交价格" in df_clean.columns:
                price_change = df_clean["成交价格"].pct_change()
                abs_change = price_change.abs()
                dynamic = abs_change.quantile(0.3)
                if pd.isna(dynamic):
                    dynamic = 0.0
                threshold = max(0.0001, float(dynamic))
                quality_flags.append("inferred_threshold_dynamic")
                inferred = pd.Series("中性盘", index=df_clean.index)
                inferred.loc[price_change > threshold] = "买盘"
                inferred.loc[price_change < -threshold] = "卖盘"
                df_clean.loc[missing_mask, "性质"] = inferred[missing_mask]
                df_clean.loc[missing_mask, "性质来源"] = "inferred"
                inferred_ratio = float(missing_mask.sum() / len(df_clean)) if len(df_clean) > 0 else 0.0
                quality_flags.append("inferred_nature")
            else:
                inferred_ratio = float(missing_mask.sum() / len(df_clean)) if len(df_clean) > 0 else 0.0
        elif len(df_clean) > 0:
            inferred_ratio = float(missing_mask.sum() / len(df_clean))

        # 全零检查：只有在前面没有推断过的情况下才执行
        # 避免覆盖前面已经正确处理的数据
        if not df_clean.empty and inferred_ratio == 0.0:
            buy_sell_count = df_clean["性质"].isin(["买盘", "卖盘"]).sum()
            if buy_sell_count == 0:
                logger.warning("性质字段全是中性盘，启动全量推断")
                price_delta_col = None
                for col in ["价格变动", "price_change", "price_delta"]:
                    if col in df_clean.columns:
                        price_delta_col = col
                        break

                inferred = pd.Series("中性盘", index=df_clean.index)
                if price_delta_col:
                    df_clean[price_delta_col] = pd.to_numeric(
                        df_clean[price_delta_col], errors="coerce"
                    ).fillna(0)
                    inferred.loc[df_clean[price_delta_col] > 0] = "买盘"
                    inferred.loc[df_clean[price_delta_col] < 0] = "卖盘"
                elif "成交价格" in df_clean.columns:
                    price_change = df_clean["成交价格"].pct_change()
                    abs_change = price_change.abs()
                    dynamic_threshold = abs_change.quantile(0.3)
                    if pd.isna(dynamic_threshold):
                        dynamic_threshold = 0.0
                    threshold = max(0.0001, float(dynamic_threshold))
                    inferred.loc[price_change > threshold] = "买盘"
                    inferred.loc[price_change < -threshold] = "卖盘"

                df_clean["性质"] = inferred
                df_clean["性质来源"] = "inferred_all"
                inferred_ratio = 1.0
                quality_flags.append("nature_all_neutral_inferred")


        time_str = df_clean["时间"].dt.strftime("%H:%M")
        auction_mask = (time_str >= "09:15") & (time_str <= "09:25")
        auction_df = df_clean[auction_mask].copy()
        df_clean = df_clean[~auction_mask]

        time_str = df_clean["时间"].dt.strftime("%H:%M")
        morning_mask = (time_str >= "09:30") & (time_str <= "11:30")
        # 严格过滤：虽然字符串匹配到15:00，但后续要进一步过滤15:00:00之后的数据
        afternoon_mask = (time_str >= "13:00") & (time_str <= "15:00")
        df_clean = df_clean[morning_mask | afternoon_mask]

        if not df_clean.empty:
            # 1. 严格过滤 15:00:00 之后的数据 (盘后固定价格交易等)
            # 注意：这里保留 15:00:00 本身(收盘竞价)，但剔除 15:00:01 及以后
            # 有些数据源收盘竞价时间可能是 15:00:00
            closing_time = df_clean["时间"].dt.normalize() + pd.Timedelta(hours=15)
            # 使用 mask 过滤，保留 时间 <= 15:00:00 的数据（在下午时段）
            valid_time_mask = (
                (df_clean["时间"].dt.hour < 15) | 
                ((df_clean["时间"].dt.hour == 15) & (df_clean["时间"].dt.minute == 0) & (df_clean["时间"].dt.second == 0))
            )
            df_clean = df_clean[valid_time_mask]


        if df_clean.empty:
            quality_flags.append("non_trading_time")

        if not df_clean.empty:
            df_clean["价格变化率"] = df_clean["成交价格"].pct_change().abs()
            df_clean["是否极端跳变"] = df_clean["价格变化率"] > 5.0

        logger.info("Tick数据清洗完成: %s rows", len(df_clean))
        return df_clean.reset_index(drop=True), quality_flags, auction_df.reset_index(drop=True), inferred_ratio
