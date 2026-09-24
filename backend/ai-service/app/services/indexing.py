"""Building a vector, and reporting the state of the index.

Two things live here and nothing else:

  `build_points`  turns standardized rows into vectors. Called from exactly one
                  place - `POST /standardized/add` - which is the only writer
                  the index has.

  `index_status`  what GET /retrieval/status reports.

There is no rebuild. The index used to be reconcilable from Postgres by
re-embedding, and `POST /retrieval/index` did that; without it the master and
the index have to be written together or not at all, which is why the add path
now rolls back rather than logging a warning (services/standardized.py::_index).

`_stale_ids` therefore reports *drift*, not *work queued*: anything it counts
is a row whose vector no longer matches its text, and the only way to repair
one now is to delete the material and offer it again.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.logic.embedding import canonical_hash, embedding_text, get_provider
from app.logic.retrieval import MaterialPoint, get_store
from app.logic.standardize import StandardMaterial
from app.models.material import Material
from app.services.jobs import run_blocking
from app.services.materials import load_materials


def build_points(
    materials: list[StandardMaterial], provider=None
) -> list[MaterialPoint]:
    """Embed in one batch. The provider L2-normalises, so cosine is a dot."""
    provider = provider or get_provider()
    if not materials:
        return []

    vectors = provider.embed(
        [embedding_text(m) for m in materials], kind="document"
    )
    return [
        MaterialPoint(
            material_id=m.material_id,
            national_id=m.national_id,
            vector=vectors[i],
            cpse_code=m.cpse_code,
            # A payload field, never part of the embedded text: the vector must
            # not move because a keyword rule fired.
            category=m.category,
            canonical_description=embedding_text(m),
            canonical_hash=canonical_hash(m),
            embedding_version=settings.embedding_version,
        )
        for i, m in enumerate(materials)
    ]


async def _stale_ids(session: AsyncSession, materials: list[StandardMaterial]) -> set[str]:
    """Materials whose stored hash no longer matches their current text, plus
    anything never indexed.

    In normal operation this is empty: the add path writes Postgres and the
    vector together or writes neither. A non-zero count means either a
    hand-edited row or a changed EMBEDDING_VERSION, and both are drift worth
    surfacing as a query rather than as silently wrong neighbours."""
    rows = (await session.execute(
        select(
            Material.material_id,
            Material.canonical_hash,
            Material.embedding_version,
            Material.indexed_at,
        )
    )).all()
    known = {r[0]: (r[1], r[2], r[3]) for r in rows}

    stale: set[str] = set()
    for material in materials:
        stored = known.get(material.material_id)
        if stored is None or stored[2] is None:
            stale.add(material.material_id)
            continue
        if stored[0] != canonical_hash(material) or stored[1] != settings.embedding_version:
            stale.add(material.material_id)
    return stale


async def index_status(session: AsyncSession) -> dict:
    """What the admin screen needs: is the index complete, and on what model."""
    materials = await load_materials(session)
    provider = get_provider()
    store = get_store()

    try:
        indexed = await run_blocking(store.count)
        reachable = True
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        # An unreachable store (or a collection that does not exist yet) is a
        # legitimate state, not a crash. It is reported, never swallowed.
        indexed, reachable = 0, False
        store_error = str(exc)
    else:
        store_error = None

    # Computed from Postgres, so it stays truthful when the store is down.
    # Reporting 0 here would say "nothing to index" when 404 rows are pending.
    stale = await _stale_ids(session, materials)
    info = provider.info()
    return {
        "materials": len(materials),
        "indexed": indexed,
        "awaiting_indexing": len(stale),
        "store": settings.vector_store,
        "store_reachable": reachable,
        "store_error": store_error,
        "provider": {
            "model_name": info.model_name,
            "model_version": info.model_version,
            "dimension": info.dimension,
            "is_fallback": info.is_fallback,
            "detail": info.detail,
        },
        "ann_enabled": settings.ann_enabled,
    }
