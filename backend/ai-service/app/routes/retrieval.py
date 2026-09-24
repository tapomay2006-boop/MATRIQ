"""HTTP endpoints for the vector index: inspect it, and prove what is live.

Read-only. The index is written in exactly one place - POST /standardized/add -
and there is no rebuild endpoint, which is why that write is all-or-nothing.
See services/standardized.py::_index.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import indexing

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.get("/status", response_model=dict)
async def status(
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Index completeness and store connectivity. National-tier operational view."""
    return await indexing.index_status(session)


@router.get("/model/info", response_model=dict)
async def model_info() -> dict:
    """Always reports the live provider.

    A demo can never silently claim Qwen3 quality while running the seeded-hash
    fallback: is_fallback says which one answered (docs/03 §5).
    """
    from app.config import settings
    from app.logic.embedding import get_provider

    info = get_provider().info()
    return {
        "model_name": info.model_name,
        "model_version": info.model_version,
        "dimension": info.dimension,
        "is_fallback": info.is_fallback,
        "detail": info.detail,
        "vector_store": settings.vector_store,
        "ann_enabled": settings.ann_enabled,
        "top_k": settings.top_k,
    }
