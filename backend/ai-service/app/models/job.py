"""Background jobs — the record of work that outlives the request that asked for it.

Some operations here are genuinely long. Checking a large batch against the
index, embedding what survives, or running a 3B model over a few hundred rows
are bounded by the size of the work, not by what an HTTP client is willing to
wait for. Run synchronously they produced the
worst possible outcome: the client timed out at 60 seconds, the server carried
on working, and nobody could see whether the work had finished, failed, or was
still going.

So the request no longer *is* the work. It creates one `Job` row, hands back the
id, and returns. Everything a caller needs afterwards - progress, result, error,
how long it took - is a column on that row, which is also what makes the work
auditable after the fact rather than only observable while it runs.

`Job` is deliberately generic. `StandardizationBatch` (models/standardized.py)
is the other half: it records what pipeline-one *offered* - which rows, which
of them were already in the vector embedding DB, which were eventually written
- and that record has a different lifetime and a different audience from the
scheduling record kept here. A check writes both, and they point at each other.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class JobStatus:
    """Not a StrEnum: these are stored strings and compared as strings."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    #: A job that will not change again. Polling can stop here.
    TERMINAL = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})


class JobKind:
    STANDARDIZED_CHECK = "STANDARDIZED_CHECK"
    STANDARDIZED_ADD = "STANDARDIZED_ADD"
    EXTRACT_BATCH = "EXTRACT_BATCH"


class Job(Base):
    """One unit of background work."""

    __tablename__ = "job"
    __table_args__ = (
        Index("ix_job_status_created", "status", "created_at"),
        Index("ix_job_kind_created", "kind", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True, default=JobStatus.QUEUED)

    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    progress_message: Mapped[str | None] = mapped_column(String(255))
    """Human-readable stage, e.g. "embedded 256/404". Display only - never parse it."""

    params_json: Mapped[str | None] = mapped_column(Text)
    """The arguments the job was submitted with, so a run can be reproduced."""

    result_json: Mapped[str | None] = mapped_column(Text)
    """The payload the synchronous endpoint used to return. Set only on SUCCEEDED."""

    error: Mapped[str | None] = mapped_column(Text)
    """Why it FAILED. The exception type and message, never a traceback: a
    traceback across a service boundary leaks paths and helps no caller."""

    error_status: Mapped[int | None] = mapped_column(Integer)
    """HTTP status the failure would have had synchronously.

    A job that fails because the CSV will not parse is a 400, not a 500, and
    moving the work into the background must not downgrade that to "something
    went wrong". Handlers raise HTTPException as they always did; the runner
    keeps the code here so the inline path can re-raise it unchanged and a
    poller can tell a bad request from a broken service."""

    # Who asked. ai-service does not authenticate users - api-service does - so
    # these are the forwarded claims, kept for the audit trail, never for a
    # permission decision made later.
    requested_by: Mapped[str | None] = mapped_column(String(120))
    user_role: Mapped[str | None] = mapped_column(String(32))
    cpse_code: Mapped[str | None] = mapped_column(String(16), index=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column()
    duration_ms: Mapped[float | None] = mapped_column(Float)

    @property
    def is_terminal(self) -> bool:
        return self.status in JobStatus.TERMINAL
