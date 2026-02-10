from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class AnalysisJobRecord:
    job_id: str
    stock_code: str
    report_type: str = "simple"
    status: str = JobStatus.PENDING.value
    requested_by: str = "beta_ui"
    created_at: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: Optional[int] = None
    retry_count: int = 0
    error_message: Optional[str] = None


@dataclass
class AnalysisResultRecord:
    job_id: str
    query_id: Optional[str]
    analysis_time: Optional[str]
    source: str
    raw_result_json: str
    context_snapshot_json: Optional[str]
    created_at: str
