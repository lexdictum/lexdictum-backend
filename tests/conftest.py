import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.config import Settings, get_settings
from app.main import app

SUPABASE_LOCAL_DEFAULTS = {
    "supabase_url": "http://127.0.0.1:54321",
    "supabase_anon_key": (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9."
        "CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
    ),
    "supabase_service_role_key": (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0."
        "EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
    ),
    "supabase_jwt_secret": (
        "super-secret-jwt-token-with-at-least-32-characters-long"
    ),
}


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that need Supabase local or external services",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(
        reason="Pass --run-integration to execute integration tests"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def disable_rate_limit_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


def make_jwt(
    settings: Settings,
    *,
    user_id: str | None = None,
    email: str = "lawyer@example.com",
    role: str = "authenticated",
    expired: bool = False,
    missing_sub: bool = False,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "aud": "authenticated",
        "exp": now + (timedelta(hours=-1) if expired else timedelta(hours=1)),
        "iat": now,
        "role": role,
        "email": email,
    }
    if not missing_sub:
        payload["sub"] = user_id or str(uuid4())
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


@pytest.fixture
def user_id() -> UUID:
    return uuid4()


@pytest.fixture
def auth_token(settings: Settings, user_id: UUID) -> str:
    return make_jwt(settings, user_id=str(user_id))


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def supabase_local_available() -> bool:
    return os.getenv("SUPABASE_LOCAL", "").lower() in ("1", "true", "yes")


@pytest.fixture
def run_integration(request) -> bool:
    return request.config.getoption("--run-integration")


@pytest.fixture
def supabase_integration_settings(
    settings: Settings, supabase_local_available: bool
) -> Settings:
    if not supabase_local_available:
        return settings

    overrides = {
        key: os.getenv(env_name, default)
        for key, env_name, default in (
            ("supabase_url", "SUPABASE_URL", SUPABASE_LOCAL_DEFAULTS["supabase_url"]),
            (
                "supabase_anon_key",
                "SUPABASE_ANON_KEY",
                SUPABASE_LOCAL_DEFAULTS["supabase_anon_key"],
            ),
            (
                "supabase_service_role_key",
                "SUPABASE_SERVICE_ROLE_KEY",
                SUPABASE_LOCAL_DEFAULTS["supabase_service_role_key"],
            ),
            (
                "supabase_jwt_secret",
                "SUPABASE_JWT_SECRET",
                SUPABASE_LOCAL_DEFAULTS["supabase_jwt_secret"],
            ),
        )
    }
    return settings.model_copy(update=overrides)


@pytest.fixture
def qdrant_available() -> bool:
    return os.getenv("QDRANT_INTEGRATION", "").lower() in ("1", "true", "yes")

