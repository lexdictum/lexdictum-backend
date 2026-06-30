from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.dependencies import get_chat_service_dep, get_conversation_service_dep
from app.main import app
from app.models.conversation import (
    ChatResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageListResponse,
    MessageResponse,
    MessageRole,
)
from app.services.chat import ChatService
from app.services.conversations import DEFAULT_CONVERSATION_TITLE, ConversationService
from app.services.llm import LLMService
from app.services.rag import RetrievedChunk


@pytest.fixture
def mock_conversation_service():
    return MagicMock(spec=ConversationService)


@pytest.fixture
def mock_chat_service():
    return MagicMock(spec=ChatService)


@pytest.fixture
def conversation_id():
    return uuid4()


@pytest.fixture
def case_id():
    return uuid4()


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def sample_conversation(conversation_id, case_id, user_id):
    now = datetime.now(UTC)
    return ConversationResponse(
        id=conversation_id,
        case_id=case_id,
        user_id=user_id,
        title=DEFAULT_CONVERSATION_TITLE,
        created_at=now,
        updated_at=now,
    )


class TestConversationService:
    def test_list_conversations(self, user_id, case_id):
        now = datetime.now(UTC)
        conv_id = uuid4()
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"id": str(case_id)}
        )
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "id": str(conv_id),
                    "case_id": str(case_id),
                    "user_id": str(user_id),
                    "title": "Consulta penal",
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            ],
            count=1,
        )

        service = ConversationService(mock_client)
        result = service.list_conversations(case_id, user_id)

        assert isinstance(result, ConversationListResponse)
        assert result.total == 1
        assert result.items[0].title == "Consulta penal"

    def test_get_conversation_not_found(self, user_id):
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=None
        )

        service = ConversationService(mock_client)
        with pytest.raises(NotFoundError, match="Conversación no encontrada"):
            service.get_conversation(uuid4(), user_id)

    def test_create_conversation_default_title(self, user_id, case_id):
        now = datetime.now(UTC)
        conv_id = uuid4()
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"id": str(case_id)}
        )
        mock_client.table.return_value.insert.return_value.select.return_value.single.return_value.execute.return_value = MagicMock(
            data={
                "id": str(conv_id),
                "case_id": str(case_id),
                "user_id": str(user_id),
                "title": DEFAULT_CONVERSATION_TITLE,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )

        from app.models.conversation import ConversationCreate

        service = ConversationService(mock_client)
        result = service.create_conversation(case_id, user_id, ConversationCreate())

        assert result.title == DEFAULT_CONVERSATION_TITLE


class TestConversationEndpoints:
    def test_list_conversations(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        mock_conversation_service,
        case_id,
        sample_conversation,
    ):
        mock_conversation_service.list_conversations.return_value = ConversationListResponse(
            items=[sample_conversation], total=1
        )

        app.dependency_overrides[get_conversation_service_dep] = (
            lambda: mock_conversation_service
        )
        try:
            response = test_client.get(
                f"/api/v1/cases/{case_id}/conversations",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == DEFAULT_CONVERSATION_TITLE

    def test_create_conversation(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        mock_conversation_service,
        case_id,
        sample_conversation,
    ):
        mock_conversation_service.create_conversation.return_value = sample_conversation

        app.dependency_overrides[get_conversation_service_dep] = (
            lambda: mock_conversation_service
        )
        try:
            response = test_client.post(
                f"/api/v1/cases/{case_id}/conversations",
                headers=auth_headers,
                json={"title": "Nueva consulta"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 201
        mock_conversation_service.create_conversation.assert_called_once()

    def test_delete_conversation(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        mock_conversation_service,
        conversation_id,
    ):
        app.dependency_overrides[get_conversation_service_dep] = (
            lambda: mock_conversation_service
        )
        try:
            response = test_client.delete(
                f"/api/v1/conversations/{conversation_id}",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 204
        mock_conversation_service.delete_conversation.assert_called_once()

    def test_list_messages(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        mock_conversation_service,
        conversation_id,
    ):
        now = datetime.now(UTC)
        mock_conversation_service.list_messages.return_value = MessageListResponse(
            items=[
                MessageResponse(
                    id=uuid4(),
                    conversation_id=conversation_id,
                    role=MessageRole.USER,
                    content="¿Cuál es el plazo?",
                    metadata={},
                    created_at=now,
                )
            ],
            total=1,
        )

        app.dependency_overrides[get_conversation_service_dep] = (
            lambda: mock_conversation_service
        )
        try:
            response = test_client.get(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_chat_without_llm_key_returns_503(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        conversation_id,
        settings: Settings,
    ):
        mock_chat = MagicMock(spec=ChatService)
        mock_chat.chat = AsyncMock(
            side_effect=ServiceUnavailableError(
                "El servicio de IA no está configurado. "
                "Configure LLM_API_KEY para habilitar el asistente jurídico."
            )
        )

        app.dependency_overrides[get_chat_service_dep] = lambda: mock_chat
        try:
            response = test_client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json={"content": "¿Qué dice el contrato?"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert "LLM_API_KEY" in response.json()["detail"]

    def test_chat_success(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        conversation_id,
    ):
        now = datetime.now(UTC)
        user_msg_id = uuid4()
        assistant_msg_id = uuid4()
        doc_id = uuid4()

        mock_chat = MagicMock(spec=ChatService)
        mock_chat.chat = AsyncMock(
            return_value=ChatResponse(
                user_message=MessageResponse(
                    id=user_msg_id,
                    conversation_id=conversation_id,
                    role=MessageRole.USER,
                    content="¿Qué dice el contrato?",
                    metadata={},
                    created_at=now,
                ),
                assistant_message=MessageResponse(
                    id=assistant_msg_id,
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content="El contrato establece un plazo de 30 días.",
                    metadata={
                        "citations": [
                            {
                                "document_id": str(doc_id),
                                "filename": "contrato.pdf",
                                "page": 2,
                                "chunk_index": 0,
                                "text_snippet": "plazo de treinta días",
                            }
                        ]
                    },
                    created_at=now,
                ),
                citations=[],
            )
        )

        app.dependency_overrides[get_chat_service_dep] = lambda: mock_chat
        try:
            response = test_client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers=auth_headers,
                json={"content": "¿Qué dice el contrato?"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 201
        body = response.json()
        assert body["assistant_message"]["role"] == "assistant"

    def test_stream_endpoint_structure(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        conversation_id,
    ):
        async def fake_stream(*_args, **_kwargs):
            yield "event: token\ndata: {\"content\": \"Hola\"}\n\n"
            yield "event: done\ndata: {\"assistant_message_id\": \"abc\"}\n\n"

        mock_chat = MagicMock(spec=ChatService)
        mock_chat.chat_stream = fake_stream

        app.dependency_overrides[get_chat_service_dep] = lambda: mock_chat
        try:
            response = test_client.post(
                f"/api/v1/conversations/{conversation_id}/messages/stream",
                headers=auth_headers,
                json={"content": "Pregunta de prueba"},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: token" in response.text
        assert "event: done" in response.text

    def test_endpoints_require_auth(self, test_client: TestClient, case_id):
        conversation_id = uuid4()
        assert (
            test_client.get(f"/api/v1/cases/{case_id}/conversations").status_code
            == 401
        )
        assert (
            test_client.get(f"/api/v1/conversations/{conversation_id}/messages").status_code
            == 401
        )


class TestLLMService:
    def test_parse_citations_strips_block(self):
        service = LLMService()
        doc_id = uuid4()
        content = (
            "Respuesta jurídica basada en el documento.\n"
            f'<!--CITATIONS:[{{"document_id":"{doc_id}",'
            '"page":1,"chunk_index":0,"text_snippet":"fragmento"}]-->'
        )
        clean, citations = service.parse_citations(content)
        assert "CITATIONS" not in clean
        assert len(citations) == 1
        assert citations[0].document_id == doc_id
        assert citations[0].page == 1

    def test_ensure_configured_raises_without_key(self, settings: Settings):
        service = LLMService(settings.model_copy(update={"llm_api_key": None}))
        with pytest.raises(ServiceUnavailableError, match="LLM_API_KEY"):
            service.ensure_configured()

    def test_build_messages_includes_context(self):
        service = LLMService()
        doc_id = str(uuid4())
        chunks = [
            RetrievedChunk(
                document_id=doc_id,
                filename="escrito.pdf",
                chunk_index=0,
                text="Texto del escrito",
                page=3,
                score=0.9,
            )
        ]
        messages = service.build_messages(
            "Eres un asistente jurídico.",
            [],
            "¿Qué dice el escrito?",
            chunks,
        )
        assert messages[0]["role"] == "system"
        assert "escrito.pdf" in messages[1]["content"]
        assert messages[-1]["content"] == "¿Qué dice el escrito?"
