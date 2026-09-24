"""Search / harmonization: find the existing materials a query refers to.

                    query
                      │
                      ▼
              logic/query.prepare        normalise; pull out identifier tokens
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
   exact lookup             Qwen3 query vector
   (Postgres: national id,        │
    material id, legacy code,     ▼
    part number)              vector store  ──►  top-K candidates
          │                       │
          └───────────┬───────────┘
                      ▼
               candidate pool  ──►  rows from Postgres
                      │
                      ▼
            Siamese reranker: (query, candidate) x K, ONE batch
                      │
                      ▼
           logic/ranking: fuse, classify, order  ──►  final_k results

Two stages of retrieval, and the split is the design. The identifier stage is
exact and model-independent: a code is looked up, not embedded. The vector
stage is the existing index, queried through the existing store interface
with the existing provider - nothing about how materials are embedded or
stored changes for search to exist. The Siamese stage never sees the corpus;
it sees the K candidates the two stages surfaced, and scores them in one
batched pass.

Two signals, kept apart in the response. An exact identifier hit is a rule -
`identifier_match: true`, the field it matched on, `match_source:
"exact_identifier"` - and it decides `high` on its own. The Siamese score is
a model's opinion about the pair and is reported as exactly that; when it
decides, `match_source` is `"siamese"`. A row can carry both, and a low
Siamese score next to an identifier hit is normal for a query that was mostly
a code.

Degradation is explicit. No reranker: results are ordered by the Qdrant score,
`siamese_score` is null, and no result can be `high` by similarity. Embedding
model not loadable, or the seeded-hash fallback in use: `pipeline.degraded`
is true with the reason in `pipeline.warnings`. Store unreachable: identifier
hits, if any, are still returned and the response carries the error; with
nothing else to answer from, a 503. Nothing is hidden.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.logic.embedding import ProviderInfo, get_provider
from app.logic.identity import normalize_legacy_code
from app.logic.query import PreparedQuery, identifier_variants, prepare
from app.logic.ranking import (
    BY_IDENTIFIER,
    BY_VECTOR,
    MatchLevel,
    MatchSource,
    RankedCandidate,
    ScoringPolicy,
    rank,
)
from app.logic.retrieval import BlockingFilter, RetrievedCandidate, get_store
from app.logic.standardize import StandardMaterial
from app.models.material import Material
from app.schemas.search import SearchHit, SearchPipelineInfo, SearchRequest, SearchResponse
from app.services import reranker as reranker_service
from app.services.jobs import run_blocking
from app.services.materials import load_materials

logger = logging.getLogger(__name__)

__all__ = ["search"]

#: Rows one identifier lookup may return. A legacy code shared by many CPSEs
#: is a real condition; an identifier that matches hundreds of rows is not an
#: identifier, and the vector stage is the better answer for it.
_IDENTIFIER_HIT_LIMIT = 50


# --------------------------------------------------------------------------
# Stage 0: exact identifier lookup
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class IdentifierHit:
    material_id: str
    field: str
    """Which stored field the token matched: national_id, material_id,
    legacy_code or part_number."""
    token: str


async def _lookup_identifiers(
    session: AsyncSession, tokens: list[str]
) -> dict[str, IdentifierHit]:
    """Rows whose national id, material id, legacy code or part number is one
    of the identifier tokens, under any spelling `identifier_variants`
    accepts - and WHICH field matched, so the response can say so.

    Postgres, not Qdrant: the legacy code and part number exist only in the
    master, and an exact lookup is a WHERE clause, not a nearest neighbour.
    """
    if not tokens:
        return {}

    variants_by_token: dict[str, list[str]] = {t: identifier_variants(t) for t in tokens}
    variants: set[str] = {v for vs in variants_by_token.values() for v in vs}
    legacy_by_token = {t: normalize_legacy_code(t) for t in tokens}

    conditions = [
        Material.national_id.in_(variants),
        Material.material_id.in_(variants),
        func.upper(Material.legacy_code).in_(variants),
        func.upper(Material.part_number_raw).in_(variants),
    ]
    for legacy in legacy_by_token.values():
        # `M-55321` is stored in material_id as `NTPC-M55321`, or as
        # `NTPC-M55321-<suffix>` when the code collided (logic/identity.py).
        if legacy:
            conditions.append(Material.material_id.like(f"%-{legacy}"))
            conditions.append(Material.material_id.like(f"%-{legacy}-%"))

    rows = (await session.execute(
        select(
            Material.material_id, Material.national_id,
            Material.legacy_code, Material.part_number_raw,
        )
        .where(or_(*conditions))
        .limit(_IDENTIFIER_HIT_LIMIT)
    )).all()

    hits: dict[str, IdentifierHit] = {}
    for material_id, national_id, legacy_code, part_number in rows:
        hit = _explain_hit(
            material_id=str(material_id),
            national_id=(national_id or "").upper(),
            legacy_code=(legacy_code or "").upper(),
            part_number=(part_number or "").upper(),
            variants_by_token=variants_by_token,
            legacy_by_token=legacy_by_token,
        )
        if hit is not None:
            hits[hit.material_id] = hit
    return hits


def _explain_hit(
    *,
    material_id: str,
    national_id: str,
    legacy_code: str,
    part_number: str,
    variants_by_token: dict[str, list[str]],
    legacy_by_token: dict[str, str | None],
) -> IdentifierHit | None:
    """Name the field and the token a row was found by. The order is the
    strength of the identity: the national id and the material id are unique
    by construction, a legacy code is unique within a CPSE, a part number is
    whatever the catalogue said it was."""
    for token, variants in variants_by_token.items():
        if national_id and national_id in variants:
            return IdentifierHit(material_id, "national_id", token)
    for token, variants in variants_by_token.items():
        if material_id in variants:
            return IdentifierHit(material_id, "material_id", token)
    for token, variants in variants_by_token.items():
        if legacy_code and legacy_code in variants:
            return IdentifierHit(material_id, "legacy_code", token)
    for token, variants in variants_by_token.items():
        if part_number and part_number in variants:
            return IdentifierHit(material_id, "part_number", token)
    for token, legacy in legacy_by_token.items():
        # The code was typed in a spelling the stored legacy code does not
        # use, but the material id was built from its normalised form.
        if legacy and (
            material_id.endswith(f"-{legacy}") or f"-{legacy}-" in material_id
        ):
            return IdentifierHit(material_id, "material_id", token)
    return None


# --------------------------------------------------------------------------
# Stage 1: vector retrieval
# --------------------------------------------------------------------------

def _embed(text: str) -> tuple[np.ndarray, ProviderInfo]:
    """The existing provider, exactly as the existence check uses it."""
    provider = get_provider()
    return provider.embed([text], kind="query")[0], provider.info()


def _search_store(vector: np.ndarray, top_k: int) -> list[RetrievedCandidate]:
    """The existing store. `embedding_version` is always in the block: a
    neighbour from a different model's vectors is not a neighbour."""
    return get_store().search(
        vector,
        top_k=top_k,
        block=BlockingFilter(embedding_version=settings.embedding_version),
    )


def _embedding_status() -> tuple[ProviderInfo | None, str | None]:
    """The provider's self-description, or why it could not be built."""
    try:
        return get_provider().info(), None
    except Exception as exc:  # noqa: BLE001 - reported, never raised from here
        return None, str(exc)


# --------------------------------------------------------------------------
# The pipeline
# --------------------------------------------------------------------------

def _resolve_k(request: SearchRequest) -> tuple[int, int]:
    top_k = min(request.top_k or settings.search_top_k, settings.search_max_top_k)
    final_k = min(request.final_k or settings.search_final_k, top_k)
    return max(1, top_k), max(1, final_k)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _hit(candidate: RankedCandidate, material: StandardMaterial) -> SearchHit:
    return SearchHit(
        national_id=material.national_id,
        material_id=material.material_id,
        cpse_code=material.cpse_code,
        company=material.company,
        legacy_code=material.legacy_code,
        description=material.description,
        uom=material.uom,
        part_number=material.part_number,
        make=material.make,
        specifications=material.specifications,
        category=material.category,
        qdrant_score=_round(candidate.qdrant_score),
        siamese_score=_round(candidate.siamese_score),
        final_score=candidate.final_score,
        match=candidate.level is MatchLevel.HIGH,
        match_level=candidate.level,
        match_source=candidate.source,
        matched_by=list(candidate.matched_by),
        identifier_match=candidate.identifier_hit,
        identifier_match_type="exact" if candidate.identifier_hit else None,
        identifier_matched_field=candidate.identifier_field,
        identifier_token=candidate.identifier_token,
    )


def _message(
    hits: list[SearchHit], *, best: MatchLevel, reranker_applied: bool,
    store_error: str | None, embedding_error: str | None, vector_search_ran: bool,
) -> str:
    if not hits:
        if embedding_error:
            return f"No results: the embedding model could not be loaded ({embedding_error})."
        if store_error:
            return f"No results: the vector store could not be reached ({store_error})."
        if not vector_search_ran:
            return "No results: the identifier was not found in the master."
        return "No results: the vector embedding DB returned no candidates for this query."

    high = sum(1 for h in hits if h.match_level is MatchLevel.HIGH)
    exact = sum(1 for h in hits if h.match_source is MatchSource.EXACT_IDENTIFIER)
    possible = sum(1 for h in hits if h.match_level is MatchLevel.POSSIBLE)
    if best is MatchLevel.HIGH:
        text = f"{high} high-confidence match(es)"
        if exact:
            text += f" ({exact} by exact identifier)"
        if possible:
            text += f" and {possible} possible"
    elif best is MatchLevel.POSSIBLE:
        text = f"{possible} possible match(es), none high-confidence"
    else:
        text = f"{len(hits)} nearest material(s), none a confident match"
    if not reranker_applied:
        text += ". Siamese reranker not applied - ordering is by retrieval score only"
    if embedding_error:
        text += f". Embedding model unavailable ({embedding_error}); identifier lookup only"
    elif store_error:
        text += f". Vector store unavailable ({store_error}); identifier lookup only"
    return text + "."


async def search(session: AsyncSession, request: SearchRequest) -> SearchResponse:
    prepared: PreparedQuery = prepare(request.query)
    if prepared.is_empty:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            "The query is empty after normalisation. Send a material code, a name, "
            "a description, or any combination of them.",
        )
    top_k, final_k = _resolve_k(request)
    warnings: list[str] = []

    # Stage 0 - exact identifiers. Free, exact, model-independent.
    identifier_hits = await _lookup_identifiers(session, prepared.identifiers)

    # Stage 1 - the vector index. Skipped only when the query was nothing but
    # identifiers AND they were found: there is no descriptive content left to
    # embed, and the exact hit is the answer.
    retrieved: list[RetrievedCandidate] = []
    store_error: str | None = None
    embedding_error: str | None = None
    embedding: ProviderInfo | None = None
    vector_search_ran = not (prepared.identifier_only and identifier_hits)
    if vector_search_ran:
        try:
            vector, embedding = await run_blocking(_embed, prepared.text)
        except Exception as exc:  # noqa: BLE001 - degraded or 503, never a 500
            embedding_error = str(exc)
            logger.warning("Embedding model unavailable: %s", exc)
        else:
            try:
                retrieved = await run_blocking(_search_store, vector, top_k)
            except Exception as exc:  # noqa: BLE001
                store_error = str(exc)
                logger.warning("Vector search unavailable: %s", exc)
        if (embedding_error or store_error) and not identifier_hits:
            reason = embedding_error or store_error
            what = "The embedding model could not be loaded" if embedding_error else (
                "The vector store could not be searched"
            )
            raise HTTPException(
                http_status.HTTP_503_SERVICE_UNAVAILABLE,
                f"{what} ({reason}) and the query matched no identifier. "
                f"Retry once it is available.",
            )
    if embedding is None:
        embedding, info_error = _embedding_status()
        embedding_error = embedding_error or info_error
    if embedding_error:
        warnings.append(f"Embedding model unavailable: {embedding_error}")
    elif embedding is not None and embedding.is_fallback:
        warnings.append(
            "EMBEDDING_PROVIDER is the seeded-hash fallback: retrieval scores carry no "
            "semantic signal and the candidate pool is not meaningful. Set "
            "EMBEDDING_PROVIDER=qwen3."
        )
    if store_error:
        warnings.append(f"Vector store unavailable: {store_error}")

    # The pool: every candidate once, remembering how it got in. A store that
    # returns the same id twice, or an id that is also an identifier hit, is
    # one candidate.
    pool: dict[str, RankedCandidate] = {}
    for candidate in retrieved:
        entry = pool.get(candidate.material_id)
        if entry is None:
            pool[candidate.material_id] = RankedCandidate(
                material_id=candidate.material_id,
                qdrant_score=candidate.embedding_score,
                matched_by=[BY_VECTOR],
            )
        elif entry.qdrant_score is None or candidate.embedding_score > entry.qdrant_score:
            entry.qdrant_score = candidate.embedding_score
    for material_id, hit in identifier_hits.items():
        entry = pool.setdefault(material_id, RankedCandidate(material_id=material_id))
        if BY_IDENTIFIER not in entry.matched_by:
            entry.matched_by.append(BY_IDENTIFIER)
        entry.identifier_field = hit.field
        entry.identifier_token = hit.token

    # The rows. A point the store has and the master does not is drift; it is
    # logged and dropped rather than returned as a result with no content.
    materials = await load_materials(session, material_ids=list(pool))
    by_id = {m.material_id: m for m in materials}
    missing = [m for m in pool if m not in by_id]
    if missing:
        logger.warning(
            "Vector store returned %d id(s) absent from the master: %s",
            len(missing), missing[:5],
        )
        for material_id in missing:
            pool.pop(material_id, None)

    # Stage 2 - the Siamese reranker, over the pool only, in one batch.
    reranker = reranker_service.get_reranker()
    reranker_applied = False
    reranker_detail = reranker_service.status().detail
    if reranker is not None and pool:
        ordered = list(pool.values())
        texts = [reranker_service.candidate_text(by_id[c.material_id]) for c in ordered]
        try:
            scores = await run_blocking(reranker.score_pairs, prepared.text, texts)
            for candidate, score in zip(ordered, scores, strict=True):
                candidate.siamese_score = float(score)
            reranker_applied = True
            reranker_detail = f"Applied to {len(ordered)} candidate(s) in one batch."
        except Exception as exc:  # noqa: BLE001 - degraded, and reported as such
            logger.warning("Siamese reranker failed; ordering by retrieval score: %s", exc)
            reranker_detail = f"Reranker failed on this query ({exc}); ordered by retrieval score."
    if not reranker_applied:
        warnings.append(f"Siamese reranker not applied: {reranker_detail}")

    # Stage 3 - one ordering, one decision per candidate.
    policy = ScoringPolicy(
        qdrant_weight=settings.search_qdrant_weight,
        siamese_weight=settings.search_siamese_weight,
        match_threshold=settings.search_match_threshold,
        possible_threshold=settings.search_possible_threshold,
        reranker_applied=reranker_applied,
    )
    ranked = rank(list(pool.values()), policy)
    hits = [_hit(c, by_id[c.material_id]) for c in ranked[:final_k]]
    best = max((h.match_level for h in hits), key=_LEVEL_RANK.__getitem__, default=MatchLevel.NONE)

    reranker_status = reranker_service.status()
    return SearchResponse(
        query=request.query,
        results=hits,
        total_candidates=len(ranked),
        best_match_level=best,
        message=_message(
            hits, best=best, reranker_applied=reranker_applied, store_error=store_error,
            embedding_error=embedding_error, vector_search_ran=vector_search_ran,
        ),
        pipeline=SearchPipelineInfo(
            normalized_query=prepared.text,
            identifiers=list(prepared.identifiers),
            identifier_only=prepared.identifier_only,
            vector_search_ran=vector_search_ran,
            embedding_model=embedding.model_name if embedding else None,
            embedding_version=embedding.model_version if embedding else None,
            embedding_is_fallback=embedding.is_fallback if embedding else None,
            embedding_error=embedding_error,
            vector_store=settings.vector_store,
            store_error=store_error,
            top_k=top_k,
            final_k=final_k,
            candidates_retrieved=len(retrieved),
            identifier_hits=len(identifier_hits),
            reranker_applied=reranker_applied,
            reranker_model=reranker_status.model_name if reranker_applied else None,
            reranker_detail=reranker_detail,
            qdrant_weight=policy.qdrant_weight,
            siamese_weight=policy.siamese_weight,
            match_threshold=policy.match_threshold,
            possible_threshold=policy.possible_threshold,
            degraded=bool(warnings),
            warnings=warnings,
        ),
    )


_LEVEL_RANK = {MatchLevel.NONE: 0, MatchLevel.POSSIBLE: 1, MatchLevel.HIGH: 2}
