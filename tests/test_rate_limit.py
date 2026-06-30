from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import RateLimitExceededError
from app.dependencies import enforce_chat_rate_limit, get_chat_service_dep
from app.main import app
from app.models.conversation import ChatResponse, MessageResponse, MessageRole
from app.services.chat import ChatService


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestRateLimit:
    def test_rate_limit_returns_429(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ):
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

        def raise_rate_limit() -> None:
            raise RateLimitExceededError(retry_after=42)

        app.dependency_overrides[get_chat_service_dep] = lambda: mock_chat
        app.dependency_overrides[enforce_chat_rate_limit] = raise_rate_limit
        try:
            response = client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json={"content": "¿Qué dice el contrato?"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 429
        assert "límite de mensajes" in response.json()["detail"].lower()
        assert response.headers.get("Retry-After") == "42"

    def test_rate_limit_disabled_allows_requests(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ):
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
            with patch("app.dependencies.get_chat_rate_limiter") as mock_limiter:
                response = client.post(
                    f"/api/v1/conversations/{conversation_id}/messages",
                    headers=auth_headers,
                    json={"content": "Pregunta"},
                )
                mock_limiter.assert_not_called()
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 201

    def test_chat_rate_limiter_increments(self):
        from app.core.rate_limit import ChatRateLimiter

        class FakeRedis:
            def __init__(self):
                self.values: dict[str, int] = {}

            def pipeline(self):
                return self

            def incr(self, key: str):
                self._key = key
                return self

            def expire(self, _key: str, _seconds: int):
                return self

            def execute(self):
                count = self.values.get(self._key, 0) + 1
                self.values[self._key] = count
                return count, True

        fake = FakeRedis()
        limiter = ChatRateLimiter.__new__(ChatRateLimiter)
        limiter._redis = fake
        limiter.limit = 2
        limiter.window = 60

        limiter.check("user-1")
        limiter.check("user-1")
        with pytest.raises(RateLimitExceededError):
            limiter.check("user-1")
