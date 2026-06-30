from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from jose import jwt

from app.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_supabase_jwt


def test_decode_valid_jwt():
    settings = get_settings()
    user_id = str(uuid4())
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": user_id,
            "email": "abogado@lexdictum.es",
            "role": "authenticated",
            "aud": "authenticated",
            "exp": now + timedelta(hours=1),
            "iat": now,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )

    result = decode_supabase_jwt(token, settings)

    assert result["id"] == user_id
    assert result["email"] == "abogado@lexdictum.es"
    assert result["role"] == "authenticated"
    assert result["claims"]["sub"] == user_id


def test_decode_expired_jwt():
    settings = get_settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": "authenticated",
            "aud": "authenticated",
            "exp": now - timedelta(minutes=5),
            "iat": now - timedelta(hours=1),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError, match="Token inválido o expirado"):
        decode_supabase_jwt(token, settings)


def test_decode_jwt_missing_sub():
    settings = get_settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "role": "authenticated",
            "aud": "authenticated",
            "exp": now + timedelta(hours=1),
            "iat": now,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError, match="Token sin identificador de usuario"):
        decode_supabase_jwt(token, settings)


def test_decode_jwt_invalid_role():
    settings = get_settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": "service_role",
            "aud": "authenticated",
            "exp": now + timedelta(hours=1),
            "iat": now,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError, match="Token con rol no permitido"):
        decode_supabase_jwt(token, settings)


def test_decode_jwt_wrong_secret():
    settings = get_settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "role": "authenticated",
            "aud": "authenticated",
            "exp": now + timedelta(hours=1),
            "iat": now,
        },
        "wrong-secret-key-that-is-long-enough",
        algorithm="HS256",
    )

    with pytest.raises(UnauthorizedError, match="Token inválido o expirado"):
        decode_supabase_jwt(token, settings)


def test_protected_route_requires_auth(test_client):
    response = test_client.get("/api/v1/auth/me")
    assert response.status_code == 401
