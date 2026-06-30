from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealthReady:
    def test_readiness_all_ok(self, client: TestClient):
        with (
            patch(
                "app.api.v1.health.check_redis",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.health.check_qdrant",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.health.check_supabase",
                new=AsyncMock(return_value={"status": "skipped"}),
            ),
        ):
            response = client.get("/api/v1/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["checks"]["redis"]["status"] == "ok"
        assert data["checks"]["qdrant"]["status"] == "ok"

    def test_readiness_critical_failure_dev_returns_200(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("APP_ENV", "development")
        get_settings.cache_clear()

        with (
            patch(
                "app.api.v1.health.check_redis",
                return_value={"status": "error", "message": "connection refused"},
            ),
            patch(
                "app.api.v1.health.check_qdrant",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.health.check_supabase",
                new=AsyncMock(return_value={"status": "skipped"}),
            ),
        ):
            response = client.get("/api/v1/health/ready")

        get_settings.cache_clear()
        assert response.status_code == 200
        assert response.json()["status"] == "error"
        assert response.json()["checks"]["redis"]["status"] == "error"

    def test_readiness_critical_failure_prod_returns_503(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("APP_ENV", "production")
        get_settings.cache_clear()

        with (
            patch(
                "app.api.v1.health.check_redis",
                return_value={"status": "ok"},
            ),
            patch(
                "app.api.v1.health.check_qdrant",
                return_value={"status": "error", "message": "unreachable"},
            ),
            patch(
                "app.api.v1.health.check_supabase",
                new=AsyncMock(return_value={"status": "error", "message": "timeout"}),
            ),
        ):
            response = client.get("/api/v1/health/ready")

        get_settings.cache_clear()
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "error"
        assert body["checks"]["qdrant"]["status"] == "error"
        assert body["checks"]["supabase"]["status"] == "error"

    def test_liveness_always_ok(self, client: TestClient):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_request_id_header(self, client: TestClient):
        response = client.get("/api/v1/health")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

        custom_id = "test-request-id-12345"
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": custom_id},
        )
        assert response.headers["X-Request-ID"] == custom_id
