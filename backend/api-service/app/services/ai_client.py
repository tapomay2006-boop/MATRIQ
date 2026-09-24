import time
from typing import Any
import httpx

from app.core.config import settings
from app.core.exceptions import (
    AIServiceError,
    AIServiceTimeoutError,
    AIServiceUnavailableError,
)


class AIServiceClient:
    """HTTP client adapter for communicating with the AI microservice."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.ai_service_url).rstrip("/")
        self.timeout = timeout or settings.ai_service_timeout

    async def check_health(self) -> dict[str, Any]:
        """Check AI service connectivity and return response with measured latency."""
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.get("/health")
                latency_ms = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "status": "healthy",
                        "latency_ms": round(latency_ms, 2),
                        "data": data,
                    }
                return {
                    "status": "degraded",
                    "latency_ms": round(latency_ms, 2),
                    "message": f"Non-200 response: {response.status_code}",
                }
        except httpx.TimeoutException:
            return {
                "status": "unavailable",
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "message": f"Connection timed out after {self.timeout}s",
            }
        except httpx.RequestError as exc:
            return {
                "status": "unavailable",
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "message": f"Connection failed: {str(exc)}",
            }

    async def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Dispatch inference request to AI service with error translation."""
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.post("/api/v1/inference/predict", json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            raise AIServiceTimeoutError(timeout=self.timeout)
        except httpx.ConnectError:
            raise AIServiceUnavailableError()
        except httpx.HTTPStatusError as exc:
            raise AIServiceError(
                message=f"AI service returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
                details={"response_text": exc.response.text},
            )
        except httpx.RequestError as exc:
            raise AIServiceError(message=f"AI service network error: {str(exc)}")


ai_client = AIServiceClient()
