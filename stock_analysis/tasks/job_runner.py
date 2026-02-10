from __future__ import annotations

import time
from typing import Any, Dict, Optional

from stock_analysis.bridge import run_original_single_stock
from stock_analysis.tasks.job_store import JobStore


def _map_report_type_for_original(report_type: str) -> str:
    rt = (report_type or "simple").strip().lower()
    if rt == "detailed":
        return "full"
    return "simple"


def run_one_job(
    *,
    store: Optional[JobStore] = None,
    timeout_seconds: int = 900,
) -> Dict[str, Any]:
    store = store or JobStore()
    claimed = store.claim_next_pending_job()
    if not claimed:
        return {"status": "idle", "message": "no pending jobs"}

    job_id = claimed["job_id"]
    stock_code = claimed["stock_code"]
    report_type = claimed.get("report_type", "simple")

    started_at = time.time()
    bridge_result = run_original_single_stock(
        stock_code=stock_code,
        report_type=_map_report_type_for_original(report_type),
        timeout_seconds=timeout_seconds,
    )
    duration_ms = int((time.time() - started_at) * 1000)

    if bridge_result.success:
        ok = store.mark_succeeded(
            job_id,
            query_id=bridge_result.query_id,
            analysis_time=bridge_result.analysis_time,
            raw_result=bridge_result.raw_result,
            context_snapshot=bridge_result.context_snapshot,
            source="original_algo",
            duration_ms=duration_ms,
        )
        return {
            "status": "succeeded" if ok else "error",
            "job_id": job_id,
            "query_id": bridge_result.query_id,
            "duration_ms": duration_ms,
        }

    store.mark_failed(job_id, bridge_result.error or "bridge failed", duration_ms=duration_ms)
    return {
        "status": "failed",
        "job_id": job_id,
        "error": bridge_result.error,
        "duration_ms": duration_ms,
    }


def run_worker_forever(
    *,
    store: Optional[JobStore] = None,
    poll_interval_seconds: int = 3,
    timeout_seconds: int = 900,
) -> None:
    store = store or JobStore()
    while True:
        outcome = run_one_job(store=store, timeout_seconds=timeout_seconds)
        if outcome.get("status") == "idle":
            time.sleep(max(1, poll_interval_seconds))


__all__ = ["run_one_job", "run_worker_forever"]
