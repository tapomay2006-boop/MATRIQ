"""HTTP endpoints for search / harmonization over the vector index.

Read-only. Nothing here writes the master or the index; the reranker is loaded
on first use and never trained by a request - training is scripts/train_siamese.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.services import search as search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Find the existing materials a free-form query refers to.

        {"query": "V BELT C 120"}
        {"query": "M-55321"}
        {"query": "industrial V belt C section approximately 1200 mm"}
        {"query": "V belt C 120 length 1200 mm NTPC M-55321", "top_k": 20, "final_k": 5}

    Identifier tokens are looked up exactly in the master; the rest is embedded
    with the live provider and searched in the vector store for `top_k`
    candidates; every candidate is scored against the query by the Siamese
    reranker in one batch; the `final_k` best are returned with every score
    that produced the ordering and a three-way match level.

    400 for a query that is empty after normalisation. 503 only when the
    vector store is unreachable AND no identifier matched - with an identifier
    hit the response is 200 and carries the store error.
    """
    return await search_service.search(session, request)


@router.get("/model/info", response_model=dict)
async def model_info() -> dict:
    """Which models the search actually runs on, right now.

    The retrieval provider - loaded or not, and whether it is the seeded-hash
    fallback - the vector store, and the Siamese reranker - loaded or not, and
    if not, why. `degraded` is true unless the real embedding model AND the
    trained reranker are both live. A demo cannot claim Qwen3 retrieval or
    reranked results while this says otherwise.
    """
    from app.config import settings
    from app.logic.embedding import get_provider
    from app.services import reranker
    from app.services.jobs import run_blocking

    try:
        info = await run_blocking(lambda: get_provider().info())
        embedding = {
            "available": True,
            "configured_provider": settings.embedding_provider,
            "model_name": info.model_name,
            "model_version": info.model_version,
            "dimension": info.dimension,
            "device": settings.embedding_device,
            "is_fallback": info.is_fallback,
            "detail": info.detail,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - this endpoint reports, never fails
        embedding = {
            "available": False,
            "configured_provider": settings.embedding_provider,
            "model_name": settings.embedding_model,
            "model_version": settings.embedding_version,
            "dimension": settings.embedding_dimension,
            "device": settings.embedding_device,
            "is_fallback": None,
            "detail": "Could not be loaded.",
            "error": str(exc),
        }

    reranker_status = await run_blocking(reranker.status)
    return {
        "embedding": embedding,
        "vector_store": settings.vector_store,
        "reranker": reranker_status.as_dict(),
        "search": {
            "top_k": settings.search_top_k,
            "final_k": settings.search_final_k,
            "max_top_k": settings.search_max_top_k,
            "qdrant_weight": settings.search_qdrant_weight,
            "siamese_weight": settings.search_siamese_weight,
            "match_threshold": settings.search_match_threshold,
            "possible_threshold": settings.search_possible_threshold,
        },
        "degraded": (
            not embedding["available"] or bool(embedding["is_fallback"])
            or not reranker_status.available
        ),
    }
