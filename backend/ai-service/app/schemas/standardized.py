"""Request and response models for the standard-format boundary.

The request is permissive about *where the rows come from* and strict about
*what a row is*. Three producers, one endpoint:

    {"session_id": "sess_..."}                     a reviewed extraction session
    {"rows":    [{"company": ..., ...}]}           a hand-written client
    {"records": [{"Company": ..., ...}]}           pipeline-one's forwarder envelope

All three end in the same check, which is why there is no separate "forward"
endpoint: looking a session up and calling the check IS the check. It also
means a pipeline-one server running elsewhere can point NEXT_PIPELINE_URL
straight at POST /api/v1/standardized/check with no adapter in between.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StandardBatchIn(BaseModel):
    """N standard-format rows, however they arrive and however they are spelled."""

    model_config = ConfigDict(extra="allow")

    rows: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "The standardized rows. Each is an object keyed by the eight "
            "canonical CPSE attributes - 'Company', 'Item Description (Raw)', "
            "'Item Code / Legacy Ref', 'Quantity', 'UOM', "
            "'Part Number / OEM Number', 'Make / Brand', "
            "'Specifications / Dimensions' - or their snake_case equivalents. "
            "'NA' means absent. Extra keys (_record_id, _raw_input and the "
            "like) are carried past without complaint."
        ),
    )
    records: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Alias for `rows`, so pipeline-one's forwarder envelope posts here "
            "unchanged. Supply one or the other, not both."
        ),
    )
    session_id: str | None = Field(
        default=None, max_length=64,
        description=(
            "A review session from POST /extract/csv or /extract/text. Its "
            "corrected records (`current`, never `predicted`) become the rows, "
            "so a reviewed extraction reaches the check without the caller "
            "having to unpack it. Send this INSTEAD of rows, not alongside."
        ),
    )
    source_pipeline: str | None = Field(
        default=None, max_length=64,
        description="Who produced these rows. A label, recorded, never trusted.",
    )
    default_company: str | None = Field(
        default=None, max_length=120,
        description=(
            "Used for rows whose Company is absent. Without it such a row is "
            "reported INVALID rather than attributed to the wrong CPSE."
        ),
    )
    requested_by: str | None = Field(
        default=None, max_length=120,
        description=(
            "Free-text label for whoever sent this, recorded on the batch. "
            "Unverified - this service has no user model."
        ),
    )

    @model_validator(mode="after")
    def _exactly_one_source(self) -> StandardBatchIn:
        if self.records:
            if self.rows:
                raise ValueError(
                    "Send either 'rows' or 'records', not both - they are the "
                    "same field under two names."
                )
            self.rows = self.records

        if self.session_id and self.rows:
            raise ValueError(
                "Send either 'session_id' or the rows themselves, not both. "
                "With a session_id the rows are read from the session, so a "
                "second list could silently disagree with what was reviewed."
            )
        if not self.session_id and not self.rows:
            raise ValueError(
                "Nothing to check. Send 'session_id' for a reviewed extraction "
                "session, or the standard-format rows in 'rows' / 'records'."
            )
        return self


class NeighbourOut(BaseModel):
    material_id: str
    score: float


class CheckedRowOut(BaseModel):
    row_number: int
    status: str = Field(
        description="NEW | ALREADY_EXISTS | DUPLICATE_IN_BATCH | INVALID"
    )
    description: str = ""
    material_id: str | None = Field(
        default=None,
        description="The id this row would be stored under.",
    )
    category: str = Field(
        default="UNCLASSIFIED",
        description="The material family this row was classified into.",
    )
    embedded_text: str | None = Field(
        default=None,
        description=(
            "Exactly what would be embedded for this row. Note the category is "
            "NOT in it - a keyword rule must not be able to move a vector."
        ),
    )

    matched_material_id: str | None = Field(
        default=None, description="What it collided with, when it exists already."
    )
    matched_by: str | None = Field(
        default=None,
        description="MATERIAL_ID | CANONICAL_HASH | VECTOR_SIMILARITY",
    )
    similarity: float | None = Field(
        default=None, description="Cosine against the nearest indexed vector."
    )
    duplicate_of_row: int | None = None
    reason: str = ""
    neighbours: list[NeighbourOut] = Field(
        default_factory=list,
        description="Nearest indexed vectors, best first. Evidence, not a verdict.",
    )
    error: str | None = None


class CheckResponse(BaseModel):
    """The split: what is already in the vector embedding DB, and what is not."""

    batch_id: str
    has_new_data: bool = Field(
        description=(
            "False when every incoming row is already in the vector embedding "
            "DB. There is then nothing to add and `new_material` is empty."
        )
    )
    message: str

    total_rows: int
    new_rows: int
    existing_rows: int
    duplicate_rows_in_batch: int = 0
    invalid_rows: int = 0

    new_material: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "ONLY the rows that are not already in the vector embedding DB, in "
            "standard format and ready to be added. This is the answer to "
            "'which of my N rows are new'."
        ),
    )
    rows: list[CheckedRowOut] = Field(
        default_factory=list,
        description="Every incoming row with its verdict, for audit.",
    )
    existence_threshold: float
    vector_store: str
    embedding_provider: str
    indexed_total: int | None = Field(
        default=None,
        description="Vectors in the store when the check ran. Null if unreachable.",
    )


class AddRequest(BaseModel):
    """Add new material to the vector embedding DB.

    Give a `batch_id` - the normal path. The rows added are the ones the check
    judged NEW, so a caller cannot talk this endpoint into indexing a row that
    already exists.

    `rows` is the standalone path for a caller that never called check. It is
    checked here before anything is written, so it carries the same guarantee.
    """

    model_config = ConfigDict(extra="allow")

    batch_id: str | None = Field(
        default=None, description="A batch id returned by POST /standardized/check."
    )
    rows: list[dict[str, Any]] | None = Field(
        default=None, description="Standard-format rows, when no batch_id is given."
    )
    records: list[dict[str, Any]] | None = Field(
        default=None, description="Alias for `rows`."
    )
    default_company: str | None = Field(default=None, max_length=120)
    requested_by: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def _one_source(self) -> AddRequest:
        if self.records and not self.rows:
            self.rows = self.records
        if bool(self.batch_id) == bool(self.rows):
            raise ValueError(
                "Send exactly one of 'batch_id' (the rows a check judged new) "
                "or 'rows' (standard-format rows to check and add in one step)."
            )
        return self


class AddedMaterialOut(BaseModel):
    national_id: str = Field(description="Allocated at admission, e.g. NMM-00000001.")
    material_id: str
    row_number: int = Field(description="The caller's row number, not source_row.")
    description: str
    cpse_code: str


class AddResponse(BaseModel):
    batch_id: str
    added: int = Field(description="Rows written to Postgres and the vector DB.")
    requested: int
    skipped_existing: int = 0
    skipped_invalid: int = 0
    indexed: int = Field(
        default=0,
        description=(
            "Vectors upserted. Always equal to `added`: the master and the "
            "index are written in one transaction, so a store that cannot be "
            "written fails the whole call with a 503 and adds nothing."
        ),
    )
    materials: list[AddedMaterialOut] = Field(default_factory=list)
    material_ids: list[str] = Field(default_factory=list)
    national_ids: list[str] = Field(
        default_factory=list,
        description="The national ids issued to the added rows, in the same order.",
    )
    message: str = ""


class BatchOut(BaseModel):
    id: str
    status: str
    source: str | None = None
    source_session_id: str | None = None
    total_rows: int
    new_rows: int
    existing_rows: int
    duplicate_rows: int
    invalid_rows: int
    added_rows: int
    requested_by: str | None = None
    cpse_code: str | None = None
    created_at: datetime | None = None
