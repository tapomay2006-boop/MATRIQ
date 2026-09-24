"""The in-process job runner.

    POST /materials/match-all
        ├─ write a Job row (QUEUED)          <- survives the request
        ├─ spawn an asyncio task              <- does the work
        └─ 202 {"job_id": ...}                <- returns immediately

    GET /jobs/{id}  ->  QUEUED | RUNNING (+progress) | SUCCEEDED (+result) | FAILED (+error)

Three things this module exists to get right:

1. **A job gets its own database session.** The request's session is closed the
   moment the response is sent, so a handler that borrowed it would fail on its
   first query - usually minutes later, in a background task, where nobody is
   looking. Every handler is therefore called with a fresh session from
   `AsyncSessionLocal` and owns its own transaction.

2. **Blocking work must leave the event loop.** The LoRA adapter, the Qdrant
   client and the embedding model are all synchronous. Awaiting them directly
   would block the single event loop this service runs on, which is what made
   one large upload stall every other request - `/health` included - for as long
   as it took. `run_blocking()` is how a handler steps off the loop, and heavy
   handlers must use it.

3. **A crash must not leave a job RUNNING forever.** Nothing survives a restart
   in an in-process runner, so `reap_orphans()` runs at startup and fails any
   job still marked RUNNING. A caller polling one of those learns the truth
   instead of waiting on a task that no longer exists.

The deliberate limit: jobs live in this process. Two workers do not share a
queue, and a restart loses in-flight work (the row is marked FAILED, and the
operations here are all safe to resubmit). Moving to Celery or RQ later means
replacing `_spawn` and leaving the rest - the Job row, the routes, the polling
contract - exactly as they are.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import anyio
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import database
from app.config import settings
from app.logic.clock import utcnow
from app.models.job import Job, JobStatus

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Handler signature: (session, job_context) -> JSON-serialisable result.
JobHandler = Callable[[AsyncSession, "JobContext"], Awaitable[Any]]

#: Live tasks, so `wait_for` can await a job instead of polling the database in
#: a loop. Only ever a cache: a job id missing here is answered from its row.
_tasks: dict[str, asyncio.Task] = {}

#: Bounds concurrent jobs. These are CPU- and memory-heavy; running an unbounded
#: number of them concurrently turns a slow service into an unavailable one.
_semaphore: asyncio.Semaphore | None = None


def _session() -> AsyncSession:
    """A new session, resolved through the module rather than bound at import.

    `app.database.AsyncSessionLocal` is rebound when the database is pointed
    somewhere else - which the test suite does per module. A name captured at
    import time would keep handing background jobs the original engine, so a
    job would quietly write to a different database from its own request.
    """
    return database.AsyncSessionLocal()


def _limiter() -> asyncio.Semaphore:
    # Built lazily: a Semaphore binds to the running loop, and at import time
    # there is not one yet.
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
    return _semaphore


async def run_blocking(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run synchronous work in a worker thread, off the event loop.

    Every heavy call in this service is synchronous - the LoRA adapter, the
    Qdrant client, torch. Called directly from a coroutine each one blocks the
    loop for its whole duration, which is why a single large import used to make
    the entire service unresponsive rather than merely slow.
    """
    if kwargs:
        from functools import partial

        return await anyio.to_thread.run_sync(partial(fn, *args, **kwargs))
    return await anyio.to_thread.run_sync(fn, *args)


class JobContext:
    """Handed to a handler so it can report progress and notice cancellation."""

    def __init__(self, job_id: str, params: dict[str, Any], actor: str | None = None):
        self.job_id = job_id
        self.params = params
        self.actor = actor or "system"
        self._cancelled = False
        self._current = 0
        self._total = 0
        self._message: str | None = None

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise JobCancelled()

    async def progress(
        self,
        session: AsyncSession,
        current: int,
        total: int,
        message: str | None = None,
    ) -> None:
        """Publish progress so a poller sees movement rather than a silent RUNNING.

        Committed on its own so it is visible immediately - a progress update
        held inside the handler's transaction would only appear once the work it
        is reporting on had already finished.
        """
        self._current, self._total, self._message = current, total, message
        await session.execute(
            update(Job)
            .where(Job.id == self.job_id)
            .values(
                progress_current=current,
                progress_total=total,
                progress_message=message,
            )
        )
        await session.commit()


class JobCancelled(Exception):
    """Raised inside a handler when the job was cancelled. Not an error."""


async def submit(
    session: AsyncSession,
    *,
    kind: str,
    handler: JobHandler,
    params: dict[str, Any] | None = None,
    actor: str | None = None,
    cpse_code: str | None = None,
) -> Job:
    """Record the job, start it, and return the row. Never waits for the work."""
    job = Job(
        kind=kind,
        status=JobStatus.QUEUED,
        params_json=json.dumps(params or {}, default=str),
        requested_by=actor,
        cpse_code=(cpse_code or "").strip().upper() or None,
    )
    session.add(job)
    await session.commit()

    context = JobContext(job.id, params or {}, actor)
    _spawn(job.id, kind, handler, context)
    return job


def _spawn(job_id: str, kind: str, handler: JobHandler, context: JobContext) -> None:
    task = asyncio.create_task(_run(job_id, kind, handler, context), name=f"job:{job_id}")
    _tasks[job_id] = task
    task.add_done_callback(lambda _t: _tasks.pop(job_id, None))


async def _run(job_id: str, kind: str, handler: JobHandler, context: JobContext) -> None:
    """Drive one job to a terminal state. Never raises into the task."""
    async with _limiter():
        started = utcnow()
        async with _session() as session:
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status=JobStatus.RUNNING, started_at=started)
            )
            await session.commit()

        status, result, error = JobStatus.SUCCEEDED, None, None
        error_status: int | None = None
        try:
            # A fresh session for the handler: it owns its own transaction, and
            # a rollback in here must not touch the bookkeeping above.
            async with _session() as session:
                result = await handler(session, context)
        except JobCancelled:
            status, error = JobStatus.CANCELLED, "Cancelled by request."
        except asyncio.CancelledError:
            status, error = JobStatus.CANCELLED, "Cancelled."
            raise
        except HTTPException as exc:
            # The handler rejected the caller's input. That is a 4xx and has to
            # stay one: a job is where the work moved to, not a reason to stop
            # telling the caller their file was malformed.
            status = JobStatus.FAILED
            error = str(exc.detail)
            error_status = exc.status_code
            logger.info("Job %s (%s) rejected: %s", job_id, kind, exc.detail)
        except Exception as exc:  # noqa: BLE001 - a failed job is a result, not a crash
            status = JobStatus.FAILED
            # Type and message only. A traceback across a service boundary leaks
            # filesystem paths and helps no caller.
            error = f"{type(exc).__name__}: {exc}"
            error_status = 500
            logger.exception("Job %s (%s) failed", job_id, kind)
        finally:
            finished = utcnow()
            try:
                async with _session() as session:
                    await session.execute(
                        update(Job)
                        .where(Job.id == job_id)
                        .values(
                            status=status,
                            result_json=(
                                json.dumps(result, default=str)
                                if result is not None
                                else None
                            ),
                            error=error,
                            error_status=error_status,
                            finished_at=finished,
                            duration_ms=round(
                                (finished - started).total_seconds() * 1000, 2
                            ),
                        )
                    )
                    await session.commit()
            except Exception:  # noqa: BLE001
                # If we cannot even record the outcome, say so loudly here -
                # reap_orphans() will fail the row on the next start.
                logger.exception("Could not record outcome for job %s", job_id)


async def wait_for(
    session: AsyncSession, job_id: str, timeout: float
) -> Job | None:
    """Await a job for up to `timeout` seconds; return its row either way.

    This is what lets one endpoint serve both callers: a UI that wants the
    answer inline passes `wait`, a batch client passes nothing and polls. The
    job is identical in both cases - only the waiting differs.
    """
    task = _tasks.get(job_id)
    if task is not None and timeout > 0:
        with anyio.move_on_after(timeout):
            await asyncio.shield(task)
    return await get(session, job_id)


async def get(session: AsyncSession, job_id: str) -> Job | None:
    # expire_all() because the row may have been written by a different session
    # in a background task, and this one could otherwise serve a cached copy.
    session.expire_all()
    return await session.get(Job, job_id)


async def list_jobs(
    session: AsyncSession,
    *,
    kind: str | None = None,
    status: str | None = None,
    cpse_code: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Job]:
    session.expire_all()
    stmt = select(Job).order_by(Job.created_at.desc())
    if kind:
        stmt = stmt.where(Job.kind == kind.upper())
    if status:
        stmt = stmt.where(Job.status == status.upper())
    if cpse_code:
        stmt = stmt.where(Job.cpse_code == cpse_code.upper())
    rows = await session.execute(stmt.offset(offset).limit(limit))
    return list(rows.scalars().all())


async def cancel(session: AsyncSession, job_id: str) -> Job | None:
    """Ask a job to stop. Cooperative: the handler decides where it is safe to.

    A QUEUED or RUNNING job whose task has already gone (a restart, say) is
    marked CANCELLED directly, so cancelling never leaves a row that no longer
    corresponds to anything running.
    """
    job = await get(session, job_id)
    if job is None or job.is_terminal:
        return job

    task = _tasks.get(job_id)
    if task is not None:
        task.cancel()
    else:
        job.status = JobStatus.CANCELLED
        job.error = "Cancelled; no running task (the service was restarted)."
        job.finished_at = utcnow()
        await session.commit()
    return await get(session, job_id)


async def reap_orphans() -> int:
    """Fail every job still marked RUNNING or QUEUED at startup.

    Jobs live in this process, so anything mid-flight when it stopped is gone.
    Leaving the row RUNNING would strand every caller polling it on a task that
    will never finish; failing it tells them to resubmit, which every operation
    behind a job here is safe to do.
    """
    async with _session() as session:
        result = await session.execute(
            update(Job)
            .where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
            .values(
                status=JobStatus.FAILED,
                error="Interrupted: the service restarted while this job was running. "
                      "Resubmit it - every job kind here is safe to run again.",
                finished_at=utcnow(),
            )
        )
        await session.commit()
        count = result.rowcount or 0
    if count:
        logger.warning("Failed %d job(s) orphaned by a restart.", count)
    return count
