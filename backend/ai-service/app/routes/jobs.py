"""HTTP endpoints for background jobs: poll one, list them, cancel one."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.job import JobOut, to_out
from app.services import jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
async def list_jobs(
    kind: str | None = Query(None, description="MATCH_ALL, REINDEX, ..."),
    job_status: str | None = Query(None, alias="status"),
    cpse: str | None = Query(None, description="Optionally narrow to one CPSE"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[JobOut]:
    """Recent jobs, newest first.

    Unfiltered by CPSE: this service does not scope callers - api-service does.
    Pass `cpse` explicitly to narrow the list.
    """
    rows = await jobs.list_jobs(
        session, kind=kind, status=job_status, cpse_code=cpse, limit=limit, offset=offset
    )
    return [to_out(job) for job in rows]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str,
    wait: float = Query(
        0,
        ge=0,
        le=60,
        description="Block up to this many seconds for the job to finish. "
                    "0 returns the current state immediately.",
    ),
    session: AsyncSession = Depends(get_db),
) -> JobOut:
    """The state of one job, including its result once it has succeeded.

    `wait` exists so a UI can avoid a tight poll loop on a job that is nearly
    done. It is capped well below any sensible proxy timeout: waiting is a
    convenience, and the answer is always available by polling instead.
    """
    job = await jobs.wait_for(session, job_id, wait) if wait else await jobs.get(session, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown job {job_id!r}")
    return to_out(job)


@router.post("/{job_id}/cancel", response_model=JobOut)
async def cancel_job(
    job_id: str,
    session: AsyncSession = Depends(get_db),
) -> JobOut:
    """Ask a running job to stop.

    Cooperative, so a job stops at the next point its handler checks - work
    already committed stays committed. A job that has already finished is
    returned unchanged rather than treated as an error.
    """
    job = await jobs.cancel(session, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown job {job_id!r}")
    return to_out(job)
