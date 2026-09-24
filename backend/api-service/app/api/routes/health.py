import time
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.schemas.common import (
    HealthResponse,
    ServicesHealthResponse,
    ServiceDependencyStatus,
)
from app.services.ai_client import ai_client

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_liveness() -> HealthResponse:
    """Basic liveness health check."""
    return HealthResponse(
        status="ok",
        service="api-service",
        version="0.1.0",
        environment=settings.environment,
    )


@router.get("/health/services", response_model=ServicesHealthResponse)
async def health_services() -> ServicesHealthResponse:
    """Deep readiness health check probing database and AI service."""
    dependencies: dict[str, ServiceDependencyStatus] = {}
    overall_status = "healthy"

    # 1. Probe Database Connectivity
    db_start = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_latency = (time.perf_counter() - db_start) * 1000
            dependencies["database"] = ServiceDependencyStatus(
                status="healthy",
                latency_ms=round(db_latency, 2),
            )
    except Exception as exc:
        db_latency = (time.perf_counter() - db_start) * 1000
        dependencies["database"] = ServiceDependencyStatus(
            status="unavailable",
            latency_ms=round(db_latency, 2),
            message=f"Database unreachable: {str(exc)}",
        )
        overall_status = "degraded"

    # 2. Probe AI Microservice Connectivity
    ai_health = await ai_client.check_health()
    dependencies["ai_service"] = ServiceDependencyStatus(
        status=ai_health["status"],
        latency_ms=ai_health.get("latency_ms"),
        message=ai_health.get("message"),
    )
    if ai_health["status"] != "healthy":
        overall_status = "degraded"

    return ServicesHealthResponse(
        status=overall_status,
        service="api-service",
        version="0.1.0",
        environment=settings.environment,
        dependencies=dependencies,
    )
