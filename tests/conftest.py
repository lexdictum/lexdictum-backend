import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.config import Settings, get_settings
from app.main import app


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


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that need Supabase local",
    )


@pytest.fixture
def run_integration(request) -> bool:
    return request.config.getoption("--run-integration")
