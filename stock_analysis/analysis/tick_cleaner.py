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
                df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")

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
            df_clean["成交额(元)"] = pd.to_numeric(df_clean["成交额(元)"], errors="coerce")

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
            df_clean["性质"] = df_clean["性质"].astype("string").str.strip()
            df_clean["性质"] = df_clean["性质"].where(df_clean["性质"] != "", pd.NA)
            df_clean["性质"] = df_clean["性质"].apply(
                lambda x: "买盘"
                if isinstance(x, str) and (x in {"B", "买"} or "买" in x)
                else (
                    "卖盘"
                    if isinstance(x, str) and (x in {"S", "卖"} or "卖" in x)
                    else ("中性盘" if isinstance(x, str) and "中性" in x else x)
                )
            )
            valid_natures = {"买盘", "卖盘", "中性盘"}
            unknown_mask = ~df_clean["性质"].isin(valid_natures)
            df_clean.loc[unknown_mask, "性质"] = pd.NA

        df_clean = df_clean.sort_values("时间")
        df_clean["性质来源"] = "raw"
        nature_series = df_clean["性质"].astype("string")
        missing_mask = nature_series.isna() | (nature_series.str.strip() == "")
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
                threshold = 0.0005
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

        if not df_clean.empty:
            buy_sell_count = df_clean["性质"].isin(["买盘", "卖盘"]).sum()
            if buy_sell_count == 0:
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
                    threshold = 0.0005
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
        afternoon_mask = (time_str >= "13:00") & (time_str <= "15:00")
        df_clean = df_clean[morning_mask | afternoon_mask]
        if df_clean.empty:
            quality_flags.append("non_trading_time")

        if not df_clean.empty:
            df_clean["价格变化率"] = df_clean["成交价格"].pct_change().abs()
            df_clean["是否极端跳变"] = df_clean["价格变化率"] > 5.0

        logger.info("Tick数据清洗完成: %s rows", len(df_clean))
        return df_clean.reset_index(drop=True), quality_flags, auction_df.reset_index(drop=True), inferred_ratio
