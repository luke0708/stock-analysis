"""
stock_cache.db 数据访问层。

对上层透明：先查 DB，缺数据才调 AkShare，结果写回 DB。
新鲜度策略：
  - 日线 T-1 及之前：永久缓存
  - 日线当日盘中（< 15:05）：不入库
  - 日线当日收盘后（>= 15:05）：入库为 final
  - 分钟线：历史永久；当日不入库
  - 股票元信息：每天刷新 1 次
  - 新闻：1 小时 TTL
  - L2 衍生快照：按 analysis_date 永久，同日重算覆盖
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from stock_analysis.data.cache_schema import DDL_STATEMENTS, SCHEMA_VERSION

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "stock_cache.db"

# 当日数据在 15:05 后才算 final
_MARKET_CLOSE_HOUR = 15
_MARKET_CLOSE_MINUTE = 5


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> date:
    return date.today()


def _is_intraday() -> bool:
    """当前时间是否处于今日盘中（未收盘 final）。"""
    now = datetime.now()
    cutoff = now.replace(hour=_MARKET_CLOSE_HOUR, minute=_MARKET_CLOSE_MINUTE, second=0, microsecond=0)
    return now < cutoff


class CacheStore:
    """统一数据访问入口，透明缓存 + L2 持久化。"""

    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self.db_path = db_path
        self._init_schema()
        self._enable_wal()

    # ── 连接管理 ────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            for stmt in DDL_STATEMENTS:
                conn.execute(stmt)
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            if current < SCHEMA_VERSION:
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def _enable_wal(self) -> None:
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")

    # ── 元数据辅助 ──────────────────────────────────────────────────────

    def _get_meta(self, key: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM cache_meta WHERE key=?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def _set_meta(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_meta(key, value, updated_at) VALUES(?,?,?)",
                (key, value, _now_str()),
            )

    # ── L1：日线 OHLC ────────────────────────────────────────────────────

    def get_daily(
        self,
        code: str,
        start: date,
        end: date,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """先查 DB，缺失区间调 AkShare 补全后返回完整结果。"""
        # 确定需要的日期范围（排除当日盘中）
        cache_end = end
        skip_today = end >= _today() and _is_intraday()
        if skip_today:
            cache_end = _today() - timedelta(days=1)

        cached = self._query_daily_db(code, start, cache_end, adjust)
        missing = self._compute_missing_dates(cached, start, cache_end)

        if missing:
            fetched = self._fetch_daily_from_akshare(code, missing[0], missing[-1])
            if not fetched.empty:
                # 盘中当日数据不入库
                if skip_today or end < _today():
                    rows_to_save = fetched
                else:
                    today_str = str(_today())
                    rows_to_save = fetched[fetched["date"].astype(str) < today_str]
                if not rows_to_save.empty:
                    self._save_daily_to_db(code, rows_to_save, adjust)
                cached = self._query_daily_db(code, start, cache_end, adjust)

        # 当日盘中：追加实时日线（不入库）
        if end >= _today() and _is_intraday():
            today_df = self._fetch_daily_from_akshare(code, _today(), _today())
            if not today_df.empty:
                cached = pd.concat([cached, today_df], ignore_index=True).drop_duplicates(
                    subset=["date"], keep="last"
                )

        return cached.sort_values("date").reset_index(drop=True) if not cached.empty else cached

    def _query_daily_db(
        self, code: str, start: date, end: date, adjust: str
    ) -> pd.DataFrame:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT date, open, high, low, close, volume, amount
                  FROM daily_ohlc
                 WHERE code=? AND adjust_flag=?
                   AND date >= ? AND date <= ?
                 ORDER BY date
                """,
                (code, adjust, str(start), str(end)),
            ).fetchall()
        if not rows:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount"])
        df = pd.DataFrame([dict(r) for r in rows])
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df

    def _compute_missing_dates(
        self, cached: pd.DataFrame, start: date, end: date
    ) -> List[date]:
        """返回 [start, end] 中缺失的日期（只检查首尾连续性，不逐日校验）。"""
        if cached.empty:
            return [start]  # 后续 fetch 用 start→end 整段
        cached_min = cached["date"].min()
        cached_max = cached["date"].max()
        missing = []
        if cached_min > start:
            missing.append(start)
        if cached_max < end:
            missing.append(cached_max + timedelta(days=1))
        return missing

    def _fetch_daily_from_akshare(
        self, code: str, start: date, end: date
    ) -> pd.DataFrame:
        try:
            from stock_analysis.data.providers.akshare_provider import AkShareProvider
            provider = AkShareProvider()
            df = provider.get_history_data(code, start_date=start, end_date=end)
            if df.empty:
                return pd.DataFrame()
            # 统一列名为英文
            col_map = {
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume", "成交额": "amount",
            }
            df = df.rename(columns=col_map)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            for c in ["open", "high", "low", "close", "volume", "amount"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            return df[["date", "open", "high", "low", "close", "volume", "amount"]].dropna(subset=["date", "close"])
        except Exception as exc:
            logger.warning("fetch_daily failed %s %s-%s: %s", code, start, end, exc)
            return pd.DataFrame()

    def _save_daily_to_db(
        self, code: str, df: pd.DataFrame, adjust: str
    ) -> None:
        now = _now_str()
        records = []
        for _, row in df.iterrows():
            records.append((
                code,
                str(row.get("date", "")),
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row.get("close"),
                row.get("volume"),
                row.get("amount"),
                adjust,
                "akshare",
                now,
            ))
        with self._conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO daily_ohlc
                  (code, date, open, high, low, close, volume, amount,
                   adjust_flag, source, fetched_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                records,
            )
        logger.debug("saved %d daily rows for %s", len(records), code)

    # ── L1：新闻 ────────────────────────────────────────────────────────

    def get_news(
        self, code: str, limit: int = 10, ttl_minutes: int = 60
    ) -> pd.DataFrame:
        """1 小时 TTL；过期则重拉并更新。"""
        meta_key = f"news_{code}_fetched_at"
        last_fetch = self._get_meta(meta_key)
        expired = True
        if last_fetch:
            try:
                delta = datetime.now() - datetime.strptime(last_fetch, "%Y-%m-%d %H:%M:%S")
                expired = delta.total_seconds() > ttl_minutes * 60
            except ValueError:
                pass

        if expired:
            self._refresh_news(code)
            self._set_meta(meta_key, _now_str())

        return self._query_news_db(code, limit)

    def _refresh_news(self, code: str) -> None:
        try:
            from stock_analysis.data.news_provider import StockNewsProvider
            df = StockNewsProvider.get_stock_news(code, limit=30)
            if df.empty:
                return
            now = _now_str()
            # AkShare stock_news_em 返回列：新闻标题 / 发布时间 / 新闻内容（可能缺失）
            col_map = {
                "新闻标题": "title",
                "发布时间": "published_at",
                "新闻内容": "summary",
                "新闻来源": "source",
            }
            df = df.rename(columns=col_map)
            records = []
            for _, row in df.iterrows():
                pub = str(row.get("published_at", "")) or now
                title = str(row.get("title", ""))
                if not title:
                    continue
                records.append((
                    code,
                    pub,
                    title,
                    str(row.get("summary", "")),
                    str(row.get("source", "")),
                    now,
                ))
            with self._conn() as conn:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO stock_news
                      (code, published_at, title, summary, source, fetched_at)
                    VALUES (?,?,?,?,?,?)
                    """,
                    records,
                )
            logger.debug("refreshed %d news for %s", len(records), code)
        except Exception as exc:
            logger.warning("refresh_news failed %s: %s", code, exc)

    def _query_news_db(self, code: str, limit: int) -> pd.DataFrame:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT published_at, title, summary, source
                  FROM stock_news
                 WHERE code=?
                 ORDER BY published_at DESC, id DESC
                 LIMIT ?
                """,
                (code, limit),
            ).fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        df = df.rename(columns={
            "published_at": "发布时间",
            "title": "新闻标题",
            "summary": "新闻内容",
            "source": "新闻来源",
        })
        return df

    # ── L1：股票元信息 ────────────────────────────────────────────────────

    def get_stock_meta(self, code: str) -> Optional[Dict]:
        """每天刷新 1 次。"""
        meta_key = f"meta_{code}_updated_at"
        last_update = self._get_meta(meta_key)
        today_str = str(_today())
        if last_update and last_update[:10] == today_str:
            return self._query_meta_db(code)

        info = self._fetch_meta_from_akshare(code)
        if info:
            self._save_meta_to_db(code, info)
            self._set_meta(meta_key, _now_str())
        return self._query_meta_db(code)

    def _fetch_meta_from_akshare(self, code: str) -> Optional[Dict]:
        try:
            import akshare as ak
            df = ak.stock_individual_info_em(symbol=code)
            if df.empty:
                return None
            result: Dict = {}
            for _, row in df.iterrows():
                key = str(row.iloc[0])
                val = str(row.iloc[1])
                result[key] = val
            name = result.get("股票简称", result.get("名称", ""))
            industry = result.get("行业", "")
            market = result.get("上市市场", "")
            return {"code": code, "name": name, "industry": industry, "market": market}
        except Exception as exc:
            logger.warning("fetch_meta failed %s: %s", code, exc)
            return None

    def _save_meta_to_db(self, code: str, info: Dict) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO stock_meta(code, name, industry, market, updated_at)
                VALUES (?,?,?,?,?)
                """,
                (
                    code,
                    info.get("name", ""),
                    info.get("industry", ""),
                    info.get("market", ""),
                    _now_str(),
                ),
            )

    def _query_meta_db(self, code: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM stock_meta WHERE code=?", (code,)
            ).fetchone()
        return dict(row) if row else None

    # ── L2：trend_signal 快照 ─────────────────────────────────────────────

    def save_trend_signal(
        self, code: str, analysis_date: str, snapshot: Dict
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trend_signal_snapshot
                  (code, analysis_date, snapshot_json, created_at)
                VALUES (?,?,?,?)
                """,
                (code, analysis_date, json.dumps(snapshot, ensure_ascii=False), _now_str()),
            )

    def get_trend_signal(
        self, code: str, analysis_date: str
    ) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT snapshot_json FROM trend_signal_snapshot
                 WHERE code=? AND analysis_date=?
                """,
                (code, analysis_date),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["snapshot_json"])
        except json.JSONDecodeError:
            return None

    # ── L2：资金流汇总 ────────────────────────────────────────────────────

    def save_flow_summary(
        self, code: str, analysis_date: str, summary: Dict
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO flow_summary_daily
                  (code, date, net_inflow, large_order_count,
                   buy_amount, sell_amount, neutral_amount,
                   summary_json, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    code,
                    analysis_date,
                    summary.get("net_inflow"),
                    summary.get("large_order_count"),
                    summary.get("buy_amount"),
                    summary.get("sell_amount"),
                    summary.get("neutral_amount"),
                    json.dumps(summary, ensure_ascii=False),
                    _now_str(),
                ),
            )

    def get_flow_summary(
        self, code: str, analysis_date: str
    ) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT summary_json FROM flow_summary_daily
                 WHERE code=? AND date=?
                """,
                (code, analysis_date),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["summary_json"])
        except json.JSONDecodeError:
            return None

    # ── L2：价格区间快照 ──────────────────────────────────────────────────

    def save_price_range(
        self, code: str, analysis_date: str, analysis: Dict
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO price_range_snapshot
                  (code, analysis_date, support_zone, resistance_zone,
                   analysis_json, created_at)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    code,
                    analysis_date,
                    analysis.get("support_zone") or analysis.get("support"),
                    analysis.get("resistance_zone") or analysis.get("resistance"),
                    json.dumps(analysis, ensure_ascii=False),
                    _now_str(),
                ),
            )

    def get_price_range(
        self, code: str, analysis_date: str
    ) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT analysis_json FROM price_range_snapshot
                 WHERE code=? AND analysis_date=?
                """,
                (code, analysis_date),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["analysis_json"])
        except json.JSONDecodeError:
            return None

    # ── L4：训练标签 ──────────────────────────────────────────────────────

    def upsert_label(self, code: str, label_date: str, **kwargs) -> None:
        """插入或更新 labels 行，kwargs 对应各 pct 字段。"""
        fields = ["next_1d_pct", "next_5d_pct", "next_20d_pct",
                  "next_1d_high_pct", "next_1d_low_pct"]
        set_parts = ", ".join(f"{f}=?" for f in fields if f in kwargs)
        vals = [kwargs[f] for f in fields if f in kwargs]
        if not set_parts:
            return
        vals += [_now_str(), code, label_date]
        with self._conn() as conn:
            conn.execute(
                f"""
                INSERT INTO labels(code, date, {', '.join(f for f in fields if f in kwargs)}, backfilled_at)
                VALUES ({', '.join(['?'] * (len(vals) - 2))}, ?)
                ON CONFLICT(code, date) DO UPDATE SET
                  {set_parts}, backfilled_at=?
                """,
                vals,
            )

    def query_labels(
        self, since: date, until: date
    ) -> pd.DataFrame:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM labels
                 WHERE date >= ? AND date <= ?
                 ORDER BY date, code
                """,
                (str(since), str(until)),
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()

    # ── 训练数据 join（占位） ──────────────────────────────────────────────

    def query_training_join(
        self,
        since: date,
        until: date,
        features: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        返回 L2 特征 JOIN L4 标签的宽表，供训练集导出用。
        本轮仅实现基础 trend_signal + labels join，其余留占位。
        """
        labels_df = self.query_labels(since, until)
        if labels_df.empty:
            return pd.DataFrame()

        with self._conn() as conn:
            ts_rows = conn.execute(
                """
                SELECT code, analysis_date, snapshot_json
                  FROM trend_signal_snapshot
                 WHERE analysis_date >= ? AND analysis_date <= ?
                """,
                (str(since), str(until)),
            ).fetchall()

        if not ts_rows:
            return labels_df

        ts_df = pd.DataFrame([dict(r) for r in ts_rows])
        ts_df = ts_df.rename(columns={"analysis_date": "date"})
        merged = labels_df.merge(ts_df, on=["code", "date"], how="left")
        return merged
