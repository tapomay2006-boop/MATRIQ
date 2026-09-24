"""The boundary: check what is new, then add only that.

    standard format -> check -> new material -> add -> vector embedding DB
                          |
                          +--> already in the vector DB: ignored

Two steps, deliberately not one. A caller is told what would change before
anything changes, and the second call cannot change more than the first
promised: `add` takes the batch id, so the rows written are the rows *this
service* judged new, not a list the client hands back. Round-tripping the
decision through the client would make the check advisory, and the one
guarantee this pair exists to provide is that a row already in the index
cannot be added again.

Where "already exists" is decided
---------------------------------
`logic/existence.py` owns the rule. This module supplies it with what it needs:

  * the material ids and canonical hashes the master already holds. A row in
    Postgres counts as present whether or not its vector is: `add` writes both
    or neither, so the two agree, and trusting the vector alone would let a
    re-post insert a second copy and then collide on the primary key;

  * the nearest vectors in the store, which is the only signal that catches the
    same article written in different words;

  * the rows of this same payload that came before it.

What this module never does
---------------------------
Read a file, guess a column, or extract an attribute from free text. All three
are Phase 1 and happen in `logic/extraction.py` before any of this runs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.logic.category import UNCLASSIFIED
from app.logic.clock import utcnow
from app.logic.embedding import canonical_hash, embedding_text, get_provider
from app.logic.existence import ExistenceStatus, Neighbour, RowVerdict, decide
from app.logic.identity import assign_material_ids
from app.logic.retrieval import BlockingFilter, get_store
from app.logic.standard_format import RowFormatError, StandardRow, parse_row, to_standard_dict
from app.logic.standardize import StandardMaterial, to_material
from app.models.material import AuditLog, Material
from app.models.standardized import StandardizationBatch
from app.schemas.standardized import (
    AddedMaterialOut,
    AddRequest,
    AddResponse,
    CheckedRowOut,
    CheckResponse,
    NeighbourOut,
    StandardBatchIn,
)
from app.services import sessions as review_sessions
from app.services.indexing import build_points
from app.services.jobs import JobContext, run_blocking
from app.services.materials import allocate_national_ids, next_source_row, persist_rows

logger = logging.getLogger(__name__)

__all__ = ["add", "check", "get_batch", "list_batches"]


# --------------------------------------------------------------------------
# Reading the payload
# --------------------------------------------------------------------------

def _parse(
    rows: list[dict[str, Any]], default_company: str
) -> tuple[list[tuple[int, StandardRow, dict[str, Any]]], list[RowVerdict]]:
    """Incoming rows -> StandardRow, quarantining what cannot be read.

    Row numbers are 1-based positions in the payload, so a caller can point at
    the row it sent. A row that cannot be read is reported, never dropped: a
    row that vanishes without a trace is indistinguishable from one that was
    never sent.
    """
    usable: list[tuple[int, StandardRow, dict[str, Any]]] = []
    invalid: list[RowVerdict] = []

    for index, payload in enumerate(rows, start=1):
        try:
            parsed = parse_row(payload, index, default_company=default_company)
        except RowFormatError as exc:
            invalid.append(RowVerdict(
                row_number=index,
                status=ExistenceStatus.INVALID,
                description=(
                    str(payload.get("description") or "")[:200]
                    if isinstance(payload, dict) else ""
                ),
                reason="The row is not usable standard format.",
                error=str(exc),
            ))
            continue
        usable.append((index, parsed, payload))

    return usable, invalid


# --------------------------------------------------------------------------
# What the master already holds
# --------------------------------------------------------------------------

async def _known(session: AsyncSession) -> tuple[set[str], dict[str, str]]:
    """(material ids, canonical hash -> material id) for the whole master.

    `canonical_hash` is only populated once a row has been embedded, so an
    un-indexed row contributes its id but no hash. That is correct: its id
    still blocks a re-import, and the vector search below is what would have
    caught it semantically.
    """
    rows = (await session.execute(
        select(Material.material_id, Material.canonical_hash)
    )).all()

    ids = {row[0] for row in rows}
    hashes: dict[str, str] = {}
    for material_id, stored_hash in rows:
        if stored_hash:
            hashes.setdefault(stored_hash, material_id)
    return ids, hashes


def _nearest(
    materials: list[StandardMaterial], top_k: int
) -> tuple[list[list[Neighbour]], str | None]:
    """The nearest indexed vectors for each row.

    Read-only, and using the store's existing search interface unchanged:
    retrieval is not this feature's to modify.

    `embedding_version` is always in the block - comparing against vectors from
    a different model is meaningless.

    Category is in it only when `EXISTENCE_BLOCK_BY_CATEGORY` is on, and that
    is **off by default**, deliberately. Blocking narrows the traversal, but a
    row the keyword table put in the wrong family would then never be compared
    against its own duplicate - and a missed duplicate is the failure this
    whole endpoint exists to prevent, while an unblocked ANN search is
    sublinear anyway. Turn it on when the corpus is large enough that the scan
    actually costs something and the category table has earned trust on your
    data. A row classified UNCLASSIFIED is never blocked, whatever the setting:
    abstention must not become a filter.

    An unreachable store returns empty neighbour lists and its error, never an
    exception: the id and hash signals still decide, and a check that refuses
    to answer because Qdrant is down is worse than one that answers with less
    evidence and says so.
    """
    if not materials:
        return [], None

    try:
        provider = get_provider()
        store = get_store()
        vectors = provider.embed(
            [embedding_text(m) for m in materials], kind="query"
        )
        blocks = [
            BlockingFilter(
                embedding_version=settings.embedding_version,
                categories=(
                    (m.category,)
                    if settings.existence_block_by_category
                    and m.category != UNCLASSIFIED
                    else ()
                ),
            )
            for m in materials
        ]
        results = store.search_batch(list(vectors), top_k=top_k, blocks=blocks)
    except Exception as exc:  # noqa: BLE001 - degraded, and reported as such
        logger.warning("Vector existence check unavailable: %s", exc)
        return [[] for _ in materials], str(exc)

    return (
        [
            [Neighbour(material_id=c.material_id, score=c.embedding_score) for c in hits]
            for hits in results
        ],
        None,
    )


async def _prune_abandoned(db: AsyncSession) -> int:
    """Drop checks nobody acted on.

    A batch stages a full copy of every row it judged new, which is what lets
    `add` write this service's decision rather than a list the client hands
    back. That copy is worth keeping only until the rows are added - after
    which it duplicates `material` - or until it is clear nobody is coming
    back for it.

    Only CHECKED batches are pruned. An ADDED batch is the audit trail for rows
    that are now in the master, and by then it no longer carries the staged
    copy anyway.

    Runs opportunistically on each new check: one indexed DELETE, no scheduler,
    and the work is proportional to what has actually expired.
    """
    days = settings.batch_retention_days
    if days <= 0:
        return 0

    cutoff = utcnow() - timedelta(days=days)
    result = await db.execute(
        delete(StandardizationBatch).where(
            StandardizationBatch.status == "CHECKED",
            StandardizationBatch.created_at < cutoff,
        )
    )
    removed = result.rowcount or 0
    if removed:
        await db.commit()
        logger.info("Pruned %d abandoned batch(es) older than %d days", removed, days)
    return removed


def _indexed_total() -> int | None:
    try:
        return get_store().count()
    except Exception:  # noqa: BLE001 - an unreachable store is a null, not a 500
        return None


# --------------------------------------------------------------------------
# 1. Check
# --------------------------------------------------------------------------

async def _rows_from_session(
    db: AsyncSession, session_id: str
) -> tuple[list[dict[str, Any]], str | None]:
    """A reviewed extraction session -> the rows to judge, and its adapter.

    `current` is read, never `predicted`: the point of a review session is that
    a human corrected what the model got wrong, and the master must hold the
    correction. `predicted` stays on the record as evidence of what the adapter
    originally said.
    """
    found = await review_sessions.rows_for_check(db, session_id)
    if found is None:
        raise HTTPException(
            http_status.HTTP_404_NOT_FOUND,
            f"Unknown session {session_id!r}. Sessions come from "
            f"POST /extract/csv or POST /extract/text.",
        )
    return found


async def check(
    session: AsyncSession,
    payload: StandardBatchIn,
    *,
    context: JobContext | None = None,
    persist_batch: bool = True,
) -> CheckResponse:
    """Split incoming standard-format rows into new material and the rest.

    The rows arrive one of two ways - given directly, or read out of a review
    session named by `session_id` - and from here on the two are identical.
    That is the whole reason there is no separate forward endpoint.
    """
    default_company = (payload.default_company or "").strip()

    rows = payload.rows
    source = payload.source_pipeline
    adapter: str | None = None
    if payload.session_id and not rows:
        rows, adapter = await _rows_from_session(session, payload.session_id)
        source = source or "extraction"

    usable, verdicts = _parse(rows, default_company)

    materials = [to_material(row) for _n, row, _p in usable]

    known_ids, known_hashes = await _known(session)

    if context:
        context.raise_if_cancelled()
        await context.progress(
            session, 0, len(materials),
            f"checking {len(materials)} rows against the vector embedding DB",
        )
    neighbours, store_error = await run_blocking(
        _nearest, materials, settings.existence_top_k
    )

    batch_hashes: dict[str, int] = {}
    accepted: list[tuple[RowVerdict, StandardMaterial, dict[str, str]]] = []

    for (row_number, row, original), material, hits in zip(
        usable, materials, neighbours, strict=True
    ):
        row_hash = canonical_hash(material)
        verdict = decide(
            row_number=row_number,
            material_id=material.material_id,
            canonical_hash=row_hash,
            description=row.description,
            category=material.category,
            canonical_text=embedding_text(material),
            known_ids=known_ids,
            known_hashes=known_hashes,
            batch_hashes=batch_hashes,
            neighbours=hits,
            threshold=settings.existence_threshold,
        )
        verdicts.append(verdict)

        if verdict.is_new:
            batch_hashes[row_hash] = row_number
            accepted.append((verdict, material, to_standard_dict(original)))

    # Ids are unique per batch, not per row: two rows can share a CPSE and a
    # legacy code, and the suffix that separates them is derived from the whole
    # group. Run it over exactly the rows that will be written, so the id
    # reported here is the id `add` will store.
    assign_material_ids([m for _v, m, _d in accepted])
    for verdict, material, _data in accepted:
        verdict.material_id = material.material_id

    verdicts.sort(key=lambda v: v.row_number)

    counts = {status: 0 for status in ExistenceStatus}
    for verdict in verdicts:
        counts[verdict.status] += 1

    new_material = [
        {**data, "row_number": verdict.row_number, "material_id": material.material_id}
        for verdict, material, data in accepted
    ]

    batch_id = ""
    if persist_batch:
        await _prune_abandoned(session)
        record = StandardizationBatch(
            status="CHECKED",
            source=source,
            source_session_id=payload.session_id,
            total_rows=len(rows),
            new_rows=counts[ExistenceStatus.NEW],
            existing_rows=counts[ExistenceStatus.ALREADY_EXISTS],
            duplicate_rows=counts[ExistenceStatus.DUPLICATE_IN_BATCH],
            invalid_rows=counts[ExistenceStatus.INVALID],
            payload_json=json.dumps({
                "default_company": default_company,
                "adapter": adapter,
                "new_material": new_material,
                "verdicts": [_verdict_to_dict(v) for v in verdicts],
            }),
            requested_by=payload.requested_by,
            cpse_code=(default_company.upper() or None),
        )
        session.add(record)
        await session.commit()
        batch_id = record.id

    return CheckResponse(
        batch_id=batch_id,
        has_new_data=counts[ExistenceStatus.NEW] > 0,
        message=_check_message(counts, store_error),
        total_rows=len(rows),
        new_rows=counts[ExistenceStatus.NEW],
        existing_rows=counts[ExistenceStatus.ALREADY_EXISTS],
        duplicate_rows_in_batch=counts[ExistenceStatus.DUPLICATE_IN_BATCH],
        invalid_rows=counts[ExistenceStatus.INVALID],
        new_material=new_material,
        rows=[_verdict_to_out(v) for v in verdicts],
        existence_threshold=settings.existence_threshold,
        vector_store=settings.vector_store,
        embedding_provider=get_provider().model_name,
        indexed_total=_indexed_total(),
    )


def _check_message(counts: dict[ExistenceStatus, int], store_error: str | None) -> str:
    total = sum(counts.values())
    new = counts[ExistenceStatus.NEW]
    existing = counts[ExistenceStatus.ALREADY_EXISTS]

    if new == 0:
        head = (
            f"No new data. All {total} row(s) are already available in the "
            f"vector embedding DB."
            if existing == total
            else f"No new data among the {total} row(s) sent."
        )
    else:
        head = (
            f"{new} of {total} row(s) are new material; {existing} already "
            f"exist in the vector embedding DB. POST /standardized/add with "
            f"this batch_id to index the new ones."
        )

    extra = []
    if counts[ExistenceStatus.DUPLICATE_IN_BATCH]:
        extra.append(
            f"{counts[ExistenceStatus.DUPLICATE_IN_BATCH]} row(s) repeat an "
            f"earlier row of this same request."
        )
    if counts[ExistenceStatus.INVALID]:
        extra.append(
            f"{counts[ExistenceStatus.INVALID]} row(s) are not usable standard "
            f"format - see rows[].error."
        )
    if store_error:
        extra.append(
            f"The vector store was unreachable ({store_error}), so only exact "
            f"identity was checked. Re-run once it is back before trusting a "
            f"NEW verdict."
        )
    return " ".join([head, *extra])


def _verdict_to_dict(verdict: RowVerdict) -> dict[str, Any]:
    data = asdict(verdict)
    data["status"] = str(verdict.status)
    return data


def _verdict_to_out(verdict: RowVerdict) -> CheckedRowOut:
    return CheckedRowOut(
        row_number=verdict.row_number,
        status=str(verdict.status),
        description=verdict.description,
        category=verdict.category,
        material_id=verdict.material_id,
        embedded_text=verdict.canonical_text,
        matched_material_id=verdict.matched_material_id,
        matched_by=verdict.matched_by,
        similarity=verdict.similarity,
        duplicate_of_row=verdict.duplicate_of_row,
        reason=verdict.reason,
        neighbours=[
            NeighbourOut(material_id=n.material_id, score=round(n.score, 4))
            for n in verdict.neighbours
        ],
        error=verdict.error,
    )


# --------------------------------------------------------------------------
# 2. Add
# --------------------------------------------------------------------------

async def add(
    session: AsyncSession,
    request: AddRequest,
    *,
    context: JobContext | None = None,
) -> AddResponse:
    """Write the new material into Postgres and the vector embedding DB.

    Whichever way the rows arrive, they are checked again here before anything
    is written. A batch is a snapshot: between check and add another caller may
    have indexed the same article, and re-checking is what keeps the promise
    that this endpoint cannot create a duplicate.
    """
    record, rows, default_company, adapter = await _resolve_batch(session, request)

    if not rows:
        await _finish(session, record, added=0, actor=request.requested_by)
        return AddResponse(
            batch_id=record.id, added=0, requested=0,
            message="No new data to add: the batch holds no new material.",
        )

    verdict = await check(
        session,
        StandardBatchIn(
            rows=rows,
            default_company=default_company or None,
            requested_by=request.requested_by,
        ),
        context=context,
        persist_batch=False,
    )

    fresh = sorted(row["row_number"] for row in verdict.new_material)
    skipped_existing = verdict.existing_rows + verdict.duplicate_rows_in_batch
    skipped_invalid = verdict.invalid_rows

    if not fresh:
        await _finish(session, record, added=0, actor=request.requested_by)
        return AddResponse(
            batch_id=record.id, added=0, requested=len(rows),
            skipped_existing=skipped_existing, skipped_invalid=skipped_invalid,
            message=(
                "No new data. Every row is already available in the vector "
                "embedding DB, so nothing was added."
            ),
        )

    keep = [rows[number - 1] for number in fresh]
    usable, _invalid = _parse(keep, default_company)
    parsed = [row for _n, row, _p in usable]

    # `source_row` orders the master and is not the caller's row number - every
    # batch has a row 1. Continue the existing sequence instead.
    start = await next_source_row(session)
    for offset, row in enumerate(parsed):
        row.source_row = start + offset

    # Provenance: the adapter recorded on the batch, which is the one the
    # session's records were extracted with. Rows posted straight to
    # /standardized/check by some other producer carry None - the honest
    # answer, since claiming an adapter read them would be worse than silence.
    def _build() -> list[StandardMaterial]:
        out = [to_material(row, extraction_model=adapter) for row in parsed]
        assign_material_ids(out)
        return out

    if context:
        context.raise_if_cancelled()
        await context.progress(
            session, 0, len(parsed), f"writing {len(parsed)} materials"
        )
    materials = await run_blocking(_build)

    # The national id, allocated here and nowhere else: inside the transaction,
    # before the row is written, and therefore before the vector is. It is the
    # identity the master owns - material_id is the CPSE's - and a material
    # must never reach the index without one.
    for material, national_id in zip(
        materials, await allocate_national_ids(session, len(materials)), strict=True
    ):
        material.national_id = national_id

    persist_rows(session, materials, batch_id=record.id)
    await session.flush()

    # Before the commit, and it raises rather than warns: see _index.
    indexed = await _index(session, materials)

    record.added_rows = len(materials)
    record.status = "ADDED"
    _settle(record, [m.material_id for m in materials])
    session.add(AuditLog(
        actor=request.requested_by or "extraction",
        action="ADD_NEW_MATERIAL",
        entity_type="standardization_batch",
        entity_id=record.id,
        detail=json.dumps({
            "requested": len(rows),
            "added": len(materials),
            "skipped_existing": skipped_existing,
            "skipped_invalid": skipped_invalid,
            "indexed": indexed,
            "material_ids": [m.material_id for m in materials][:50],
            "national_ids": [m.national_id for m in materials][:50],
        }),
    ))
    await session.commit()

    return AddResponse(
        batch_id=record.id,
        added=len(materials),
        requested=len(rows),
        skipped_existing=skipped_existing,
        skipped_invalid=skipped_invalid,
        indexed=indexed,
        materials=[
            AddedMaterialOut(
                national_id=material.national_id,
                material_id=material.material_id,
                row_number=row_number,
                description=material.description,
                cpse_code=material.cpse_code,
            )
            for row_number, material in zip(fresh, materials, strict=True)
        ],
        material_ids=[material.material_id for material in materials],
        national_ids=[material.national_id for material in materials],
        message=(
            f"Added {len(materials)} new material row(s) to the master and the "
            f"vector embedding DB."
        ),
    )


async def _resolve_batch(
    session: AsyncSession, request: AddRequest
) -> tuple[StandardizationBatch, list[dict[str, Any]], str, str | None]:
    """Find (or open) the batch this add belongs to, the rows it may write, and
    the Phase 1 adapter that produced them."""
    if request.batch_id:
        record = await session.get(StandardizationBatch, request.batch_id)
        if record is None:
            raise HTTPException(
                http_status.HTTP_404_NOT_FOUND,
                f"Unknown batch {request.batch_id!r}. Call POST "
                f"/standardized/check first.",
            )
        if record.status == "ADDED":
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                f"Batch {record.id} has already been added: {record.added_rows} "
                f"row(s) went in. Re-adding it would re-check the same rows and "
                f"find them all present. Run a new check instead.",
            )
        stored = json.loads(record.payload_json or "{}")
        return (
            record,
            list(stored.get("new_material") or []),
            str(stored.get("default_company") or ""),
            stored.get("adapter"),
        )

    # Standalone: check and add in one call. Still two steps internally, so the
    # same guarantee holds - the check above decides what gets written.
    rows = request.rows or []
    default_company = (request.default_company or "").strip()
    record = StandardizationBatch(
        status="CHECKED",
        source="direct",
        total_rows=len(rows),
        payload_json=json.dumps({
            "default_company": default_company, "adapter": None,
            "new_material": rows, "verdicts": [],
        }),
        requested_by=request.requested_by,
        cpse_code=(default_company.upper() or None),
    )
    session.add(record)
    await session.flush()
    return record, rows, default_company, None


async def _index(
    session: AsyncSession, materials: list[StandardMaterial]
) -> int:
    """Embed the new rows and upsert them. Raises if the store will not take them.

    All-or-nothing, and that is a change of doctrine worth stating. While
    `POST /retrieval/index` existed, an unreachable store was survivable: the
    rows landed in Postgres, the response said the index was behind, and a
    reindex reconciled it later. There is no reindex endpoint any more, so a
    row written to the master but not to the index would be stranded - it could
    never be embedded, and the next check would keep calling it new while the
    master already held it.

    So the vector write happens inside the caller's transaction, before its
    commit, and an exception here rolls the whole add back. Nothing is written
    anywhere, and the caller gets a 503 telling it to retry.
    """
    provider = get_provider()
    store = get_store()

    def _embed_and_upsert() -> list:
        store.ensure_collection(dimension=provider.dimension)
        points = build_points(materials, provider)
        store.upsert(points)
        return points

    try:
        points = await run_blocking(_embed_and_upsert)
    except Exception as exc:  # noqa: BLE001 - surfaced as 503, nothing written
        logger.warning("Could not index %d new material(s): %s", len(materials), exc)
        raise HTTPException(
            http_status.HTTP_503_SERVICE_UNAVAILABLE,
            f"The vector store could not be written ({exc}). Nothing was added - "
            f"the master and the index are written together or not at all. "
            f"Retry once the store is reachable.",
        ) from exc

    now = utcnow()
    for point in points:
        await session.execute(
            update(Material)
            .where(Material.material_id == point.material_id)
            .values(
                canonical_hash=point.canonical_hash,
                embedding_version=point.embedding_version,
                indexed_at=now,
            )
        )
    return len(points)


def _settle(record: StandardizationBatch, material_ids: list[str]) -> None:
    """Replace the staged rows with the ids they became.

    The batch carried a full copy of every row it judged new, so that `add`
    would write this service's decision rather than a list the client handed
    back. Once those rows are in `material` that copy is a second, stale copy
    of the master - 156 KB per 200-row batch, never read again - so it goes.

    The verdicts stay. They are why each row was judged the way it was, they
    exist nowhere else, and they are what an auditor asks for.
    """
    stored = json.loads(record.payload_json or "{}")
    stored.pop("new_material", None)
    stored["material_ids"] = material_ids
    record.payload_json = json.dumps(stored)


async def _finish(
    session: AsyncSession,
    record: StandardizationBatch,
    *,
    added: int,
    actor: str | None,
) -> None:
    record.added_rows = added
    record.status = "ADDED"
    _settle(record, [])
    session.add(AuditLog(
        actor=actor or "extraction",
        action="ADD_NEW_MATERIAL",
        entity_type="standardization_batch",
        entity_id=record.id,
        detail=json.dumps({"added": added, "reason": "no new material"}),
    ))
    await session.commit()


# --------------------------------------------------------------------------
# The audit trail
# --------------------------------------------------------------------------

async def list_batches(
    session: AsyncSession, *, limit: int = 50
) -> list[StandardizationBatch]:
    rows = await session.execute(
        select(StandardizationBatch)
        .order_by(StandardizationBatch.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars().all())


async def get_batch(session: AsyncSession, batch_id: str) -> StandardizationBatch | None:
    return await session.get(StandardizationBatch, batch_id)
