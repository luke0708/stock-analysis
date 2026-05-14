"""
AI 投顾建议复盘日志 — SQLite 持久化。
记录每次 AI 建议，T+1/T+5 自动回填实际涨跌幅。
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "advice_journal.db"

_DDL = """
CREATE TABLE IF NOT EXISTS advice_log (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at            TEXT    NOT NULL,
    stock_code            TEXT    NOT NULL,
    stock_name            TEXT,
    prompt_version        TEXT    NOT NULL,
    focus                 TEXT,
    advice_mode           TEXT,
    analysis_date         TEXT,
    input_snapshot_json   TEXT    NOT NULL,
    advice_text           TEXT    NOT NULL,
    advice_label          TEXT,
    actual_next_day_pct   REAL,
    actual_5d_pct         REAL,
    review_status         TEXT    DEFAULT 'pending'
)
"""


class AdviceJournal:
    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(_DDL)

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def record_advice(
        self,
        stock_code: str,
        stock_name: str,
        prompt_version: str,
        focus: str,
        advice_mode: str,
        context_snapshot: Dict,
        advice_text: str,
        analysis_date: Optional[str] = None,
    ) -> int:
        """保存一次 AI 建议，返回新记录的 id。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO advice_log
                  (created_at, stock_code, stock_name, prompt_version,
                   focus, advice_mode, analysis_date,
                   input_snapshot_json, advice_text, review_status)
                VALUES (?,?,?,?,?,?,?,?,?,'pending')
                """,
                (
                    now,
                    stock_code,
                    stock_name,
                    prompt_version,
                    focus,
                    advice_mode,
                    analysis_date,
                    json.dumps(context_snapshot, ensure_ascii=False),
                    advice_text,
                ),
            )
            return cur.lastrowid

    # ------------------------------------------------------------------
    # T+1 / T+5 回填
    # ------------------------------------------------------------------

    def follow_up_pending(self) -> int:
        """拉取 pending 记录的 T+1、T+5 实际涨跌幅，返回更新数量。"""
        try:
            from stock_analysis.data.providers.akshare_provider import AkShareProvider
        except ImportError:
            logger.error("AkShareProvider 不可用，跳过回填")
            return 0

        updated = 0
        today = date.today()

        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, stock_code, analysis_date FROM advice_log WHERE review_status='pending'"
            ).fetchall()

        for row in rows:
            row_id = row["id"]
            code = row["stock_code"]
            analysis_date_str = row["analysis_date"]

            if not analysis_date_str:
                continue
            try:
                t0 = date.fromisoformat(analysis_date_str)
            except ValueError:
                continue

            t1 = t0 + timedelta(days=1)
            t5 = t0 + timedelta(days=7)  # 用 7 日窗口覆盖周末，取实际第 5 交易日

            if t1 > today:
                continue  # T+1 未到，跳过

            try:
                provider = AkShareProvider()
                hist = provider.get_history_data(
                    code,
                    start_date=t0,
                    end_date=min(t5, today),
                )
                if hist.empty:
                    continue

                hist = hist.sort_values("日期").reset_index(drop=True)
                # 统一日期列为 date 字符串，方便比较
                hist["_date_str"] = hist["日期"].astype(str).str[:10]

                # 找 T0 收盘价
                t0_rows = hist[hist["_date_str"] == str(t0)]
                if t0_rows.empty:
                    continue
                close_t0 = float(t0_rows.iloc[0]["收盘"])

                def _pct(row_df):
                    if row_df.empty:
                        return None
                    return round((float(row_df.iloc[0]["收盘"]) / close_t0 - 1) * 100, 2)

                t1_rows = hist[hist["_date_str"] >= str(t1)]
                t1_pct = _pct(t1_rows.iloc[[0]] if not t1_rows.empty else t1_rows)

                t5_rows = hist.tail(1) if len(hist) >= 5 else hist
                t5_pct = _pct(t5_rows)

                status = "reviewed" if t1_pct is not None else "pending"

                with self._conn() as conn:
                    conn.execute(
                        """
                        UPDATE advice_log
                           SET actual_next_day_pct=?, actual_5d_pct=?, review_status=?
                         WHERE id=?
                        """,
                        (t1_pct, t5_pct, status, row_id),
                    )
                if status == "reviewed":
                    updated += 1
            except Exception as exc:
                logger.warning("回填失败 %s row_id=%s: %s", code, row_id, exc)

        return updated

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_history(self, limit: int = 100) -> List[Dict]:
        """返回历史记录列表（最新在前）。"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM advice_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_summary_stats(self) -> Dict:
        """按 prompt_version 统计命中率（T+1 涨跌幅均值、已复盘数）。"""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT prompt_version,
                       COUNT(*) AS total,
                       SUM(CASE WHEN review_status='reviewed' THEN 1 ELSE 0 END) AS reviewed,
                       AVG(actual_next_day_pct) AS avg_t1_pct,
                       AVG(actual_5d_pct) AS avg_t5_pct
                  FROM advice_log
                 GROUP BY prompt_version
                 ORDER BY prompt_version DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]
