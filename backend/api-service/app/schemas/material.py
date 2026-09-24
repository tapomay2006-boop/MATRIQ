"""Foundational domain schemas for Unified Material Intelligence."""

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field



class MaterialAttribute(BaseModel):
    """Normalized technical attribute key-value pair."""

    name: str
    value: str | float | int | bool
    unit: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class IngestionErrorItem(BaseModel):
    """Details for a single record validation failure or duplicate error."""

    row: int
    legacy_code: str | None = None
    reason: str


class MaterialIngestionResponse(BaseModel):
    """Result summary of a batch material ingestion operation."""

    ingestion_id: str
    filename: str
    total_records: int
    accepted_records: int
    rejected_records: int
    duplicate_records: int
    errors: list[IngestionErrorItem] = Field(default_factory=list)


class MaterialRecordInput(BaseModel):
    """Standardized internal representation of an ingested material record."""

    organization: str
    legacy_code: str
    description: str
    uom: str | None = None
    item_name: str | None = None
    part_number: str | None = None
    manufacturer: str | None = None
    equipment_compatibility: str | None = None
    material_type: str | None = None
    category: str | None = None
    specification: str | None = None
    national_id: str | None = None
    status: str | None = "AVAILABLE"
    source_file: str | None = None
    source_row: int | None = None


class MaterialResponse(BaseModel):
    """API response model for a single persisted material record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization: str
    legacy_code: str
    description: str
    uom: str | None = None
    item_name: str | None = None
    part_number: str | None = None
    manufacturer: str | None = None
    equipment_compatibility: str | None = None
    material_type: str | None = None
    category: str | None = None
    specification: str | None = None
    national_id: str | None = None
    status: str | None = "AVAILABLE"
    source_file: str | None = None
    source_row: int | None = None
    created_at: datetime
    updated_at: datetime


class MaterialListResponse(BaseModel):
    """Paginated list of material catalog items."""

    items: list[MaterialResponse]
    total: int
    limit: int
    offset: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 1


class MaterialQualityStats(BaseModel):
    """Deterministic calculation of completeness metrics across all material master records."""

    total_materials: int
    organizations: int
    missing_uom: int
    missing_manufacturer: int
    missing_part_number: int
    missing_category: int
    assigned_count: int = 0
    unassigned_count: int = 0



class MaterialBase(BaseModel):
    """Core material entity foundation."""

    id: str | None = None
    item_code: str
    description: str
    organization_id: str | None = None
    category: str | None = None
    attributes: list[MaterialAttribute] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EquivalentMatchStub(BaseModel):
    """Match recommendation between material items."""

    source_item_id: str
    target_item_id: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    match_status: str = "pending"  # "pending", "verified", "rejected"
    matched_attributes: list[str] = Field(default_factory=list)
    rationale: str | None = None


class ReviewStub(BaseModel):
    """Verification review record for material harmonization."""

    id: str | None = None
    match_id: str
    reviewer_id: str
    decision: str  # "approved", "rejected", "modified"
    comments: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

