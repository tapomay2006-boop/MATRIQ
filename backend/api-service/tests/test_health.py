import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_root_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "api-service"


@pytest.mark.asyncio
async def test_api_v1_health(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "api-service"


@pytest.mark.asyncio
async def test_health_services_graceful_fallback(client):
    """Verify /api/v1/health/services handles offline dependencies gracefully without crashing."""
    response = await client.get("/api/v1/health/services")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "dependencies" in body
    assert "ai_service" in body["dependencies"]
    assert "database" in body["dependencies"]


@pytest.mark.asyncio
async def test_health_services_healthy_mock(client):
    """Verify /api/v1/health/services returns healthy status when dependencies respond."""
    with patch("app.services.ai_client.ai_client.check_health", new_callable=AsyncMock) as mock_ai:
        mock_ai.return_value = {"status": "healthy", "latency_ms": 1.5, "data": {"status": "ok"}}
        response = await client.get("/api/v1/health/services")
        assert response.status_code == 200
        body = response.json()
        assert body["dependencies"]["ai_service"]["status"] == "healthy"
