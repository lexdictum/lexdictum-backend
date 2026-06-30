import json
from collections.abc import AsyncIterator
from uuid import UUID

from qdrant_client import QdrantClient

from app.config import Settings, get_settings
from app.models.conversation import ChatResponse, Citation, MessageRole
from app.services.conversations import ConversationService, get_conversation_service
from app.services.llm import LLMService, get_llm_service
from app.services.rag import RAGService, get_rag_service
from supabase import Client


class ChatService:
    def __init__(
        self,
        conversation_service: ConversationService,
        rag_service: RAGService,
        llm_service: LLMService,
        settings: Settings | None = None,
    ) -> None:
        self._conversations = conversation_service
        self._rag = rag_service
        self._llm = llm_service
        self._settings = settings or get_settings()

    async def chat(
        self,
        conversation_id: UUID,
        user_id: UUID,
        content: str,
    ) -> ChatResponse:
        conversation = self._conversations.get_conversation(conversation_id, user_id)
        user_message = self._conversations.save_message(
            conversation_id,
            user_id,
            MessageRole.USER,
            content,
        )

        history = self._conversations.get_recent_messages(
            conversation_id,
            user_id,
            self._settings.rag_max_context_messages,
        )
        history = [message for message in history if message.id != user_message.id]

        context_chunks = self._rag.retrieve_context(conversation.case_id, content)
        messages = self._llm.build_messages(
            self._settings.rag_system_prompt,
            history,
            content,
            context_chunks,
        )

        self._llm.ensure_configured()
        assistant_content, citations = await self._llm.generate_response(
            messages, context_chunks
        )
        if not citations and context_chunks:
            citations = self._fallback_citations(context_chunks)

        assistant_message = self._conversations.save_message(
            conversation_id,
            user_id,
            MessageRole.ASSISTANT,
            assistant_content,
            metadata={"citations": [c.model_dump(mode="json") for c in citations]},
        )

        return ChatResponse(
            user_message=user_message,
            assistant_message=assistant_message,
            citations=citations,
        )

    async def chat_stream(
        self,
        conversation_id: UUID,
        user_id: UUID,
        content: str,
    ) -> AsyncIterator[str]:
        conversation = self._conversations.get_conversation(conversation_id, user_id)
        user_message = self._conversations.save_message(
            conversation_id,
            user_id,
            MessageRole.USER,
            content,
        )

        history = self._conversations.get_recent_messages(
            conversation_id,
            user_id,
            self._settings.rag_max_context_messages,
        )
        history = [message for message in history if message.id != user_message.id]

        context_chunks = self._rag.retrieve_context(conversation.case_id, content)
        messages = self._llm.build_messages(
            self._settings.rag_system_prompt,
            history,
            content,
            context_chunks,
        )

        self._llm.ensure_configured()

        yield _sse_event("user_message", {"id": str(user_message.id)})

        full_content = ""
        async for token in self._llm.stream_response(messages):
            full_content += token
            yield _sse_event("token", {"content": token})

        clean_content, citations = self._llm.parse_citations(
            full_content, context_chunks
        )
        if not citations and context_chunks:
            citations = self._fallback_citations(context_chunks)

        for citation in citations:
            yield _sse_event(
                "citation",
                citation.model_dump(mode="json"),
            )

        assistant_message = self._conversations.save_message(
            conversation_id,
            user_id,
            MessageRole.ASSISTANT,
            clean_content,
            metadata={"citations": [c.model_dump(mode="json") for c in citations]},
        )

        yield _sse_event(
            "done",
            {
                "assistant_message_id": str(assistant_message.id),
                "content": clean_content,
            },
        )

    def _fallback_citations(self, context_chunks) -> list[Citation]:
        from uuid import UUID as UUIDType

        citations: list[Citation] = []
        for chunk in context_chunks:
            try:
                document_id = UUIDType(chunk.document_id)
            except ValueError:
                continue
            citations.append(
                Citation(
                    document_id=document_id,
                    filename=chunk.filename,
                    page=chunk.page,
                    chunk_index=chunk.chunk_index,
                    text_snippet=chunk.text[:200],
                )
            )
        return citations


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def get_chat_service(
    client: Client,
    qdrant: QdrantClient,
    settings: Settings | None = None,
) -> ChatService:
    settings = settings or get_settings()
    return ChatService(
        get_conversation_service(client),
        get_rag_service(client, qdrant, settings),
        get_llm_service(settings),
        settings,
    )
