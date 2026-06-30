"""Security-focused API tests (auth, uploads, rate limits)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.core.validators import validate_upload_file
from app.dependencies import get_chat_service_dep
from app.main import app
from app.models.conversation import ChatResponse, MessageResponse, MessageRole
from app.services.chat import ChatService
from tests.conftest import make_jwt


class TestJWTSecurity:
    def test_tampered_token_rejected(self, test_client: TestClient, auth_token: str):
        tampered = auth_token[:-1] + ("a" if auth_token[-1] != "a" else "b")
        response = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        assert response.status_code == 401

    def test_expired_token_rejected(
        self, test_client: TestClient, settings: Settings, user_id
    ):
        token = make_jwt(settings, user_id=str(user_id), expired=True)
        response = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
        assert "inválido" in response.json()["detail"].lower()

    def test_service_role_token_rejected_on_user_endpoints(
        self, test_client: TestClient, settings: Settings, user_id
    ):
        token = make_jwt(settings, user_id=str(user_id), role="service_role")
        for path in (
            "/api/v1/auth/me",
            "/api/v1/cases",
            f"/api/v1/documents/case/{uuid4()}/upload",
        ):
            if path.endswith("/upload"):
                response = test_client.post(
                    path,
                    headers={"Authorization": f"Bearer {token}"},
                    files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
                )
            elif path == "/api/v1/cases":
                response = test_client.get(
                    path,
                    headers={"Authorization": f"Bearer {token}"},
                )
            else:
                response = test_client.get(
                    path,
                    headers={"Authorization": f"Bearer {token}"},
                )
            assert response.status_code == 401, path


class TestUploadSecurity:
    def test_path_traversal_filename_rejected_unit(self, settings: Settings):
        for malicious in (
            "../../../etc/passwd.pdf",
            "..\\secret.docx",
            "/etc/passwd.pdf",
            "nested/../../escape.pdf",
        ):
            with pytest.raises(Exception, match="no válido"):
                validate_upload_file(
                    malicious,
                    b"%PDF-1.4",
                    "application/pdf",
                    max_size_bytes=settings.max_upload_size_bytes,
                )

    def test_path_traversal_filename_rejected_via_api(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        response = test_client.post(
            f"/api/v1/documents/case/{uuid4()}/upload",
            headers=auth_headers,
            files={"file": ("../../etc/passwd.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert response.status_code == 415
        assert "no válido" in response.json()["detail"].lower()

    def test_oversized_payload_rejected(
        self, test_client: TestClient, auth_headers: dict[str, str], settings: Settings
    ):
        oversized = b"x" * (settings.max_upload_size_bytes + 1)
        response = test_client.post(
            f"/api/v1/documents/case/{uuid4()}/upload",
            headers=auth_headers,
            files={"file": ("grande.pdf", oversized, "application/pdf")},
        )
        assert response.status_code == 413


class TestChatRateLimitHeaders:
    def test_rate_limit_headers_when_enabled(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
        get_settings.cache_clear()

        conversation_id = uuid4()
        now = datetime.now(UTC)
        mock_chat = MagicMock(spec=ChatService)
        mock_chat.chat = AsyncMock(
            return_value=ChatResponse(
                user_message=MessageResponse(
                    id=uuid4(),
                    conversation_id=conversation_id,
                    role=MessageRole.USER,
                    content="test",
                    metadata={},
                    created_at=now,
                ),
                assistant_message=MessageResponse(
                    id=uuid4(),
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content="respuesta",
                    metadata={},
                    created_at=now,
                ),
                citations=[],
            )
        )

        app.dependency_overrides[get_chat_service_dep] = lambda: mock_chat
        try:
            with patch("app.dependencies.get_chat_rate_limiter") as mock_limiter_factory:
                mock_limiter = MagicMock()
                from app.core.rate_limit import RateLimitInfo

                mock_limiter.check.return_value = RateLimitInfo(
                    limit=20, remaining=19, reset=9999999999
                )
                mock_limiter_factory.return_value = mock_limiter

                response = test_client.post(
                    f"/api/v1/conversations/{conversation_id}/messages",
                    headers=auth_headers,
                    json={"content": "¿Qué dice el contrato?"},
                )
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()

        assert response.status_code == 201
        assert response.headers.get("X-RateLimit-Limit") == "20"
        assert response.headers.get("X-RateLimit-Remaining") == "19"
        assert response.headers.get("X-RateLimit-Reset") == "9999999999"
