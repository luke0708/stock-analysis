from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from stock_analysis.core.config import settings
from stock_analysis.tasks.job_models import JobStatus


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,
    stock_code TEXT NOT NULL,
    report_type TEXT NOT NULL DEFAULT 'simple',
    status TEXT NOT NULL,
    requested_by TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,
    query_id TEXT,
    analysis_time TEXT,
    source TEXT NOT NULL DEFAULT 'original_algo',
    raw_result_json TEXT NOT NULL,
    context_snapshot_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created
ON analysis_jobs(status, created_at);

CREATE INDEX IF NOT EXISTS idx_jobs_stock_created
ON analysis_jobs(stock_code, created_at);

CREATE INDEX IF NOT EXISTS idx_results_query_id
ON analysis_results(query_id);

CREATE INDEX IF NOT EXISTS idx_results_created
ON analysis_results(created_at);
"""


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class JobStore:
    """SQLite-backed task store for async single-stock analysis jobs."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else (settings.DATA_DIR / "analysis_tasks.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def create_job(
        self,
        stock_code: str,
        report_type: str = "simple",
        requested_by: str = "beta_ui",
        job_id: Optional[str] = None,
    ) -> str:
        if not stock_code or len(stock_code.strip()) != 6 or not stock_code.strip().isdigit():
            raise ValueError("stock_code must be a 6-digit code")

        report_type = (report_type or "simple").strip().lower()
        if report_type not in {"simple", "detailed"}:
            raise ValueError("report_type must be 'simple' or 'detailed'")

        final_job_id = job_id or uuid.uuid4().hex
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analysis_jobs (
                    job_id, stock_code, report_type, status, requested_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    final_job_id,
                    stock_code.strip(),
                    report_type,
                    JobStatus.PENDING.value,
                    requested_by,
                    now,
                ),
            )
            conn.commit()
        return final_job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM analysis_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        sql = "SELECT * FROM analysis_jobs"
        params: List[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def mark_running(self, job_id: str) -> bool:
        now = _now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE analysis_jobs
                SET status = ?, started_at = ?, error_message = NULL
                WHERE job_id = ? AND status IN (?, ?)
                """,
                (
                    JobStatus.RUNNING.value,
                    now,
                    job_id,
                    JobStatus.PENDING.value,
                    JobStatus.FAILED.value,
                ),
            )
            conn.commit()
        return cur.rowcount > 0

    def claim_next_pending_job(self) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM analysis_jobs
                WHERE status = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (JobStatus.PENDING.value,),
            ).fetchone()
            if not row:
                conn.commit()
                return None

            now = _now_iso()
            conn.execute(
                """
                UPDATE analysis_jobs
                SET status = ?, started_at = ?, error_message = NULL
                WHERE job_id = ?
                """,
                (JobStatus.RUNNING.value, now, row["job_id"]),
            )
            conn.commit()

        claimed = dict(row)
        claimed["status"] = JobStatus.RUNNING.value
        claimed["started_at"] = now
        claimed["error_message"] = None
        return claimed

    def mark_succeeded(
        self,
        job_id: str,
        *,
        query_id: Optional[str],
        analysis_time: Optional[str],
        raw_result: Dict[str, Any],
        context_snapshot: Optional[Dict[str, Any]],
        source: str = "original_algo",
        duration_ms: Optional[int] = None,
    ) -> bool:
        now = _now_iso()
        raw_json = json.dumps(raw_result or {}, ensure_ascii=False)
        ctx_json = json.dumps(context_snapshot, ensure_ascii=False) if context_snapshot is not None else None

        with self._connect() as conn:
            conn.execute("BEGIN")
            conn.execute(
                """
                INSERT INTO analysis_results (
                    job_id, query_id, analysis_time, source, raw_result_json, context_snapshot_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    query_id = excluded.query_id,
                    analysis_time = excluded.analysis_time,
                    source = excluded.source,
                    raw_result_json = excluded.raw_result_json,
                    context_snapshot_json = excluded.context_snapshot_json,
                    created_at = excluded.created_at
                """,
                (job_id, query_id, analysis_time, source, raw_json, ctx_json, now),
            )
            cur = conn.execute(
                """
                UPDATE analysis_jobs
                SET status = ?, finished_at = ?, duration_ms = ?, error_message = NULL
                WHERE job_id = ?
                """,
                (JobStatus.SUCCEEDED.value, now, duration_ms, job_id),
            )
            conn.commit()
        return cur.rowcount > 0

    def mark_failed(self, job_id: str, error_message: str, duration_ms: Optional[int] = None) -> bool:
        now = _now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE analysis_jobs
                SET status = ?, finished_at = ?, duration_ms = ?, retry_count = retry_count + 1, error_message = ?
                WHERE job_id = ?
                """,
                (JobStatus.FAILED.value, now, duration_ms, (error_message or "").strip()[:2000], job_id),
            )
            conn.commit()
        return cur.rowcount > 0

    def get_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM analysis_results WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if not row:
            return None

        data = dict(row)
        try:
            data["raw_result"] = json.loads(data.pop("raw_result_json"))
        except Exception:
            data["raw_result"] = {}
        ctx_text = data.pop("context_snapshot_json", None)
        if ctx_text:
            try:
                data["context_snapshot"] = json.loads(ctx_text)
            except Exception:
                data["context_snapshot"] = None
        else:
            data["context_snapshot"] = None
        return data

    def get_job_with_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self.get_job(job_id)
        if not job:
            return None
        result = self.get_result(job_id)
        return {
            "job": job,
            "result": result,
        }

    def delete_job(self, job_id: str, *, delete_result: bool = True) -> Dict[str, int]:
        """Delete one job and (optionally) its persisted result snapshot."""
        if not job_id:
            return {"job_deleted": 0, "result_deleted": 0}

        with self._connect() as conn:
            conn.execute("BEGIN")
            result_deleted = 0
            if delete_result:
                cur_result = conn.execute(
                    "DELETE FROM analysis_results WHERE job_id = ?",
                    (job_id,),
                )
                result_deleted = int(cur_result.rowcount or 0)

            cur_job = conn.execute(
                "DELETE FROM analysis_jobs WHERE job_id = ?",
                (job_id,),
            )
            job_deleted = int(cur_job.rowcount or 0)
            conn.commit()

        return {"job_deleted": job_deleted, "result_deleted": result_deleted}


__all__ = ["JobStore", "JobStatus"]
