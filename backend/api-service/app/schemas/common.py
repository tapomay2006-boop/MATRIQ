from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard success response wrapper."""

    success: bool = True
    data: T | None = None
    message: str | None = None


class ApiErrorDetail(BaseModel):
    """Structured error payload details."""

    code: str = "ERROR"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(BaseModel):
    """Standard error response wrapper."""

    success: bool = False
    error: ApiErrorDetail


class HealthResponse(BaseModel):
    """Liveness health check response model."""

    status: str = "ok"
    service: str = "api-service"
    version: str = "0.1.0"
    environment: str = "development"


class ServiceDependencyStatus(BaseModel):
    """Status of an individual dependency subsystem."""

    status: str  # "healthy", "degraded", "unavailable"
    latency_ms: float | None = None
    message: str | None = None


class ServicesHealthResponse(BaseModel):
    """Deep readiness and service dependencies status response model."""

    status: str  # "healthy", "degraded", "unhealthy"
    service: str = "api-service"
    version: str = "0.1.0"
    environment: str = "development"
    dependencies: dict[str, ServiceDependencyStatus]
