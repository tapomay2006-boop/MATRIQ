"""The submit-a-job-and-answer helper shared by every long-running endpoint.

One contract, used identically everywhere:

    200 + the payload   the work finished within `wait`. Exactly what the
                        synchronous endpoint used to return; the job id is in
                        the `X-Job-Id` header for anyone who wants it.
    202 + JobOut        still running. Poll `Location` until `terminal` is true;
                        the payload is then in `result`.
    4xx / 5xx           the work failed, with the status it would have had
                        synchronously.

Answering inline with the payload rather than a wrapper is what makes this
addition backward compatible: a client that was happy waiting sees no change,
and only work that genuinely outruns the wait becomes a job it has to poll.
A malformed CSV is still a 400 rather than a job "that failed", because the job
runner keeps the status code the handler raised.

`wait` therefore lets one endpoint serve both kinds of caller. An interactive
upload passes a few seconds and usually gets its answer; a national batch load
passes nothing, gets a job id immediately, and polls. The work is identical -
only the waiting differs.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.job import JobStatus
from app.schemas.job import JobOut, to_out
from app.services import jobs

#: Documents the 202 branch on every endpoint that can defer. The declared
#: response_model stays the domain payload, because that is what a caller who
#: waits actually receives.
JOB_RESPONSES: dict[int | str, dict[str, Any]] = {
    202: {
        "model": JobOut,
        "description": (
            "The work outran `wait` and is running in the background. Poll the "
            "URL in the Location header until `terminal` is true; the payload "
            "is then in `result`."
        ),
    }
}


def WaitParam() -> Any:  # noqa: N802 - reads as a type at the call site
    """The `wait` query parameter, with one description in one place."""
    # default=None, not the configured value: a default baked in here would be
    # captured when the module is imported, so changing the setting afterwards
    # (deployment config, a test that wants jobs inline) would have no effect.
    # `submit_and_answer` resolves None against the live setting instead.
    return Query(
        default=None,
        ge=0,
        le=settings.job_max_wait_seconds,
        description=(
            "Seconds to wait inline before answering. 0 returns 202 with a job "
            "id immediately. If the job finishes within the window the response "
            "is 200 and carries the result."
        ),
    )


async def submit_and_answer(
    session: AsyncSession,
    *,
    kind: str,
    handler: jobs.JobHandler,
    params: dict[str, Any] | None = None,
    actor: str | None = None,
    cpse_code: str | None = None,
    wait: float | None = None,
) -> JSONResponse:
    job = await jobs.submit(
        session, kind=kind, handler=handler, params=params,
        actor=actor, cpse_code=cpse_code,
    )

    seconds = settings.job_default_wait_seconds if wait is None else wait
    seconds = min(max(seconds, 0.0), settings.job_max_wait_seconds)
    if seconds > 0:
        job = await jobs.wait_for(session, job.id, seconds) or job

    prefix = settings.api_v1_prefix

    if job.status == JobStatus.SUCCEEDED:
        # Inline: answer with the work, not with a wrapper around it. A caller
        # that waited wants the preview, not a job it must now fetch. The job
        # row is still there, and GET /jobs/{id} still returns it.
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=jsonable_encoder(_loads(job.result_json)),
            headers={"X-Job-Id": job.id},
        )

    if job.status == JobStatus.FAILED:
        # Re-raised with the status it would have had synchronously, so moving
        # the work into the background does not turn "your CSV is malformed"
        # into an opaque 500.
        raise HTTPException(
            job.error_status or status.HTTP_500_INTERNAL_SERVER_ERROR,
            job.error or "The job failed.",
            headers={"X-Job-Id": job.id},
        )

    if job.status == JobStatus.CANCELLED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            job.error or "The job was cancelled.",
            headers={"X-Job-Id": job.id},
        )

    # Still running. This is the path that exists for work too large to wait on.
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=jsonable_encoder(to_out(job, prefix=prefix)),
        headers={"Location": f"{prefix}/jobs/{job.id}", "X-Job-Id": job.id},
    )


def _loads(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None
