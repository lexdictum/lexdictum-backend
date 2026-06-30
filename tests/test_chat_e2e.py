"""End-to-end chat flow tests (mocked LLM; optional real Qdrant)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.config import Settings
from app.models.conversation import (
    ConversationResponse,
    MessageResponse,
    MessageRole,
)
from app.services.chat import ChatService
from app.services.conversations import DEFAULT_CONVERSATION_TITLE
from app.services.llm import LLMService
from app.services.rag import RAGService, RetrievedChunk


@pytest.fixture
def conversation_context(user_id):
    conversation_id = uuid4()
    case_id = uuid4()
    now = datetime.now(UTC)
    conversation = ConversationResponse(
        id=conversation_id,
        case_id=case_id,
        user_id=user_id,
        title=DEFAULT_CONVERSATION_TITLE,
        created_at=now,
        updated_at=now,
    )
    return conversation_id, case_id, user_id, conversation, now


class TestChatFlowE2E:
    """ChatService orchestration with mocked LLM and RAG."""

    @pytest.mark.asyncio
    async def test_full_chat_flow_persists_messages_and_citations(
        self, settings: Settings, conversation_context
    ):
        conversation_id, case_id, user_id, conversation, now = conversation_context
        doc_id = uuid4()
        user_msg_id = uuid4()
        assistant_msg_id = uuid4()

        mock_conversations = MagicMock()
        mock_conversations.get_conversation.return_value = conversation
        mock_conversations.get_recent_messages.return_value = []
        mock_conversations.save_message.side_effect = [
            MessageResponse(
                id=user_msg_id,
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content="¿Cuál es el plazo contractual?",
                metadata={},
                created_at=now,
            ),
            MessageResponse(
                id=assistant_msg_id,
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content="El plazo es de 30 días naturales.",
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
        ]

        mock_rag = MagicMock(spec=RAGService)
        mock_rag.retrieve_context.return_value = [
            RetrievedChunk(
                document_id=str(doc_id),
                filename="contrato.pdf",
                chunk_index=0,
                text="El plazo de treinta días naturales...",
                page=2,
                score=0.92,
            )
        ]

        mock_llm = MagicMock(spec=LLMService)
        mock_llm.build_messages.return_value = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "¿Cuál es el plazo contractual?"},
        ]
        mock_llm.ensure_configured.return_value = None
        mock_llm.generate_response = AsyncMock(
            return_value=(
                "El plazo es de 30 días naturales.",
                [],
            )
        )

        service = ChatService(mock_conversations, mock_rag, mock_llm, settings)
        result = await service.chat(
            conversation_id,
            user_id,
            "¿Cuál es el plazo contractual?",
        )

        mock_conversations.get_conversation.assert_called_once_with(
            conversation_id, user_id
        )
        mock_rag.retrieve_context.assert_called_once_with(case_id, "¿Cuál es el plazo contractual?")
        mock_llm.generate_response.assert_awaited_once()
        assert result.user_message.role == MessageRole.USER
        assert result.assistant_message.role == MessageRole.ASSISTANT
        assert len(result.citations) == 1
        assert result.citations[0].document_id == doc_id

    @pytest.mark.asyncio
    async def test_stream_emits_token_and_done_events(
        self, settings: Settings, conversation_context
    ):
        conversation_id, case_id, user_id, conversation, now = conversation_context
        user_msg_id = uuid4()
        assistant_msg_id = uuid4()

        mock_conversations = MagicMock()
        mock_conversations.get_conversation.return_value = conversation
        mock_conversations.get_recent_messages.return_value = []
        mock_conversations.save_message.side_effect = [
            MessageResponse(
                id=user_msg_id,
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content="Pregunta",
                metadata={},
                created_at=now,
            ),
            MessageResponse(
                id=assistant_msg_id,
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content="Respuesta",
                metadata={"citations": []},
                created_at=now,
            ),
        ]

        mock_rag = MagicMock(spec=RAGService)
        mock_rag.retrieve_context.return_value = []

        async def token_stream(_messages):
            yield "Resp"
            yield "uesta"

        mock_llm = MagicMock(spec=LLMService)
        mock_llm.build_messages.return_value = []
        mock_llm.ensure_configured.return_value = None
        mock_llm.stream_response = token_stream
        mock_llm.parse_citations.return_value = ("Respuesta", [])

        service = ChatService(mock_conversations, mock_rag, mock_llm, settings)
        events = [
            event
            async for event in service.chat_stream(conversation_id, user_id, "Pregunta")
        ]

        assert any("event: token" in event for event in events)
        assert any("event: done" in event for event in events)
        mock_rag.retrieve_context.assert_called_once_with(case_id, "Pregunta")


@pytest.mark.integration
class TestChatFlowWithQdrant:
    """Optional integration against a running Qdrant instance."""

    @pytest.mark.asyncio
    async def test_rag_retrieve_from_qdrant(
        self, settings: Settings, qdrant_available: bool
    ):
        if not qdrant_available:
            pytest.skip("Set QDRANT_INTEGRATION=1 with docker compose up qdrant")

        from qdrant_client import QdrantClient

        from app.pipeline.embeddings import LocalSentenceTransformerProvider
        from app.vector.qdrant import ChunkRecord, ensure_collection, upsert_chunks

        case_id = str(uuid4())
        document_id = str(uuid4())
        collection = f"test_chat_{uuid4().hex[:8]}"
        client = QdrantClient(url=settings.qdrant_url)
        embedder = LocalSentenceTransformerProvider(settings)

        try:
            ensure_collection(client, collection)
            text = "El plazo de resolución es de quince días hábiles."
            vector = embedder.embed([text])[0]
            upsert_chunks(
                client,
                collection,
                [
                    ChunkRecord(
                        case_id=case_id,
                        document_id=document_id,
                        chunk_index=0,
                        text=text,
                        page=1,
                        vector=vector,
                    )
                ],
            )

            from app.vector.qdrant import search_case_chunks

            results = search_case_chunks(
                client,
                collection,
                case_id,
                embedder.embed(["plazo de resolución"])[0],
                top_k=1,
            )
            assert len(results) == 1
            assert "quince días" in results[0].text
        finally:
            if client.collection_exists(collection):
                client.delete_collection(collection)
