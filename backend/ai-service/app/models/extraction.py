"""Phase 1 state that has to survive the process: sessions, records, taxonomy.

All three used to live in module-level dicts backed by files, inherited from
pipeline-one where a single-process Review Studio makes that reasonable. In a
service with a database and more than one worker it is not:

  * `SessionStore._sessions` was a per-process dict whose `list_sessions()`
    never read the disk fallback, so `GET /extract/sessions` returned an empty
    list after every restart while the JSON sat in `data/sessions/`. With two
    workers, a session created on one was invisible to the other.

  * `_ABBREVIATIONS_REGISTRY` was a module-level dict appended to a CSV with no
    locking. Worker 1 learned `VLV -> VALVE`; worker 2 kept extracting without
    it until someone restarted the service.

So the state moves here. The *algorithms* stay vendored and untouched in
`logic/extraction.py` - the prompt, the grounding guardrail, `expand_abbreviations`
- and only the storage is this service's.

A record is a row, not a field of a JSON blob on the session. `PUT /extract/
records/{sid}/{rid}` is then a single-row update rather than a read-modify-write
of the whole batch, which is what stops two reviewers working the same
100-record session from overwriting each other.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ExtractionSession(Base):
    """One run of Phase 1, awaiting review.

    Working state, not the master. Nothing in a session is part of the master
    until `POST /standardized/add` accepts the rows it produced.
    """

    __tablename__ = "extraction_session"
    __table_args__ = (Index("ix_extraction_session_created", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    """`sess_<epoch>_<hex>`, the id pipeline-one's store minted. Kept in that
    shape so a client written against either service reads the same thing."""

    source_type: Mapped[str] = mapped_column(String(16))
    """text | csv"""

    original_filename: Mapped[str | None] = mapped_column(String(255))
    total_records: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(24), default="PROCESSING", index=True)
    """PROCESSING -> PENDING_REVIEW -> REVIEWED (a record was corrected)
    -> CHECKED (offered to the boundary), or FAILED.

    Never CONFIRMED: whether the rows were actually added is a property of the
    batch, not of the session.

    A session is created PROCESSING *before* the model runs, and its records
    are appended as they are extracted. That is what lets a client watch a
    500-row file fill up instead of waiting for all of it - and it means a run
    that fails half way leaves the rows it did manage, rather than nothing."""

    job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    """The background job extracting into this session.

    Extraction is minutes of GPU time on a real catalogue, so it runs as a job
    and the request returns a job id. This is the link back: given the job, a
    poller finds the session and can read the records already done."""

    adapter: Mapped[str | None] = mapped_column(String(64))
    """Which Phase 1 adapter produced these records. Travels onto the material
    when the rows are added, so a row can be traced to the weights that read it."""

    requested_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    records: Mapped[list[ExtractionRecord]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ExtractionRecord.row_index",
    )


class ExtractionRecord(Base):
    """One extracted record: what the model said, and what a human left.

    `predicted` is never overwritten. That is the whole value of keeping a
    session at all - without it there is no way to tell later whether a
    retrained adapter is getting better or worse at a given kind of
    description, only that somebody edited something.
    """

    __tablename__ = "extraction_record"
    __table_args__ = (
        Index("ix_extraction_record_session", "session_id", "row_index"),
        Index("uq_extraction_record", "session_id", "record_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("extraction_session.id"), index=True
    )
    record_id: Mapped[str] = mapped_column(String(24))
    """`rec_0001`, unique within the session and stable for its lifetime."""

    row_index: Mapped[int] = mapped_column(Integer)
    raw_input: Mapped[str] = mapped_column(Text)
    """The string the model was actually given. Kept so a bad extraction can be
    reproduced against a new adapter without the original file."""

    predicted_json: Mapped[str] = mapped_column(Text)
    """The eight attributes as the model emitted them. Immutable."""

    current_json: Mapped[str] = mapped_column(Text)
    """The eight attributes as they stand after review. This is what gets
    checked and, if new, embedded."""

    is_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="pending_review")

    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    session: Mapped[ExtractionSession] = relationship(back_populates="records")


class Abbreviation(Base):
    """One CPSE domain abbreviation, added at runtime.

    The shipped taxonomy lives in `logic/extraction.py` (the curated defaults)
    and `data/config/abbreviations.csv` (the seed file), and both are read when
    the engine imports. This table is the *runtime* layer on top: everything
    `POST /extract/taxonomy/abbreviations` has ever added, applied over the
    baseline at startup.

    Postgres rather than a CSV append because this is domain configuration a
    materials engineer owns and every worker must see. A file append is
    per-container, unordered under concurrency, and carries no record of who
    decided `PRV` means `PRESSURE RELIEF VALVE`.
    """

    __tablename__ = "abbreviation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    raw: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    """Upper-cased on the way in, so `vlv` and `VLV` are the same entry."""

    expansion: Mapped[str] = mapped_column(String(255))
    scope: Mapped[str | None] = mapped_column(String(64))
    """Optional category the mapping belongs to. Recorded, not yet enforced -
    the vendored engine expands globally."""

    created_by: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
