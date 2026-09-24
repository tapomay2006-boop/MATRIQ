"""The master: writing standard-format rows, reading them back, removing them.

One place that knows how a `StandardMaterial` becomes a `material` row and back
again. There is exactly one writer - `POST /standardized/add` - and it goes
through `persist_rows`, so the mapping exists once and cannot drift.

This service reads no files. The only way a material enters the master is
through the standard-format boundary; the only way one leaves is
`delete_material`.
"""

from __future__ import annotations

import json
import logging

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logic.national_id import format_national_id, is_national_id
from app.logic.retrieval import get_store
from app.logic.standardize import StandardMaterial
from app.models.material import AuditLog, Material, NationalIdCounter
from app.schemas.material import MaterialDeleteResponse, MaterialOut, MaterialPage

logger = logging.getLogger(__name__)

__all__ = [
    "allocate_national_ids",
    "delete_material",
    "get_material",
    "list_materials",
    "load_materials",
    "next_source_row",
    "persist_rows",
    "purge_materials",
    "to_out",
]


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------

def persist_rows(
    session: AsyncSession,
    materials: list[StandardMaterial],
    *,
    batch_id: str | None = None,
) -> int:
    """Stage the INSERTs. No delete, no commit - the caller owns those.

    The caller owning the transaction is what lets the add path write the rows,
    upsert their vectors and stamp their index state in a single commit - which
    is the only reason the master and the index cannot drift apart.
    """
    for material in materials:
        if not material.national_id:
            raise ValueError(
                f"{material.material_id} has no national_id. Allocate with "
                f"allocate_national_ids() before persisting - a material must "
                f"never reach the master, or the index, without one."
            )
        session.add(Material(
            national_id=material.national_id,
            national_seq=int(material.national_id.rsplit("-", 1)[1]),
            material_id=material.material_id,
            source_row=material.source_row,
            cpse_code=material.cpse_code,
            cpse_name=material.company,
            legacy_code=material.legacy_code,
            description_raw=material.description,
            quantity=material.quantity,
            category=material.category,
            uom_raw=material.uom or None,
            part_number_raw=material.part_number or None,
            manufacturer_raw=material.make or None,
            specifications_raw=material.specifications or None,
            batch_id=batch_id,
            extraction_model=material.extraction_model,
        ))
    return len(materials)


async def allocate_national_ids(session: AsyncSession, count: int) -> list[str]:
    """Reserve `count` consecutive national ids. No commit.

    One UPDATE ... RETURNING on the counter row, inside the caller's
    transaction, so a batch of 200 costs one statement and two concurrent adds
    cannot be handed the same number. The counter row is created on first use.

    Called BEFORE the vector write on purpose: the id has to exist to travel in
    the vector payload, and a material must never be in the index without one.
    """
    if count <= 0:
        return []

    counter = await session.get(NationalIdCounter, 1, with_for_update=True)
    if counter is None:
        counter = NationalIdCounter(id=1, next_value=1)
        session.add(counter)
        await session.flush()

    first = counter.next_value
    counter.next_value = first + count
    await session.flush()
    return [format_national_id(first + i) for i in range(count)]


async def next_source_row(session: AsyncSession) -> int:
    """Continue the sequence rather than restarting it per batch.

    `source_row` orders the master; it is not the caller's row number, because
    every batch has a row 1.
    """
    highest = (await session.execute(
        select(func.coalesce(func.max(Material.source_row), 0))
    )).scalar_one()
    return int(highest) + 1


async def purge_materials(
    session: AsyncSession, material_ids: list[str] | None = None
) -> int:
    """Delete materials. `None` means the whole corpus. No commit.

    Vectors are handled by the caller, after the transaction commits: a
    rolled-back delete that had already dropped its vectors would leave the
    index short of rows Postgres still has, and there is no rebuild endpoint to
    put them back.
    """
    if material_ids is not None and not material_ids:
        return 0
    statement = delete(Material)
    if material_ids is not None:
        statement = statement.where(Material.material_id.in_(material_ids))
    result = await session.execute(statement)
    return result.rowcount or 0


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------

def _row_to_material(row: Material) -> StandardMaterial:
    return StandardMaterial(
        national_id=row.national_id,
        material_id=row.material_id,
        source_row=row.source_row,
        cpse_code=row.cpse_code,
        company=row.cpse_name,
        description=row.description_raw,
        legacy_code=row.legacy_code or "",
        quantity=row.quantity,
        uom=row.uom_raw or "",
        part_number=row.part_number_raw or "",
        make=row.manufacturer_raw or "",
        specifications=row.specifications_raw or "",
        category=row.category or "UNCLASSIFIED",
        extraction_model=row.extraction_model,
    )


async def load_materials(
    session: AsyncSession,
    *,
    material_ids: list[str] | None = None,
    cpse_codes: list[str] | None = None,
) -> list[StandardMaterial]:
    """Rebuild the in-memory records the indexer works on.

    Unfiltered, this is the whole corpus. The filters exist for the callers
    that do not need all of it.
    """
    statement = select(Material)
    if material_ids is not None:
        if not material_ids:
            return []
        statement = statement.where(Material.material_id.in_(material_ids))
    if cpse_codes:
        statement = statement.where(
            Material.cpse_code.in_([c.upper() for c in cpse_codes])
        )
    rows = (await session.execute(statement)).scalars().all()
    return [_row_to_material(row) for row in rows]


def to_out(row: Material) -> MaterialOut:
    """A stored row as the API returns it: the eight attributes plus state."""
    material = _row_to_material(row)
    return MaterialOut(
        national_id=row.national_id,
        material_id=row.material_id,
        source_row=row.source_row,
        cpse_code=row.cpse_code,
        company=row.cpse_name,
        description=row.description_raw,
        legacy_code=row.legacy_code or "",
        quantity=row.quantity,
        uom=row.uom_raw or "",
        part_number=row.part_number_raw or "",
        make=row.manufacturer_raw or "",
        specifications=row.specifications_raw or "",
        category=row.category or "UNCLASSIFIED",
        attributes=material.attributes,
        batch_id=row.batch_id,
        extraction_model=row.extraction_model,
        embedding_version=row.embedding_version,
        indexed=row.indexed_at is not None,
        indexed_at=row.indexed_at,
        created_at=row.created_at,
    )


async def list_materials(
    session: AsyncSession,
    *,
    cpse: str | None = None,
    national_id: str | None = None,
    category: str | None = None,
    query: str | None = None,
    indexed: bool | None = None,
    limit: int = 10,
    offset: int = 0,
) -> MaterialPage:
    """One page of the master.

    Every row by default. `add` writes Postgres and the vector store in one
    transaction, so a row normally IS a vector - but a row loaded by an earlier
    build can exist without one, and a listing that silently hid it would read
    as "no data" when the data is right there. `indexed=true` / `false` narrow
    to one side of that line; each item carries `indexed` either way, so the
    gap is visible rather than hidden.

    Paginated with a total and a `next_offset`, so a client fetching ten at a
    time never has to load the whole master to find out whether there is more.

    `query` is a SQL substring filter over description, legacy code and
    material id - a way to find a row you already know about, not a search.
    Semantic search over the vector index is a separate concern and is not
    built in this service yet.

    No tenant scoping: `cpse` is a filter the caller chooses, not a boundary
    this service enforces. api-service decides who may ask for what.
    """
    conditions = []
    if cpse:
        conditions.append(Material.cpse_code == cpse.upper())
    if national_id:
        conditions.append(Material.national_id == national_id.upper())
    if category:
        conditions.append(Material.category == category.upper())
    if indexed is True:
        conditions.append(Material.indexed_at.is_not(None))
    elif indexed is False:
        conditions.append(Material.indexed_at.is_(None))
    if query:
        pattern = f"%{query.lower()}%"
        conditions.append(
            func.lower(Material.description_raw).like(pattern)
            | func.lower(Material.legacy_code).like(pattern)
            | func.lower(Material.material_id).like(pattern)
            | func.lower(Material.national_id).like(pattern)
        )

    total = int((await session.execute(
        select(func.count()).select_from(Material).where(*conditions)
    )).scalar_one())

    rows = (await session.execute(
        select(Material)
        .where(*conditions)
        .order_by(Material.national_seq, Material.source_row)
        .offset(offset)
        .limit(limit)
    )).scalars().all()

    unindexed = int((await session.execute(
        select(func.count()).select_from(Material)
        .where(*conditions, Material.indexed_at.is_(None))
    )).scalar_one())

    end = offset + len(rows)
    return MaterialPage(
        items=[to_out(row) for row in rows],
        total=total,
        unindexed=unindexed,
        limit=limit,
        offset=offset,
        has_more=end < total,
        next_offset=end if end < total else None,
    )


async def _find(session: AsyncSession, identifier: str) -> Material | None:
    """A row by either of its identities.

    Both columns are always checked - two indexed lookups, and the order only
    decides which is tried first. That is what makes the lookup independent of
    the pattern check: a CPSE legacy code can be a bare run of digits, and an
    id issued under an earlier prefix must still be found.
    """
    first, second = (
        (Material.national_id, Material.material_id)
        if is_national_id(identifier)
        else (Material.material_id, Material.national_id)
    )
    for column in (first, second):
        row = (await session.execute(
            select(Material).where(column == identifier)
        )).scalar_one_or_none()
        if row is not None:
            return row
    return None


async def get_material(session: AsyncSession, identifier: str) -> MaterialOut | None:
    row = await _find(session, identifier)
    return None if row is None else to_out(row)


async def delete_material(
    session: AsyncSession, material_id: str, *, actor: str | None = None
) -> MaterialDeleteResponse | None:
    """Delete one material from the vector embedding DB and the master.

    Vector first, then Postgres, and the order is the guarantee. There is no
    reindex endpoint, so the one state that can never be repaired is a row in
    the master whose vector is gone - or a vector whose row is gone, which
    would keep surfacing as a neighbour that no longer opens. So:

      * the store is asked first. If it refuses, nothing has changed and the
        caller gets a 503 to retry;
      * a vector delete is idempotent, so if Postgres then fails the caller
        retries the whole call and the second attempt heals it.

    The audit entry names the caller, because this is the one irreversible
    operation in the service.
    """
    row = await _find(session, material_id)
    if row is None:
        return None
    material_id = row.material_id

    try:
        get_store().delete([material_id])
    except Exception as exc:  # noqa: BLE001 - surfaced as 503, nothing written
        logger.warning("Could not delete vector for %s: %s", material_id, exc)
        raise HTTPException(
            http_status.HTTP_503_SERVICE_UNAVAILABLE,
            f"The vector store could not be reached ({exc}). Nothing was "
            f"deleted - the vector and the master row are removed together or "
            f"not at all. Retry once the store is reachable.",
        ) from exc

    await purge_materials(session, [material_id])
    session.add(AuditLog(
        actor=actor or "system",
        action="DELETE_MATERIAL",
        entity_type="material",
        entity_id=material_id,
        detail=json.dumps({
            "national_id": row.national_id,
            "description": row.description_raw[:200],
            "cpse_code": row.cpse_code,
            "category": row.category,
        }),
    ))
    await session.commit()

    return MaterialDeleteResponse(
        national_id=row.national_id,
        material_id=material_id,
        deleted=True,
        vector_deleted=True,
        detail="Removed from the vector embedding DB and the master.",
    )
