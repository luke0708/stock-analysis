from __future__ import annotations

from typing import Any, Dict, Optional

from stock_analysis.tasks.job_store import JobStore
from stock_analysis.tasks.job_runner import run_one_job


def submit_single_stock_job(
    stock_code: str,
    report_type: str = "simple",
    requested_by: str = "beta_ui",
    store: Optional[JobStore] = None,
) -> Dict[str, Any]:
    store = store or JobStore()
    job_id = store.create_job(
        stock_code=stock_code,
        report_type=report_type,
        requested_by=requested_by,
    )
    return {"job_id": job_id}


def get_job_status(job_id: str, store: Optional[JobStore] = None) -> Dict[str, Any]:
    store = store or JobStore()
    job = store.get_job(job_id)
    if not job:
        return {
            "status": "not_found",
            "progress": 0.0,
            "message": "job not found",
        }

    status = job.get("status", "unknown")
    progress_map = {
        "pending": 0.1,
        "running": 0.5,
        "succeeded": 1.0,
        "failed": 1.0,
    }
    message = ""
    if status == "failed":
        message = job.get("error_message") or "job failed"
    elif status == "succeeded":
        message = "completed"
    elif status == "running":
        message = "running"
    else:
        message = "pending"

    return {
        "status": status,
        "progress": progress_map.get(status, 0.0),
        "message": message,
    }


def get_job_result(job_id: str, store: Optional[JobStore] = None) -> Dict[str, Any]:
    store = store or JobStore()
    bundle = store.get_job_with_result(job_id)
    if not bundle:
        return {"error": "job not found"}

    job = bundle["job"]
    if job.get("status") != "succeeded":
        return {"error": f"job not succeeded, current status={job.get('status')}"}

    result = bundle.get("result")
    if not result:
        return {"error": "result missing"}

    return {
        "meta": {
            "query_id": result.get("query_id"),
            "analysis_time": result.get("analysis_time"),
            "source": result.get("source"),
            "job_id": job_id,
        },
        "raw_result": result.get("raw_result") or {},
        "context_snapshot": result.get("context_snapshot"),
    }


def run_one_pending_job(
    store: Optional[JobStore] = None,
    timeout_seconds: int = 900,
) -> Dict[str, Any]:
    return run_one_job(store=store, timeout_seconds=timeout_seconds)


__all__ = [
    "submit_single_stock_job",
    "get_job_status",
    "get_job_result",
    "run_one_pending_job",
]
