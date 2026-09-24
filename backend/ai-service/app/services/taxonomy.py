"""The CPSE abbreviation taxonomy, in Postgres.

`expand_abbreviations` stays where it is - vendored, in `logic/extraction.py`.
The algorithm is pipeline-one's and is not this service's to reimplement. What
moves here is *where an addition lives*.

Three layers, applied in that order:

    1. DEFAULT_CPSE_ABBREVIATIONS   curated, in logic/extraction.py
    2. data/config/abbreviations.csv  the shipped seed file
    3. this table                    everything added at runtime

1 and 2 are read when the engine imports. 3 is applied over them at startup by
`sync_to_engine`, and again on every add, so the registry a worker holds is the
baseline plus the database - never one worker's private history.

Why not keep appending to the CSV, which is what the vendored
`register_abbreviation(persist=True)` does:

  * the registry it mutates is a module-level dict, so an addition reached one
    uvicorn worker and no other until a restart;
  * an unsynchronised append from several workers interleaves rows;
  * the file lives inside the container, so a redeploy forgot everything;
  * and it recorded no actor, so nobody could say who decided `PRV` means
    `PRESSURE RELIEF VALVE`.

Every one of those is a property of the storage, not of the algorithm - which
is why only the storage changed.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import Abbreviation
from app.models.material import AuditLog

logger = logging.getLogger(__name__)

__all__ = ["add", "count", "list_all", "sync_to_engine"]


def _apply(raw: str, expansion: str, scope: str = "") -> bool:
    """Push one mapping into the engine's live registry.

    `persist=False`: the CSV is the shipped baseline and stays read-only from
    here. Postgres is where a runtime addition belongs, and writing it in two
    places would let them disagree.
    """
    from app.logic.extraction import register_abbreviation

    return bool(register_abbreviation(raw, expansion, scope=scope, persist=False))


async def sync_to_engine(db: AsyncSession) -> int:
    """Apply every stored abbreviation over the engine's baseline.

    Called once at startup, so a worker that has just booted expands exactly
    what every other worker expands. Idempotent - the registry is a dict.
    """
    rows = (await db.execute(select(Abbreviation))).scalars().all()
    applied = sum(_apply(r.raw, r.expansion, r.scope or "") for r in rows)
    if applied:
        logger.info("Applied %d stored abbreviation(s) to the extraction engine", applied)
    return applied


async def add(
    db: AsyncSession,
    *,
    raw: str,
    expansion: str,
    scope: str = "",
    actor: str | None = None,
) -> Abbreviation | None:
    """Register an abbreviation. Returns None if either side is empty.

    Written to the database first and applied to the live registry second: a
    mapping this process expands but has not stored would vanish on restart and
    was never true for any other worker.

    Re-registering an existing `raw` updates it rather than failing. A taxonomy
    correction - `PRV` was mapped wrong and is being fixed - is the common case,
    and refusing it would push people back to editing the CSV by hand.
    """
    raw_clean = (raw or "").strip().upper()
    exp_clean = (expansion or "").strip().upper()
    if not raw_clean or not exp_clean:
        return None

    existing = (await db.execute(
        select(Abbreviation).where(Abbreviation.raw == raw_clean)
    )).scalar_one_or_none()

    if existing is None:
        entry = Abbreviation(
            raw=raw_clean, expansion=exp_clean,
            scope=(scope or "").strip() or None, created_by=actor,
        )
        db.add(entry)
        action = "ADD_ABBREVIATION"
        previous = None
    else:
        entry = existing
        previous = entry.expansion
        entry.expansion = exp_clean
        entry.scope = (scope or "").strip() or entry.scope
        action = "UPDATE_ABBREVIATION"

    db.add(AuditLog(
        actor=actor or "system",
        action=action,
        entity_type="abbreviation",
        entity_id=raw_clean,
        detail=json.dumps(
            {"raw": raw_clean, "expansion": exp_clean, "scope": scope or None}
            | ({"previous": previous} if previous else {})
        ),
    ))
    await db.commit()
    await db.refresh(entry)

    _apply(raw_clean, exp_clean, scope or "")
    return entry


async def list_all(db: AsyncSession, *, limit: int = 500) -> list[Abbreviation]:
    rows = await db.execute(
        select(Abbreviation).order_by(Abbreviation.raw).limit(limit)
    )
    return list(rows.scalars().all())


async def count(db: AsyncSession) -> int:
    return int(
        (await db.execute(select(func.count()).select_from(Abbreviation))).scalar_one()
    )
