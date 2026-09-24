"""The material table, and the audit trail.

One row per material, holding the eight standard-format attributes exactly as
Phase 1 produced them plus the state of its vector.

There is no `standardized_material` table any more, and no `material_attribute`
or `quality_flag` alongside it. Those existed to hold a second, derived
representation of a row - a category, typed attributes with roles, a canonical
text - built by a processing chain this service no longer runs. Phase 1 emits
the standard format; the standard format is what gets stored and what gets
embedded. A derived copy of it would be a copy with nothing added.

The vector stamps moved here for the same reason. `canonical_hash` detects a
vector whose source text has since changed, and `indexed_at IS NULL` finds
everything awaiting indexing in one query - both are properties of the material
row itself, not of a table that no longer exists.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Material(Base):
    """One standard-format row, as Phase 1 produced it."""

    __tablename__ = "material"
    __table_args__ = (Index("ix_material_cpse_legacy", "cpse_code", "legacy_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    national_id: Mapped[str | None] = mapped_column(String(24), unique=True, index=True)
    """The identifier the national master owns: NMM-00000001.

    Allocated by this service when the row is admitted, before its vector is
    written, from a database counter - so it is unique by construction and
    independent of how any CPSE codes its own catalogue. See logic/national_id.py.

    Nullable only for rows loaded by a build that predates it; every row that
    goes through POST /standardized/add has one."""

    national_seq: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    """The integer behind national_id, for ordering and range queries."""

    material_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    """{CPSE}-{legacy code}, or a content hash when the row carries no code.
    Stable across re-upload and order-independent - see logic/identity.py.

    This is the CPSE's identity for the row, not the nation's. Two CPSEs holding
    the same article have two of these and, once matched, should share one
    national_id."""

    source_row: Mapped[int] = mapped_column(Integer)

    # --- The eight canonical CPSE attributes -----------------------------
    cpse_code: Mapped[str] = mapped_column(String(16), index=True)
    cpse_name: Mapped[str] = mapped_column(String(120))
    """"Company", as sent. cpse_code is its normalised form."""

    description_raw: Mapped[str] = mapped_column(Text)
    """"Item Description (Raw)". The single field every row must carry."""

    legacy_code: Mapped[str] = mapped_column(String(64), index=True)
    quantity: Mapped[float | None] = mapped_column(Float)

    category: Mapped[str] = mapped_column(
        String(32), default="UNCLASSIFIED", index=True, server_default="UNCLASSIFIED"
    )
    """The material family, derived from the description (logic/category.py).

    Not one of the eight attributes and not part of the vector - it is a
    blocking key and a filter. Indexed because both uses are lookups."""
    uom_raw: Mapped[str | None] = mapped_column(String(24))
    part_number_raw: Mapped[str | None] = mapped_column(String(80))
    manufacturer_raw: Mapped[str | None] = mapped_column(String(80))
    specifications_raw: Mapped[str | None] = mapped_column(Text)

    # --- Provenance ------------------------------------------------------
    batch_id: Mapped[str | None] = mapped_column(String(36), index=True)
    """The standardization batch that admitted this row, so any material can be
    traced back to the payload it arrived in and the check that let it in."""

    extraction_model: Mapped[str | None] = mapped_column(String(64))
    """Which Phase 1 produced it - the LoRA adapter name, or null for a row
    loaded from the seed corpus. A retrained adapter changes what a
    description means, and that has to be visible on the row."""

    # --- Plant & Facility Location ---------------------------------------
    plant_code: Mapped[str | None] = mapped_column(String(32), index=True)
    plant_name: Mapped[str | None] = mapped_column(String(120))
    storage_location: Mapped[str | None] = mapped_column(String(64))

    # --- Commercial & Valuation ------------------------------------------
    unit_price: Mapped[float | None] = mapped_column(Float)
    total_inventory_value: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(8), default="INR", server_default="INR")

    # --- Operational & Depletion Lifecycle -------------------------------
    po_number: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(32), default="AVAILABLE", server_default="AVAILABLE", index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    correction_comment: Mapped[str | None] = mapped_column(Text)

    # --- Flexible Enterprise Attributes (Unmapped ERP columns) -----------
    extra_attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # --- Vector index state ----------------------------------------------
    # Qdrant is derived state and gives no transactional consistency with
    # Postgres, so the gap is closed explicitly rather than hoped away.
    canonical_hash: Mapped[str | None] = mapped_column(String(40), index=True)
    embedding_version: Mapped[str | None] = mapped_column(String(32))
    indexed_at: Mapped[datetime | None] = mapped_column(index=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


class NationalIdCounter(Base):
    """The single row that hands out national ids.

    One row, `id = 1`, holding the next value to issue. Allocation is
    `UPDATE ... SET next_value = next_value + n RETURNING next_value` inside the
    admitting transaction, which is atomic on Postgres and SQLite alike and
    hands a batch a contiguous block in one statement.

    A rolled-back add leaves a gap in the sequence. That is correct: the ids
    were reserved and not used, and a gap is cheaper than the serialisation it
    would take to avoid one. Uniqueness matters; contiguity does not.
    """

    __tablename__ = "national_id_counter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    next_value: Mapped[int] = mapped_column(Integer, default=1)


class PlantLocation(Base):
    """A physical plant, refinery, power station, or warehouse facility operated by a CPSE."""

    __tablename__ = "plant_location"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    cpse_code: Mapped[str] = mapped_column(String(16), index=True)
    plant_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    plant_name: Mapped[str] = mapped_column(String(120))
    state_region: Mapped[str | None] = mapped_column(String(64))
    warehouse_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AuditLog(Base):
    """An append-only record of everything that changed the master.

    ai-service does not authenticate anyone - api-service owns that - so
    `actor` is a free-text label passed in by the caller. It is attribution,
    never authorisation.
    """

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(48), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
