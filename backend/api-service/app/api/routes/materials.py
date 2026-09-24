"""API endpoints for Material Ingestion and Master Catalog browsing."""

import math
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import and_, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.material import Material
from app.schemas.material import (
    MaterialIngestionResponse,
    MaterialListResponse,
    MaterialQualityStats,
    MaterialResponse,
)
from app.services.material_ingestion import (
    MaterialIngestionError,
    MaterialIngestionService,
)

router = APIRouter(prefix="/materials", tags=["materials"])


class BatchMaterialIngestRequest(BaseModel):
    items: list[dict[str, Any]]
    default_organization: str | None = None



@router.post(
    "/ingest",
    response_model=MaterialIngestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest batch material dataset",
    description="Upload CSV or JSON material dataset from CPSEs with automatic schema normalization, deduplication, and PostgreSQL persistence.",
)
async def ingest_materials(
    file: Annotated[UploadFile, File(description="CSV or JSON dataset file")],
    default_organization: Annotated[
        str | None,
        Form(description="Optional fallback CPSE organization name if missing from file columns"),
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> MaterialIngestionResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a valid filename.",
        )

    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".csv") or filename_lower.endswith(".json")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file.filename}'. Please upload a .csv or .json file.",
        )

    try:
        content = await file.read()
        if not content or len(content.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        result = await MaterialIngestionService.ingest_batch(
            db=db,
            filename=file.filename,
            file_content=content,
            default_organization=default_organization,
        )
        return result
    except MaterialIngestionError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing file ingestion: {str(e)}",
        )


@router.post(
    "/ingest/batch",
    response_model=MaterialIngestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Direct JSON batch material ingestion",
    description="Ingest standardized material items directly from frontend review or automated extraction pipelines.",
)
async def ingest_materials_batch(
    payload: BatchMaterialIngestRequest,
    db: AsyncSession = Depends(get_db),
) -> MaterialIngestionResponse:
    try:
        return await MaterialIngestionService.ingest_direct_rows(
            db=db,
            rows=payload.items,
            filename="frontend_batch_submission",
            default_organization=payload.default_organization,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing batch ingestion: {str(e)}",
        )


@router.get(
    "",
    response_model=MaterialListResponse,
    status_code=status.HTTP_200_OK,
    summary="List master catalog materials",
    description="Retrieve paginated material master items with optional CPSE organization filtering and keyword search.",
)
async def list_materials(
    page: int | None = Query(default=None, ge=1, description="Page number (1-indexed)"),
    page_size: int | None = Query(default=None, ge=1, le=100, description="Items per page"),
    limit: int | None = Query(default=None, ge=1, le=200, description="Legacy limit override"),
    offset: int | None = Query(default=None, ge=0, description="Legacy offset override"),
    organization: str | None = Query(default=None, description="Filter by CPSE organization"),
    national_id: str | None = Query(default=None, description="Filter by exact or prefix national_id"),
    status: str | None = Query(default=None, description="Filter by material status (e.g. ASSIGNED, PENDING_REVIEW)"),
    search: str | None = Query(default=None, description="Search term across description, codes, and attributes"),
    db: AsyncSession = Depends(get_db),
) -> MaterialListResponse:
    # Resolve pagination parameters preserving both page/page_size and limit/offset conventions
    if page is not None or page_size is not None:
        effective_page_size = page_size or 20
        effective_page = page or 1
        effective_offset = (effective_page - 1) * effective_page_size
        effective_limit = effective_page_size
    elif limit is not None or offset is not None:
        effective_limit = limit or 20
        effective_offset = offset or 0
        effective_page_size = effective_limit
        effective_page = (effective_offset // effective_page_size) + 1
    else:
        effective_page = 1
        effective_page_size = 20
        effective_offset = 0
        effective_limit = 20

    stmt = select(Material)
    count_stmt = select(func.count(Material.id))

    if national_id and national_id.strip():
        nid = national_id.strip()
        if nid.upper() == "UNASSIGNED" or nid.upper() == "NULL":
            stmt = stmt.where(or_(Material.national_id.is_(None), Material.national_id == ""))
            count_stmt = count_stmt.where(or_(Material.national_id.is_(None), Material.national_id == ""))
        else:
            stmt = stmt.where(func.lower(Material.national_id) == nid.lower())
            count_stmt = count_stmt.where(func.lower(Material.national_id) == nid.lower())

    if status and status.strip():
        stmt = stmt.where(func.lower(Material.status) == status.strip().lower())
        count_stmt = count_stmt.where(func.lower(Material.status) == status.strip().lower())

    if organization and organization.strip():
        org_val = organization.strip().lower()
        if org_val == "ccl":
            org_filter = or_(
                func.lower(Material.organization) == "ccl",
                func.lower(Material.organization).like("%central coalfields%"),
                func.lower(Material.organization).like("%coal india%"),
            )
            stmt = stmt.where(org_filter)
            count_stmt = count_stmt.where(org_filter)
        else:
            stmt = stmt.where(func.lower(Material.organization) == org_val)
            count_stmt = count_stmt.where(func.lower(Material.organization) == org_val)

    if search and search.strip():
        search_term = f"%{search.strip().lower()}%"
        search_filter = or_(
            func.lower(Material.legacy_code).like(search_term),
            func.lower(Material.description).like(search_term),
            func.lower(Material.item_name).like(search_term),
            func.lower(Material.part_number).like(search_term),
            func.lower(Material.manufacturer).like(search_term),
            func.lower(Material.category).like(search_term),
            func.lower(Material.material_type).like(search_term),
            func.lower(Material.national_id).like(search_term),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    total_count = await db.scalar(count_stmt) or 0
    total_pages = max(1, math.ceil(total_count / effective_page_size)) if total_count > 0 else 1

    # Deterministic ordering by created_at DESC and id DESC
    stmt = (
        stmt.order_by(Material.created_at.desc(), Material.id.desc())
        .offset(effective_offset)
        .limit(effective_limit)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    return MaterialListResponse(
        items=[MaterialResponse.model_validate(item) for item in items],
        total=total_count,
        page=effective_page,
        page_size=effective_page_size,
        total_pages=total_pages,
        limit=effective_limit,
        offset=effective_offset,
    )


@router.get(
    "/organizations",
    response_model=list[str],
    status_code=status.HTTP_200_OK,
    summary="List distinct CPSE organizations",
    description="Retrieve all unique CPSE organization names currently represented in the master catalog.",
)
async def list_organizations(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    stmt = (
        select(distinct(Material.organization))
        .where(Material.organization.is_not(None))
        .where(func.trim(Material.organization) != "")
        .order_by(Material.organization.asc())
    )
    result = await db.execute(stmt)
    orgs = [str(r).strip() for r in result.scalars().all() if r and str(r).strip()]
    return orgs


@router.get(
    "/quality",
    response_model=MaterialQualityStats,
    status_code=status.HTTP_200_OK,
    summary="Get catalog data quality statistics",
    description="Deterministic calculation of completeness metrics across all material master records.",
)
async def get_catalog_quality(
    db: AsyncSession = Depends(get_db),
) -> MaterialQualityStats:
    stmt = select(
        func.count(Material.id).label("total_materials"),
        func.count(distinct(Material.organization)).label("organizations"),
        func.sum(case((or_(Material.uom.is_(None), func.trim(Material.uom) == ""), 1), else_=0)).label("missing_uom"),
        func.sum(case((or_(Material.manufacturer.is_(None), func.trim(Material.manufacturer) == ""), 1), else_=0)).label("missing_manufacturer"),
        func.sum(case((or_(Material.part_number.is_(None), func.trim(Material.part_number) == ""), 1), else_=0)).label("missing_part_number"),
        func.sum(case((or_(Material.category.is_(None), func.trim(Material.category) == ""), 1), else_=0)).label("missing_category"),
        func.sum(case((and_(Material.national_id.is_not(None), func.trim(Material.national_id) != ""), 1), else_=0)).label("assigned_count"),
        func.sum(case((or_(Material.national_id.is_(None), func.trim(Material.national_id) == ""), 1), else_=0)).label("unassigned_count"),
    )
    result = await db.execute(stmt)
    row = result.one_or_none()

    if not row or row[0] is None:
        return MaterialQualityStats(
            total_materials=0,
            organizations=0,
            missing_uom=0,
            missing_manufacturer=0,
            missing_part_number=0,
            missing_category=0,
            assigned_count=0,
            unassigned_count=0,
        )

    return MaterialQualityStats(
        total_materials=int(row[0] or 0),
        organizations=int(row[1] or 0),
        missing_uom=int(row[2] or 0),
        missing_manufacturer=int(row[3] or 0),
        missing_part_number=int(row[4] or 0),
        missing_category=int(row[5] or 0),
        assigned_count=int(row[6] or 0),
        unassigned_count=int(row[7] or 0),
    )


@router.get(
    "/{material_id}",
    response_model=MaterialResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single material details",
)
async def get_material(
    material_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MaterialResponse:
    stmt = select(Material).where(Material.id == material_id)
    result = await db.execute(stmt)
    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID '{material_id}' not found.",
        )

    return MaterialResponse.model_validate(material)


class MaterialUpdateRequest(BaseModel):
    description: str | None = None
    item_name: str | None = None
    part_number: str | None = None
    manufacturer: str | None = None
    uom: str | None = None
    category: str | None = None
    specification: str | None = None
    equipment_compatibility: str | None = None
    material_type: str | None = None


@router.put(
    "/{material_id}",
    response_model=MaterialResponse,
    status_code=status.HTTP_200_OK,
    summary="Update material record",
    description="Update canonical fields of a single material record in the master catalog.",
)
async def update_material(
    material_id: uuid.UUID,
    payload: MaterialUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> MaterialResponse:
    from datetime import datetime

    stmt = select(Material).where(Material.id == material_id)
    result = await db.execute(stmt)
    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID '{material_id}' not found.",
        )

    update_dict = payload.model_dump(exclude_unset=True)
    for field_name, val in update_dict.items():
        if hasattr(material, field_name) and val is not None:
            setattr(material, field_name, str(val).strip())

    material.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(material)

    return MaterialResponse.model_validate(material)
