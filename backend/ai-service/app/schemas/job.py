"""Wire shapes for background jobs."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.models.job import Job


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    """QUEUED | RUNNING | SUCCEEDED | FAILED | CANCELLED. Stop polling on the
    last three - `terminal` says so without the caller hard-coding the set."""

    terminal: bool = False

    progress_current: int = 0
    progress_total: int = 0
    progress_percent: float | None = None
    progress_message: str | None = None

    params: dict[str, Any] = Field(default_factory=dict)
    result: Any | None = None
    """The payload the synchronous endpoint used to return, verbatim. Present
    only once status is SUCCEEDED."""

    error: str | None = None
    error_status: int | None = None
    """The HTTP status this failure had, or would have had synchronously. 4xx
    means the request was wrong; 5xx means the service was."""

    poll_url: str | None = None
    """Where to re-read this job. Present so a 202 needs no URL construction."""

    requested_by: str | None = None
    user_role: str | None = None
    cpse_code: str | None = None

    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: float | None = None


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        # A job whose result will not parse is still a job worth reporting.
        return default


def to_out(job: Job, *, prefix: str = "/api/v1") -> JobOut:
    percent: float | None = None
    if job.progress_total > 0:
        percent = round(job.progress_current / job.progress_total * 100, 2)

    return JobOut(
        id=job.id,
        kind=job.kind,
        status=job.status,
        terminal=job.is_terminal,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        progress_percent=percent,
        progress_message=job.progress_message,
        params=_loads(job.params_json, {}),
        result=_loads(job.result_json, None),
        error=job.error,
        error_status=job.error_status,
        poll_url=f"{prefix}/jobs/{job.id}",
        requested_by=job.requested_by,
        user_role=job.user_role,
        cpse_code=job.cpse_code,
        created_at=job.created_at.isoformat() if job.created_at else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        duration_ms=job.duration_ms,
    )
