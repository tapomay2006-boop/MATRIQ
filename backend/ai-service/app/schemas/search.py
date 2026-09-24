"""POST /search: what a caller sends, and what comes back.

The response carries every number that produced the ordering - the Qdrant
cosine, the Siamese pair score, the fused score, how the candidate entered the
pool - so a reviewer can see *why* a row is where it is, and a `pipeline` block
saying which models actually ran. A result from the seeded-hash embedding or
without the reranker looks different from one with both, by design.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.logic.ranking import MatchLevel, MatchSource


class SearchRequest(BaseModel):
    query: str = Field(
        ...,
        max_length=2000,
        description=(
            "Anything: a material code (`M-55321`), a name (`V BELT`), a name with "
            "parameters (`V BELT C 120`), a sentence, or all of them together. "
            "No fixed fields."
        ),
        examples=["V BELT C 120", "M-55321", "industrial V belt C section approximately 1200 mm"],
    )
    top_k: int | None = Field(
        None, ge=1,
        description="Candidates fetched from the vector store and reranked. Default SEARCH_TOP_K.",
    )
    final_k: int | None = Field(
        None, ge=1,
        description="Results returned. Default SEARCH_FINAL_K; never more than top_k.",
    )

    @field_validator("query")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("query must not be empty")
        return value


class SearchHit(BaseModel):
    national_id: str | None
    material_id: str
    cpse_code: str
    company: str
    legacy_code: str
    description: str
    uom: str
    part_number: str
    make: str
    specifications: str
    category: str

    qdrant_score: float | None = Field(
        description=(
            "Cosine from the retrieval vector. Null when the row entered by identifier only."
        )
    )
    siamese_score: float | None = Field(
        description="Siamese pair score in [0, 1]. Null when the reranker did not run."
    )
    final_score: float = Field(
        description=(
            "The ranking key: the configured weighted sum of the two scores. A "
            "cosine-derived number, not a probability."
        )
    )
    match: bool = Field(description="True only for a high-confidence match.")
    match_level: MatchLevel
    match_source: MatchSource = Field(
        description=(
            "What decided match_level: 'exact_identifier' (a rule - the row was "
            "found by a code), 'siamese' (the trained pair model), 'retrieval_only' "
            "(no reranker; never high), or 'none'."
        )
    )
    matched_by: list[str] = Field(
        description="How the row reached the pool: 'identifier', 'vector', or both."
    )
    identifier_match: bool = Field(
        description="True when an identifier token in the query matched this row exactly."
    )
    identifier_match_type: str | None = Field(
        description="'exact' when identifier_match; null otherwise."
    )
    identifier_matched_field: str | None = Field(
        description="national_id | material_id | legacy_code | part_number, or null."
    )
    identifier_token: str | None = Field(
        description="The query token that matched, e.g. 'M-55321' or 'C-120'."
    )


class SearchPipelineInfo(BaseModel):
    """Which stages ran, on what, with which settings. Never omitted."""

    normalized_query: str
    identifiers: list[str]
    identifier_only: bool
    vector_search_ran: bool
    embedding_model: str | None
    embedding_version: str | None
    embedding_is_fallback: bool | None = Field(
        description="True = the seeded-hash stand-in: retrieval scores carry no meaning."
    )
    embedding_error: str | None = Field(
        description="Why the embedding model could not be loaded, when it could not."
    )
    vector_store: str
    store_error: str | None
    top_k: int
    final_k: int
    candidates_retrieved: int
    identifier_hits: int
    reranker_applied: bool
    reranker_model: str | None
    reranker_detail: str
    qdrant_weight: float
    siamese_weight: float
    match_threshold: float
    possible_threshold: float
    degraded: bool = Field(
        description=(
            "True when any stage did not run as designed: fallback or unloadable "
            "embedding, unreachable store, or no reranker. `warnings` says which."
        )
    )
    warnings: list[str]


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]
    total_candidates: int = Field(
        description="Distinct candidates scored before final_k was applied."
    )
    best_match_level: MatchLevel
    message: str
    pipeline: SearchPipelineInfo
