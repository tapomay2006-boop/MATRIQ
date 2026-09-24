"""Review sessions, in Postgres.

Replaces the vendored `SessionStore`, which kept sessions in a process-local
dict backed by JSON files. That is right for pipeline-one's single-process
Review Studio and wrong here: `list_sessions()` never read the disk fallback,
so a restart emptied the listing, and two uvicorn workers each held their own
dict.

The API shape is unchanged - `predicted` and `current` side by side, records
keyed `rec_0001` - so a client written against pipeline-one reads the same
JSON. Only where it lives changed.

One record per row, not a JSON blob on the session: correcting a cell is then
a single-row UPDATE, and two reviewers working the same 100-record session
cannot overwrite each other's edits.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.logic.standard_format import FIELD_BY_ALIAS, normalize_key
from app.models.extraction import ExtractionRecord, ExtractionSession

__all__ = [
    "append_records",
    "count_sessions",
    "create_pending",
    "create_session",
    "fail",
    "finish",
    "get_session",
    "list_sessions",
    "record_to_dict",
    "rows_for_check",
    "session_for_job",
    "session_to_dict",
    "update_record",
]

#: The eight canonical names, keyed by the field they fill. Corrections arrive
#: under any accepted spelling and are stored under the canonical one, so a
#: session never holds the same attribute twice under two names.
_CANONICAL_BY_FIELD = {
    "company": "Company",
    "description": "Item Description (Raw)",
    "legacy_code": "Item Code / Legacy Ref",
    "quantity": "Quantity",
    "uom": "UOM",
    "part_number": "Part Number / OEM Number",
    "make": "Make / Brand",
    "specifications": "Specifications / Dimensions",
}

#: What the model writes when it could not ground an attribute. A correction
#: that clears a cell is stored as this, not as an empty string, so the session
#: keeps reading the way the engine's own output does.
_ABSENT_IN = {"", "none", "null", "na", "n/a", "unknown"}


def _new_session_id() -> str:
    """The id shape pipeline-one mints, so ids remain interchangeable."""
    return f"sess_{int(time.time())}_{uuid.uuid4().hex[:6]}"


async def create_pending(
    db: AsyncSession,
    *,
    source_type: str,
    total_records: int,
    original_filename: str | None = None,
    adapter: str | None = None,
    requested_by: str | None = None,
    job_id: str | None = None,
) -> ExtractionSession:
    """Open an empty session before the model runs. Commits.

    Created up front on purpose. The row count is known from the file, so the
    session exists - and is pollable - from the first moment, and records are
    appended as they come out of the engine. A client watching a 500-row file
    sees it fill; a run that dies at row 217 leaves the 217 it managed.
    """
    session = ExtractionSession(
        id=_new_session_id(),
        source_type=source_type,
        original_filename=original_filename,
        total_records=total_records,
        status="PROCESSING",
        adapter=adapter,
        requested_by=requested_by,
        job_id=job_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


def _record(predicted: dict[str, Any], raw: str, index: int) -> ExtractionRecord:
    if not raw:
        # No source string (a record handed over already structured). A
        # readable stand-in beats an empty column when someone opens the
        # session to work out why an extraction went wrong.
        raw = " | ".join(str(v) for v in predicted.values() if v)

    payload = json.dumps(predicted, ensure_ascii=False)
    return ExtractionRecord(
        record_id=f"rec_{index:04d}",
        row_index=index,
        raw_input=raw,
        predicted_json=payload,
        current_json=payload,
        is_modified=False,
        status="pending_review",
    )


async def append_records(
    db: AsyncSession,
    session_id: str,
    records: list[dict[str, Any]],
    raw_texts: list[str],
    *,
    start_index: int,
) -> int:
    """Add a chunk of freshly extracted records. Commits.

    Committed per chunk rather than at the end, so progress a caller can see is
    progress that is actually durable. `start_index` is 0-based; `record_id`
    stays `rec_0001`-style and one-based, unchanged from pipeline-one.
    """
    for offset, predicted in enumerate(records):
        raw = raw_texts[offset] if offset < len(raw_texts) else ""
        record = _record(predicted, raw, start_index + offset + 1)
        record.session_id = session_id
        db.add(record)
    await db.commit()
    return len(records)


async def finish(db: AsyncSession, session_id: str) -> None:
    """Extraction is done; the session is ready for a human."""
    session = await db.get(ExtractionSession, session_id)
    if session is not None:
        session.status = "PENDING_REVIEW"
        await db.commit()


async def fail(db: AsyncSession, session_id: str) -> None:
    """Extraction stopped part way. The records it produced are kept.

    Not deleted: a run that got 217 of 500 rows out of a model has done 217
    rows of real work, and throwing that away would make a transient failure
    cost the whole file.
    """
    session = await db.get(ExtractionSession, session_id)
    if session is not None:
        session.status = "FAILED"
        await db.commit()


async def create_session(
    db: AsyncSession,
    *,
    source_type: str,
    records: list[dict[str, Any]],
    raw_texts: list[str] | None = None,
    original_filename: str | None = None,
    adapter: str | None = None,
    requested_by: str | None = None,
) -> ExtractionSession:
    """Open a session and fill it in one go, for callers with every record already."""
    session = await create_pending(
        db, source_type=source_type, total_records=len(records),
        original_filename=original_filename, adapter=adapter,
        requested_by=requested_by,
    )
    await append_records(
        db, session.id, records, list(raw_texts or []), start_index=0
    )
    await finish(db, session.id)
    return await get_session(db, session.id)


async def get_session(db: AsyncSession, session_id: str) -> ExtractionSession | None:
    """One session with its records eager-loaded.

    Eager, because lazy loading cannot run inside an async session and the
    caller always wants the records.
    """
    result = await db.execute(
        select(ExtractionSession)
        .where(ExtractionSession.id == session_id)
        .options(selectinload(ExtractionSession.records))
    )
    return result.scalar_one_or_none()


async def list_sessions(db: AsyncSession, *, limit: int = 50) -> list[ExtractionSession]:
    """Every session, newest first - including ones this process never created.

    That is the whole point of the move: the listing is a query, so it survives
    a restart and is the same on every worker.
    """
    result = await db.execute(
        select(ExtractionSession)
        .order_by(ExtractionSession.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_sessions(db: AsyncSession) -> int:
    return int(
        (await db.execute(select(func.count()).select_from(ExtractionSession)))
        .scalar_one()
    )


def _canonical_updates(updates: dict[str, Any]) -> dict[str, str]:
    """Resolve a correction's keys onto the eight canonical names.

    Accepts everything the boundary accepts - canonical names, snake_case, and
    the engine's own alias table - so a reviewer's client can use whichever
    spelling it already has.
    """
    resolved: dict[str, str] = {}
    for key, value in updates.items():
        field = FIELD_BY_ALIAS.get(normalize_key(str(key)))
        if field is None:
            continue
        canonical = _CANONICAL_BY_FIELD[field]

        text = "" if value is None else str(value).strip()
        if text.lower() in _ABSENT_IN:
            resolved[canonical] = "NA"
            continue

        if canonical == "Quantity":
            try:
                resolved[canonical] = str(int(float(text)))
            except (TypeError, ValueError):
                # "as required" is not a quantity, but it is what the CPSE
                # wrote. Storing NA keeps the record readable rather than
                # inventing a number.
                resolved[canonical] = "NA"
            continue

        resolved[canonical] = text
    return resolved


async def update_record(
    db: AsyncSession, session_id: str, record_id: str, updates: dict[str, Any]
) -> ExtractionRecord | None:
    """Correct one record. Returns None if the session or record is unknown.

    `predicted_json` is never touched: the model's original answer is the only
    evidence of whether a retrained adapter is improving, and an edit that
    erased it would destroy that quietly.
    """
    result = await db.execute(
        select(ExtractionRecord)
        .where(
            ExtractionRecord.session_id == session_id,
            ExtractionRecord.record_id == record_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None

    resolved = _canonical_updates(updates)
    if not resolved:
        return record

    current = json.loads(record.current_json)
    current.update(resolved)
    record.current_json = json.dumps(current, ensure_ascii=False)
    record.is_modified = True
    record.status = "reviewed"

    session = await db.get(ExtractionSession, session_id)
    if session is not None and session.status == "PENDING_REVIEW":
        session.status = "REVIEWED"

    await db.commit()
    await db.refresh(record)
    return record


async def rows_for_check(
    db: AsyncSession, session_id: str
) -> tuple[list[dict[str, Any]], str | None] | None:
    """A reviewed session -> the rows the boundary judges, and its adapter.

    `current` is taken, never `predicted`: the point of a review session is
    that a human corrected what the model got wrong, and the master has to hold
    the correction.

    The record id travels with each row so a verdict can be matched back to the
    cell a reviewer edited. The boundary ignores it, as it ignores every key
    that is not one of the eight.
    """
    session = await get_session(db, session_id)
    if session is None:
        return None

    rows = [
        {
            **json.loads(record.current_json),
            "_record_id": record.record_id,
            "_is_modified": record.is_modified,
        }
        for record in session.records
    ]

    if session.status != "CHECKED":
        session.status = "CHECKED"
        await db.commit()

    return rows, session.adapter


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

async def session_for_job(db: AsyncSession, job_id: str) -> ExtractionSession | None:
    """The session a background extraction job is filling, if it got that far.

    None while the job is still queued - the session is created as the handler
    starts, not when the request is accepted.
    """
    result = await db.execute(
        select(ExtractionSession)
        .where(ExtractionSession.job_id == job_id)
        .options(selectinload(ExtractionSession.records))
    )
    return result.scalar_one_or_none()


def record_to_dict(record: ExtractionRecord) -> dict[str, Any]:
    """The record shape pipeline-one's API returns, unchanged."""
    return {
        "record_id": record.record_id,
        "row_index": record.row_index,
        "raw_input": record.raw_input,
        "predicted": json.loads(record.predicted_json),
        "current": json.loads(record.current_json),
        "is_modified": record.is_modified,
        "status": record.status,
    }


def session_to_dict(
    session: ExtractionSession, *, with_records: bool = True
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "session_id": session.id,
        "created_at": session.created_at,
        "source_type": session.source_type,
        "total_records": session.total_records,
        "original_filename": session.original_filename,
        "status": session.status,
        "adapter": session.adapter,
        "requested_by": session.requested_by,
        "job_id": session.job_id,
    }
    if with_records:
        out["records"] = [record_to_dict(r) for r in session.records]
    return out
