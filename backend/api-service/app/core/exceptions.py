"""Centralized application exception definitions for api-service."""

from typing import Any


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class EntityNotFoundError(AppException):
    def __init__(self, entity: str, identifier: Any) -> None:
        super().__init__(
            message=f"{entity} with identifier '{identifier}' was not found.",
            code="NOT_FOUND",
            status_code=404,
            details={"entity": entity, "identifier": str(identifier)},
        )


class AIServiceError(AppException):
    """Base exception for AI microservice communication errors."""

    def __init__(
        self,
        message: str = "AI service communication error",
        code: str = "AI_SERVICE_ERROR",
        status_code: int = 502,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code, details=details)


class AIServiceUnavailableError(AIServiceError):
    def __init__(self, message: str = "AI service is currently unavailable or unreachable.") -> None:
        super().__init__(
            message=message,
            code="AI_SERVICE_UNAVAILABLE",
            status_code=503,
        )


class AIServiceTimeoutError(AIServiceError):
    def __init__(self, timeout: float) -> None:
        super().__init__(
            message=f"AI service request timed out after {timeout} seconds.",
            code="AI_SERVICE_TIMEOUT",
            status_code=504,
            details={"timeout_seconds": timeout},
        )


class DatabaseConnectionError(AppException):
    def __init__(self, message: str = "Database connection error.") -> None:
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=503,
        )

