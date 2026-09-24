import csv
import io
import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.schemas.material import IngestionErrorItem, MaterialIngestionResponse


class MaterialIngestionError(Exception):
    """Domain error raised during material batch ingestion."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class MaterialIngestionService:
    """Service for parsing, validating, and ingesting material master datasets."""

    @classmethod
    async def ingest_batch(
        cls,
        db: AsyncSession,
        filename: str,
        file_content: bytes,
        default_organization: str | None = None,
    ) -> MaterialIngestionResponse:
        ingestion_id = str(uuid.uuid4())
        filename_lower = filename.lower()

        # 1. Parse content into raw row dictionaries
        rows: list[dict[str, Any]] = []
        try:
            if filename_lower.endswith(".csv"):
                text_content = file_content.decode("utf-8-sig", errors="replace")
                reader = csv.DictReader(io.StringIO(text_content))
                rows = [row for row in reader]
            elif filename_lower.endswith(".json"):
                data = json.loads(file_content.decode("utf-8", errors="replace"))
                if isinstance(data, list):
                    rows = data
                elif isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
                    rows = data["items"]
                else:
                    raise MaterialIngestionError("JSON file must be an array of objects or contain an 'items' array.")
            else:
                raise MaterialIngestionError(f"Unsupported file format for '{filename}'.", status_code=400)
        except Exception as exc:
            if isinstance(exc, MaterialIngestionError):
                raise
            raise MaterialIngestionError(f"Failed to parse file: {str(exc)}", status_code=400)

        # Parse file into rows, then delegate to ingest_direct_rows
        return await cls.ingest_direct_rows(
            db=db,
            rows=rows,
            filename=filename,
            default_organization=default_organization,
            ingestion_id=ingestion_id,
        )

    @classmethod
    async def ingest_direct_rows(
        cls,
        db: AsyncSession,
        rows: list[dict[str, Any]],
        filename: str = "direct_batch",
        default_organization: str | None = None,
        ingestion_id: str | None = None,
    ) -> MaterialIngestionResponse:
        ingestion_id = ingestion_id or str(uuid.uuid4())
        total_records = len(rows)
        accepted_records = 0
        rejected_records = 0
        duplicate_records = 0
        errors: list[IngestionErrorItem] = []

        # Process each row
        for idx, row in enumerate(rows, start=1):
            # Resolve headers with multi-source fallback
            org = (
                row.get("organization")
                or row.get("Organization")
                or row.get("company")
                or row.get("Company")
                or default_organization
            )
            legacy_code = (
                row.get("legacy_code")
                or row.get("Legacy Code")
                or row.get("Item Code / Legacy Ref")
                or row.get("item_code")
                or row.get("code")
            )
            desc = (
                row.get("description")
                or row.get("Description")
                or row.get("Item Description (Raw)")
                or row.get("item_description")
                or row.get("description_raw")
            )

            # Validate mandatory fields
            if not org or not str(org).strip():
                rejected_records += 1
                errors.append(
                    IngestionErrorItem(
                        row=idx,
                        legacy_code=str(legacy_code).strip() if legacy_code else None,
                        reason="Missing mandatory organization/company.",
                    )
                )
                continue

            if not legacy_code or not str(legacy_code).strip():
                rejected_records += 1
                errors.append(
                    IngestionErrorItem(
                        row=idx,
                        legacy_code=None,
                        reason="Missing mandatory legacy code / item code.",
                    )
                )
                continue

            if not desc or not str(desc).strip():
                rejected_records += 1
                errors.append(
                    IngestionErrorItem(
                        row=idx,
                        legacy_code=str(legacy_code).strip(),
                        reason="Missing mandatory description.",
                    )
                )
                continue

            clean_org = str(org).strip()
            org_lower = clean_org.lower()
            if "coal india" in org_lower or "central coalfields" in org_lower:
                clean_org = "CCL"
            clean_code = str(legacy_code).strip()
            clean_desc = str(desc).strip()

            uom = row.get("uom") or row.get("UOM")
            item_name = row.get("item_name") or row.get("Item Name")
            part_no = (
                row.get("part_number")
                or row.get("Part Number / OEM Number")
                or row.get("part_no")
                or row.get("part_number_raw")
            )
            mfg = (
                row.get("manufacturer")
                or row.get("Make / Brand")
                or row.get("make")
                or row.get("manufacturer_raw")
            )
            equip_compat = row.get("equipment_compatibility") or row.get("Equipment Compatibility")
            mat_type = row.get("material_type") or row.get("Material Type")
            category = row.get("category") or row.get("Category")
            specs = (
                row.get("specification")
                or row.get("specifications")
                or row.get("Specifications / Dimensions")
                or row.get("specifications_raw")
            )

            def _clean(val: Any) -> str | None:
                if val is None:
                    return None
                s = str(val).strip()
                return s if s and s.upper() != "NA" else None

            # Check if record already exists in database
            stmt = select(Material).where(
                func.lower(Material.organization) == clean_org.lower(),
                func.lower(Material.legacy_code) == clean_code.lower(),
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()

            if existing:
                duplicate_records += 1
                existing.description = clean_desc
                existing.uom = _clean(uom)
                existing.item_name = _clean(item_name)
                existing.part_number = _clean(part_no)
                existing.manufacturer = _clean(mfg)
                existing.equipment_compatibility = _clean(equip_compat)
                existing.material_type = _clean(mat_type)
                existing.category = _clean(category)
                existing.specification = _clean(specs)
                existing.source_file = filename
                existing.source_row = idx
                accepted_records += 1
            else:
                new_material = Material(
                    organization=clean_org,
                    legacy_code=clean_code,
                    description=clean_desc,
                    uom=_clean(uom),
                    item_name=_clean(item_name),
                    part_number=_clean(part_no),
                    manufacturer=_clean(mfg),
                    equipment_compatibility=_clean(equip_compat),
                    material_type=_clean(mat_type),
                    category=_clean(category),
                    specification=_clean(specs),
                    source_file=filename,
                    source_row=idx,
                )
                db.add(new_material)
                accepted_records += 1

        await db.commit()

        return MaterialIngestionResponse(
            ingestion_id=ingestion_id,
            filename=filename,
            total_records=total_records,
            accepted_records=accepted_records,
            rejected_records=rejected_records,
            duplicate_records=duplicate_records,
            errors=errors,
        )
