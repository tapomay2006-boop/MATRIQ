"""Request and response models for the extraction (Phase 1) endpoints.

Mirrors pipeline-one's own request shapes, so a client written against that
server works against this one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExtractTextRequest(BaseModel):
    text: str = Field(
        min_length=1,
        description="Raw, un-delimited catalogue or ERP material string.",
    )


class UpdateRecordRequest(BaseModel):
    """A correction to one extracted record.

    Accepts the canonical names and their snake_case forms alike; the session
    store resolves them. `extra="allow"` because a reviewer edits whichever
    cells were wrong, not a fixed set.
    """

    model_config = ConfigDict(extra="allow")

    company: str | None = None
    item_description_raw: str | None = None
    item_code_legacy_ref: str | None = None
    quantity: Any | None = None
    uom: str | None = None
    part_number_oem_number: str | None = None
    make_brand: str | None = None
    specifications_dimensions: str | None = None


class AbbreviationRequest(BaseModel):
    raw: str = Field(min_length=1, max_length=64, description="e.g. VLV, ALM, PRV")
    expansion: str = Field(
        min_length=1, max_length=255, description="e.g. VALVE, ALUMINIUM"
    )
    scope: str | None = Field(
        default=None, max_length=64,
        description="Optional category the mapping belongs to. Recorded, not enforced.",
    )
    actor: str | None = Field(
        default=None, max_length=120,
        description=(
            "Free-text label for whoever decided this, recorded on the audit "
            "entry. Unverified - this service has no user model - but a "
            "taxonomy change is a domain decision and should carry a name."
        ),
    )


class AbbreviationOut(BaseModel):
    raw: str
    expansion: str
    scope: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SessionSummaryOut(BaseModel):
    session_id: str
    created_at: datetime | None = None
    source_type: str
    total_records: int
    original_filename: str | None = None
    status: str = Field(
        default="PENDING_REVIEW",
        description="PENDING_REVIEW -> REVIEWED (a record was corrected) -> CHECKED",
    )
    adapter: str | None = Field(
        default=None, description="Which Phase 1 adapter produced these records."
    )
    job_id: str | None = Field(
        default=None,
        description=(
            "The background extraction job filling this session. Poll it at "
            "GET /extract/jobs/{job_id}."
        ),
    )
    requested_by: str | None = None


class SessionOut(SessionSummaryOut):
    records: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Each record carries `predicted` (what the model said) and "
            "`current` (what a reviewer left). Only `current` is forwarded."
        ),
    )


class ExtractionJobOut(BaseModel):
    """A background extraction, as a polling client reads it.

    Deliberately row-shaped rather than the service's generic job shape: what a
    client rendering an upload needs is `processed_rows / total_rows`, and the
    generic `GET /jobs/{id}` is still there for anything that wants the rest.
    """

    job_id: str
    status: str = Field(
        description="processing | completed | failed | cancelled"
    )
    processed_rows: int = 0
    total_rows: int = 0

    session_id: str | None = Field(
        default=None,
        description=(
            "The review session being filled. Present as soon as the job opens "
            "it - before any row is done - so partial records can be read from "
            "GET /extract/sessions/{session_id} while the rest run."
        ),
    )
    source_file: str | None = None

    result: dict[str, Any] | None = Field(
        default=None,
        description=(
            "The completed extraction, in exactly the shape this endpoint "
            "returned when it was synchronous. Present once status is "
            "'completed', and it stays - a client that polls late still gets it."
        ),
    )

    error: str | None = None
    error_status: int | None = Field(
        default=None,
        description="The HTTP status this failure would have had synchronously.",
    )

    started_at: str | None = None
    finished_at: str | None = None

    @property
    def progress(self) -> float:
        return self.processed_rows / self.total_rows if self.total_rows else 0.0
