import json
import re
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import httpx

from app.config import Settings, get_settings
from app.core.exceptions import ServiceUnavailableError
from app.models.conversation import Citation, MessageResponse, MessageRole
from app.services.rag import RetrievedChunk

CITATIONS_PATTERN = re.compile(
    r"<!--CITATIONS:(\[.*?\])-->",
    re.DOTALL,
)


class LLMService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def ensure_configured(self) -> None:
        if not self._settings.llm_api_key:
            raise ServiceUnavailableError(
                "El servicio de IA no está configurado. "
                "Configure LLM_API_KEY para habilitar el asistente jurídico."
            )

    @property
    def _chat_completions_url(self) -> str:
        base = self._settings.llm_base_url
        if base:
            return f"{base.rstrip('/')}/chat/completions"
        return "https://api.openai.com/v1/chat/completions"

    def build_messages(
        self,
        system_prompt: str,
        history: list[MessageResponse],
        user_message: str,
        context_chunks: list[RetrievedChunk],
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        if context_chunks:
            context_lines = ["Fragmentos documentales del expediente:\n"]
            for index, chunk in enumerate(context_chunks, start=1):
                page_label = f"pág. {chunk.page}" if chunk.page is not None else "sin página"
                filename = chunk.filename or chunk.document_id
                context_lines.append(
                    f"[Fuente {index}] documento={filename}, "
                    f"document_id={chunk.document_id}, {page_label}, "
                    f"chunk_index={chunk.chunk_index}:\n{chunk.text}\n"
                )
            messages.append({"role": "system", "content": "\n".join(context_lines)})

        for message in history:
            if message.role == MessageRole.SYSTEM:
                continue
            messages.append(
                {"role": message.role.value, "content": message.content}
            )

        messages.append({"role": "user", "content": user_message})
        return messages

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        context_chunks: list[RetrievedChunk] | None = None,
    ) -> tuple[str, list[Citation]]:
        self.ensure_configured()
        payload = self._build_payload(messages, stream=False)

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self._chat_completions_url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return self.parse_citations(content, context_chunks)

    async def stream_response(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        self.ensure_configured()
        payload = self._build_payload(messages, stream=True)

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                self._chat_completions_url,
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line.removeprefix("data: ").strip()
                    if data_str == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content")
                    if token:
                        yield token

    def parse_citations(
        self,
        content: str,
        context_chunks: list[RetrievedChunk] | None = None,
    ) -> tuple[str, list[Citation]]:
        match = CITATIONS_PATTERN.search(content)
        if not match:
            return content.strip(), []

        clean_content = CITATIONS_PATTERN.sub("", content).strip()
        try:
            raw_citations = json.loads(match.group(1))
        except json.JSONDecodeError:
            return clean_content, []

        chunk_lookup = {}
        if context_chunks:
            chunk_lookup = {
                (chunk.document_id, chunk.chunk_index): chunk
                for chunk in context_chunks
            }

        citations: list[Citation] = []
        for item in raw_citations:
            if not isinstance(item, dict):
                continue
            document_id_str = str(item.get("document_id", ""))
            chunk_index = int(item.get("chunk_index", 0))
            try:
                document_id = UUID(document_id_str)
            except ValueError:
                continue

            chunk = chunk_lookup.get((document_id_str, chunk_index))
            citations.append(
                Citation(
                    document_id=document_id,
                    filename=chunk.filename if chunk else item.get("filename"),
                    page=item.get("page") if item.get("page") is not None else (
                        chunk.page if chunk else None
                    ),
                    chunk_index=chunk_index,
                    text_snippet=str(
                        item.get("text_snippet")
                        or (chunk.text[:200] if chunk else "")
                    ),
                )
            )
        return clean_content, citations

    def _build_payload(
        self, messages: list[dict[str, str]], *, stream: bool
    ) -> dict[str, Any]:
        return {
            "model": self._settings.llm_model,
            "messages": messages,
            "stream": stream,
            "temperature": 0.2,
        }

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.llm_api_key}",
            "Content-Type": "application/json",
        }


def get_llm_service(settings: Settings | None = None) -> LLMService:
    return LLMService(settings)
