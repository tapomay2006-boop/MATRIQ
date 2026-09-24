"""Request and response models for the material API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MaterialOut(BaseModel):
    """One stored row: the eight standard attributes, plus its vector state."""

    national_id: str | None = Field(
        default=None,
        description=(
            "The identifier the national master owns, e.g. NMM-00000001. "
            "Allocated by this service at admission, independent of any CPSE's "
            "coding. Null only on rows loaded by a build that predates it."
        ),
    )
    material_id: str = Field(
        description="The CPSE's identity for the row: {CPSE}-{legacy code}."
    )
    source_row: int

    cpse_code: str
    company: str
    description: str
    legacy_code: str = ""
    quantity: float | None = None
    uom: str = ""
    part_number: str = ""
    make: str = ""
    specifications: str = ""

    category: str = Field(
        default="UNCLASSIFIED",
        description=(
            "The material family, derived from the description. A filter and a "
            "blocking key - not one of the eight attributes, and never part of "
            "the vector."
        ),
    )

    attributes: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "The same eight fields under their canonical names, with absent "
            "ones omitted. This is exactly what gets embedded."
        ),
    )

    batch_id: str | None = Field(
        default=None, description="The standardization batch that admitted this row."
    )
    extraction_model: str | None = Field(
        default=None,
        description="Which Phase 1 adapter produced this row.",
    )
    embedding_version: str | None = None
    indexed: bool = Field(
        default=False, description="Whether a current vector exists for this row."
    )
    indexed_at: datetime | None = None
    created_at: datetime | None = None


class MaterialPage(BaseModel):
    """One page of the vector embedding DB's contents.

    An envelope rather than a bare list, so a client fetching ten at a time
    knows whether to ask for the next ten without a second call. `next_offset`
    is null on the last page - pass it straight back as `?offset=`.
    """

    items: list[MaterialOut]
    total: int = Field(description="Rows matching the filters, across all pages.")
    unindexed: int = Field(
        default=0,
        description=(
            "Of those, rows with no vector. Normally 0 - add writes both stores "
            "or neither - so a non-zero count is rows from an earlier build. "
            "They are in the master but not in the vector DB; delete and "
            "re-offer them to bring them in."
        ),
    )
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None = Field(
        default=None, description="Pass this as ?offset= for the next page. Null on the last."
    )


class MaterialDeleteResponse(BaseModel):
    national_id: str | None = None
    material_id: str
    deleted: bool
    vector_deleted: bool = Field(
        description=(
            "Always true on a 200: the vector is removed first, and a store "
            "that will not take the delete fails the whole call with a 503."
        )
    )
    detail: str


class AuditLogOut(BaseModel):
    id: str
    actor: str
    action: str
    entity_type: str
    entity_id: str | None = None
    detail: str | None = None
    occurred_at: datetime | None = None
