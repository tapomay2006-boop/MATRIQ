"""HTTP endpoints for the master: browse it, fetch one row, delete one.

Read-only apart from the delete. Material enters through the standard-format
boundary and nowhere else - see routes/standardized.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.material import MaterialDeleteResponse, MaterialOut, MaterialPage
from app.services import materials

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("", response_model=MaterialPage)
async def list_materials(
    limit: int = Query(10, ge=1, le=500, description="Rows per page. Ten by default."),
    offset: int = Query(0, ge=0, description="Pass the previous page's next_offset."),
    cpse: str | None = Query(None, description="Narrow to one CPSE code"),
    national_id: str | None = Query(None, description="Exactly one national id"),
    category: str | None = Query(
        None, description="Narrow to one material family, e.g. BEARING, VALVE"
    ),
    query: str | None = Query(
        None,
        description=(
            "Substring filter over description, legacy code and material id. "
            "A way to find a row you already know about - not semantic search."
        ),
    ),
    indexed: bool | None = Query(
        None,
        description=(
            "Omit for every row. true = rows with a vector (in the vector "
            "embedding DB). false = rows without one - loaded by an earlier "
            "build, not yet in the vector DB."
        ),
    ),
    session: AsyncSession = Depends(get_db),
) -> MaterialPage:
    """The master, ten at a time.

        GET /materials                    -> first 10, plus total and next_offset
        GET /materials?offset=10          -> the next 10
        GET /materials?offset=<next_offset> ... until has_more is false

    Never the whole master in one response: `limit` caps at 500, and the
    envelope carries `total` so a client can render a page count without
    fetching everything to find out.

    `unindexed` in the envelope, and `indexed` on each item, say whether a row
    is actually in the vector DB. Normally every row is; a non-zero
    `unindexed` means rows from before the current pipeline.
    """
    return await materials.list_materials(
        session, cpse=cpse, national_id=national_id, category=category,
        query=query, indexed=indexed, limit=limit, offset=offset,
    )


@router.get("/{material_id}", response_model=MaterialOut)
async def get_material(
    material_id: str = Path(description="A national id (NMM-…) or a material id (NTPC-…)"),
    session: AsyncSession = Depends(get_db),
) -> MaterialOut:
    """One material by either of its identities.

    Accepts the national id (`NMM-00000042`) or the CPSE's material id
    (`NTPC-1001`). The response carries both.
    """
    found = await materials.get_material(session, material_id)
    if found is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Unknown material {material_id!r}"
        )
    return found


@router.delete("/{material_id}", response_model=MaterialDeleteResponse)
async def delete_material(
    material_id: str,
    actor: str | None = Query(
        None,
        max_length=120,
        description=(
            "Free-text label recorded on the audit entry. Unverified, but this "
            "is the one irreversible operation here, so it should be supplied."
        ),
    ),
    session: AsyncSession = Depends(get_db),
) -> MaterialDeleteResponse:
    """Delete a material from the vector embedding DB and the master.

    By national id or material id. The vector goes first. A store that cannot
    be reached fails the call with a 503 and nothing is deleted - the two are
    removed together or not at all, and the call is safe to retry.
    """
    result = await materials.delete_material(session, material_id, actor=actor)
    if result is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Unknown material {material_id!r}"
        )
    return result
