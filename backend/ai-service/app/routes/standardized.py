"""HTTP endpoints for the standard-format boundary.

    Raw CSV / XLSX / TXT
            |
            v
      POST /extract/csv   (Qwen2.5-3B + qwen2.5-3b-cpse-lora-v2, routes/extraction.py)
            |
            v
      Standard Format  ---> POST /standardized/check   which rows are new?
            |            (rows, records, or a reviewed session_id)
            |                       |
            |                already there --> ignored
            |                       |
            +------------------> new material
                                    |
                                    v
                        POST /standardized/add   -> vector embedding DB

Nothing on this router parses a file or runs a model. It takes over at the
standard format and owns everything from there to the vector index.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import JobKind
from app.routes._jobs import JOB_RESPONSES, WaitParam, submit_and_answer
from app.schemas.standardized import (
    AddRequest,
    AddResponse,
    BatchOut,
    CheckResponse,
    StandardBatchIn,
)
from app.services import standardized

router = APIRouter(prefix="/standardized", tags=["standardized"])


@router.post("/check", response_model=CheckResponse, responses=JOB_RESPONSES)
async def check_against_vector_db(
    payload: StandardBatchIn,
    wait: float | None = WaitParam(),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Which of these standard-format rows are NOT already in the vector DB?

    Three ways to say what to check, and they end in the same place:

        {"session_id": "sess_..."}   a reviewed extraction session; its
                                     corrected records become the rows
        {"rows":    [...]}           the rows directly
        {"records": [...]}           the same, under pipeline-one's envelope
                                     name, so NEXT_PIPELINE_URL can point here

    A row is judged already present when it shares a material id with the
    master, when the text that would be embedded is identical to something
    already embedded, or when its nearest vector sits at or above
    `EXISTENCE_THRESHOLD`.

    Nothing is written to the master or the index. The response carries a
    `batch_id`; hand that to `POST /standardized/add` to index exactly the rows
    this call judged new.

    When every row already exists, `has_new_data` is false, `new_material` is
    empty, and `message` says so in as many words - that is the answer, not an
    error.

    Runs as a job: the work is proportional to the number of rows sent, and
    every one of them is standardized and embedded before it can be judged.
    """
    async def handler(job_session, context):
        result = await standardized.check(job_session, payload, context=context)
        return result.model_dump()

    return await submit_and_answer(
        session,
        kind=JobKind.STANDARDIZED_CHECK,
        handler=handler,
        params={
            "rows": len(payload.rows),
            "source_pipeline": payload.source_pipeline,
            "session_id": payload.session_id,
        },
        actor=payload.requested_by,
        cpse_code=payload.default_company,
        wait=wait,
    )


@router.post("/add", response_model=AddResponse, responses=JOB_RESPONSES)
async def add_new_material(
    payload: AddRequest,
    wait: float | None = WaitParam(),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Add new material rows to the vector embedding DB.

    The normal path is `{"batch_id": "..."}` from a preceding check: the rows
    written are the ones this service judged new, so a client cannot talk this
    endpoint into re-indexing something that already exists.

    `{"rows": [...]}` checks and adds in one call for a caller that skipped the
    check. Either way the rows are re-checked here before anything is written -
    a batch is a snapshot, and another caller may have indexed the same article
    in between.

    If nothing is left to add, the response is a 200 saying `added: 0` and why.
    A batch can be added once; a second attempt is a 409.

    Runs as a job: standardizing and embedding the selected rows is bounded by
    how many were selected, not by an HTTP timeout.
    """
    async def handler(job_session, context):
        result = await standardized.add(job_session, payload, context=context)
        return result.model_dump()

    return await submit_and_answer(
        session,
        kind=JobKind.STANDARDIZED_ADD,
        handler=handler,
        params={
            "batch_id": payload.batch_id,
            "rows": len(payload.rows or []),
        },
        actor=payload.requested_by,
        wait=wait,
    )


@router.get("/batches", response_model=list[BatchOut])
async def list_batches(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
) -> list[BatchOut]:
    """Recent check/add batches. The audit trail for what Phase 1 offered."""
    return [
        BatchOut.model_validate(batch, from_attributes=True)
        for batch in await standardized.list_batches(session, limit=limit)
    ]


@router.get("/batches/{batch_id}", response_model=dict)
async def get_batch(
    batch_id: str,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """One batch, with the verdict recorded for every row it carried.

    `new_material` is the staged copy of the rows judged new, and it is present
    only while the batch is CHECKED. Once added, those rows live in `material`
    and the batch carries `material_ids` instead - keeping a second copy of the
    master would just let the two drift.
    """
    import json

    batch = await standardized.get_batch(session, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown batch {batch_id!r}")

    stored = json.loads(batch.payload_json or "{}")
    return {
        **BatchOut.model_validate(batch, from_attributes=True).model_dump(),
        "new_material": stored.get("new_material", []),
        "material_ids": stored.get("material_ids", []),
        "rows": stored.get("verdicts", []),
    }
