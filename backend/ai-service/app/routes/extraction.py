"""Phase 1 endpoints: raw text or a raw file -> the standard format.

    VENDORED FROM backend/pipeline-one/app.py

This is pipeline-one's extraction API, brought into ai-service. `/extract/text`,
`/extract/csv`, the review-session endpoints and `/taxonomy/abbreviations`
behave exactly as they do over there, and `row_to_composite_text` - the thing
that turns a whole spreadsheet row into one coherent string for the model - is
copied verbatim.

Two endpoints from pipeline-one's server are deliberately NOT here:

  * `POST /pipeline/forward`, which posted a reviewed session to a downstream
    webhook. Downstream is now this same service, and a wrapper that looked up
    a session and called the check would be the check under a second name - so
    `POST /standardized/check` takes a `session_id` directly instead.
  * the Review Studio UI at `/`. This service has no UI; the endpoints are the
    interface and the frontend is its own application.

This router stops at the standard format. What happens next is one call:

    raw file --[ this router ]--> a review session
                                        |
                                        v
                     POST /standardized/check {"session_id": "..."}
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.job import JobKind
from app.routes._jobs import JOB_RESPONSES, WaitParam, submit_and_answer
from app.schemas.extraction import (
    AbbreviationOut,
    AbbreviationRequest,
    ExtractionJobOut,
    ExtractTextRequest,
    SessionOut,
    SessionSummaryOut,
)
from app.services import extraction, jobs, sessions, taxonomy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extract", tags=["extraction"])


def _loads(raw: str | None) -> Any:
    """A stored JSON column, or None. A job whose result will not parse is
    still a job worth reporting on."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@router.get("/info", response_model=dict)
async def extraction_info(session: AsyncSession = Depends(get_db)) -> dict:
    """Which Phase 1 is live, and whether the LoRA weights are actually there.

    Always reports the real state. A demo can never claim fine-tuned extraction
    while running with `EXTRACTION_ENABLED=false` - the same honesty rule
    `GET /retrieval/model/info` follows for the embedding provider.
    """
    return {
        **extraction.info(),
        "sessions": await sessions.count_sessions(session),
        "abbreviations_learned": await taxonomy.count(session),
    }


@router.post("/text", response_model=dict, responses=JOB_RESPONSES)
async def extract_text(
    payload: ExtractTextRequest,
    wait: float | None = WaitParam(),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """One un-delimited ERP string -> the eight canonical attributes.

    Runs as a background job, like every other heavy endpoint here: even one
    record is a 3B model generating up to 256 tokens, which is seconds on a GPU
    and much longer on CPU.

    202 + a job id by default; poll `GET /extract/jobs/{job_id}` until `status`
    is `completed`. Pass `?wait=30` to block instead and get the finished body
    inline - which is exactly what this endpoint returned before it became a job.

    The result opens a review session, so the prediction can be corrected
    before it is offered to the vector DB. Nothing is written to the master.
    """
    raw_text = payload.text.strip()
    if not raw_text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Text cannot be empty.")

    async def handler(job_session, context):
        return await extraction.run_extraction(
            job_session, context,
            texts=[raw_text],
            source_type="text",
            requested_by=context.actor,
        )

    return await submit_and_answer(
        session,
        kind=JobKind.EXTRACT_BATCH,
        handler=handler,
        params={"source_type": "text", "total_rows": 1},
        wait=wait,
    )


@router.post("/csv", response_model=dict, responses=JOB_RESPONSES)
async def extract_csv(
    file: UploadFile = File(..., description="CSV, XLSX or XLS"),
    text_column: str | None = Form(None),
    max_rows: int | None = Form(100),
    wait: float | None = WaitParam(),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """A raw CSV/XLSX file -> standard-format rows, row by row.

    Where a real CPSE catalogue enters the system, and the longest operation in
    the service: a 3B model doing generative extraction is minutes for a few
    hundred rows, not seconds. So it runs as a background job.

        POST /extract/csv        -> 202 {"id": "<job_id>", ...}
        GET  /extract/jobs/{id}  -> processed_rows / total_rows, every 1-2s
        GET  /extract/jobs/{id}  -> status "completed", `result` is the body

    `result` is byte-for-byte the response this endpoint returned when it was
    synchronous. `?wait=` blocks inline for that many seconds and returns the
    same body directly, so a caller that was happy waiting can keep waiting.

    The file is read and parsed **here**, in the request: a background task has
    no request left to read from, it is what makes `total_rows` known
    immediately, and a file that will not parse stays a 400 on the upload
    rather than becoming a job that fails a second later.

    Rows are extracted in chunks and written to the session as they are done,
    so `GET /extract/sessions/{session_id}` returns the first 200 rows of a
    500-row file without waiting for the other 300.
    """
    contents = await file.read()
    filename = file.filename or "upload.csv"

    texts, column_label = extraction.read_upload(
        contents, filename, text_column=text_column, max_rows=max_rows
    )

    async def handler(job_session, context):
        return await extraction.run_extraction(
            job_session, context,
            texts=texts,
            source_type="csv",
            column_label=column_label,
            original_filename=filename,
            requested_by=context.actor,
        )

    return await submit_and_answer(
        session,
        kind=JobKind.EXTRACT_BATCH,
        handler=handler,
        params={
            "source_type": "csv",
            "source_file": filename,
            "text_column_used": column_label,
            "total_rows": len(texts),
        },
        wait=wait,
    )


#: Job status as an extraction client reads it. The Job row keeps the service's
#: own vocabulary; this is the translation, in one place.
_CLIENT_STATUS = {
    "QUEUED": "processing",
    "RUNNING": "processing",
    "SUCCEEDED": "completed",
    "FAILED": "failed",
    "CANCELLED": "cancelled",
}


@router.get("/jobs/{job_id}", response_model=ExtractionJobOut)
async def extraction_job_status(
    job_id: str,
    session: AsyncSession = Depends(get_db),
) -> ExtractionJobOut:
    """Progress of a background extraction, for a client polling every 1-2s.

        {"job_id": "...", "status": "processing", "processed_rows": 320, "total_rows": 500}
        {"job_id": "...", "status": "completed",  "processed_rows": 500, "total_rows": 500,
         "result": { ...the original response body... }}
        {"job_id": "...", "status": "failed",     "processed_rows": 217, "total_rows": 500,
         "error": "..."}

    `result` appears once `status` is `completed` and stays there, so a client
    that polls late - or reloads the page - still gets the finished body.

    `session_id` appears as soon as the job has opened its session, before any
    row is done, so the records already extracted can be read from
    `GET /extract/sessions/{session_id}` while the rest are still running.

    The generic `GET /jobs/{job_id}` reports the same job in the service's
    standard shape; this one exists because a row count is what an extraction
    client actually wants to render.
    """
    job = await jobs.get(session, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown job {job_id!r}")
    if job.kind != JobKind.EXTRACT_BATCH:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Job {job_id!r} is a {job.kind} job, not an extraction. Read it at "
            f"GET {settings.api_v1_prefix}/jobs/{job_id}.",
        )

    review = await sessions.session_for_job(session, job_id)
    params = _loads(job.params_json) or {}
    result = _loads(job.result_json)

    return ExtractionJobOut(
        job_id=job.id,
        status=_CLIENT_STATUS.get(job.status, job.status.lower()),
        processed_rows=job.progress_current,
        total_rows=job.progress_total or int(params.get("total_rows") or 0),
        session_id=review.id if review else None,
        source_file=params.get("source_file"),
        result=result,
        error=job.error,
        error_status=job.error_status,
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
    )


@router.get("/sessions", response_model=list[SessionSummaryOut])
async def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> list[SessionSummaryOut]:
    """Every review session, newest first.

    A query, not a process-local dict - so it survives a restart and reads the
    same on every worker. The old in-memory store listed nothing after a
    restart even though the JSON was still on disk.
    """
    return [
        SessionSummaryOut(**sessions.session_to_dict(review, with_records=False))
        for review in await sessions.list_sessions(session, limit=limit)
    ]


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: str,
    session: AsyncSession = Depends(get_db),
) -> SessionOut:
    """One session and all its records, prediction and correction side by side."""
    review = await sessions.get_session(session, session_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown session {session_id!r}")
    return SessionOut(**sessions.session_to_dict(review))


@router.put("/records/{session_id}/{record_id}", response_model=dict)
async def update_record(
    session_id: str,
    record_id: str,
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Correct one extracted record.

    `predicted` is left untouched and `current` takes the edit, so the model's
    original answer survives the correction. That is what makes a review
    session usable later as training signal rather than only as a fix.
    """
    updated = await sessions.update_record(session, session_id, record_id, payload)
    if updated is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Record {record_id!r} in session {session_id!r} not found.",
        )
    return {"success": True, "record": sessions.record_to_dict(updated)}


@router.post("/taxonomy/abbreviations", response_model=dict)
async def add_abbreviation(
    payload: AbbreviationRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Teach the CPSE taxonomy a new abbreviation, without retraining.

    Active learning at the cheapest price there is: `VLV -> VALVE` is a
    dictionary entry a domain expert controls, applied to every subsequent
    extraction, and it costs nothing to add or to undo.

    Stored in Postgres and applied to this worker's live registry. It used to
    be a module-level dict plus a CSV append, which meant an addition reached
    one uvicorn worker and no other until a restart, and nothing recorded who
    decided it. Every worker now picks it up from the database at startup.

    Re-registering an existing abbreviation updates it - correcting a wrong
    mapping is the common case, and refusing it would push people back to
    editing the CSV by hand.
    """
    entry = await taxonomy.add(
        session,
        raw=payload.raw,
        expansion=payload.expansion,
        scope=payload.scope or "",
        actor=payload.actor,
    )
    if entry is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Invalid abbreviation or expansion provided.",
        )
    return {
        "success": True,
        "raw": entry.raw,
        "expansion": entry.expansion,
        "message": (
            "Stored and applied. Every worker picks it up at startup; this one "
            "has it already."
        ),
    }


@router.get("/taxonomy/abbreviations", response_model=list[AbbreviationOut])
async def list_abbreviations(
    limit: int = Query(500, ge=1, le=2000),
    session: AsyncSession = Depends(get_db),
) -> list[AbbreviationOut]:
    """Everything added at runtime, and who added it.

    NOT the whole taxonomy: the curated defaults in logic/extraction.py and the
    shipped data/config/abbreviations.csv are the baseline this sits on top of.
    """
    return [
        AbbreviationOut.model_validate(a, from_attributes=True)
        for a in await taxonomy.list_all(session, limit=limit)
    ]
