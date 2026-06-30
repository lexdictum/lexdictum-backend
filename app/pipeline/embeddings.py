"""Embedding provider abstraction.

LocalSentenceTransformerProvider loads the model in-process (arq workers).
HttpEmbeddingProvider calls a dedicated embedder microservice.
"""

from typing import Literal, Protocol

import httpx

from app.config import Settings, get_settings

EmbeddingProviderKind = Literal["local", "http"]


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalSentenceTransformerProvider:
    """In-process sentence-transformers backend (current default)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def embed(self, texts: list[str]) -> list[list[float]]:
        from app.pipeline.embedder import embed_texts

        return embed_texts(texts, settings=self._settings)


class HttpEmbeddingProvider:
    """Remote embedding service (POST {url}/embed with {"texts": [...]})."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.embedding_service_url:
            raise ValueError(
                "EMBEDDING_SERVICE_URL es obligatorio cuando embedding_provider=http"
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        base_url = self._settings.embedding_service_url.rstrip("/")
        response = httpx.post(
            f"{base_url}/embed",
            json={"texts": texts},
            timeout=60.0,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise ValueError("Respuesta del servicio de embeddings inválida")
        return embeddings


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    provider = settings.embedding_provider.lower()
    if provider == "http":
        return HttpEmbeddingProvider(settings)
    if provider != "local":
        raise ValueError(f"Proveedor de embeddings no soportado: {provider}")
    return LocalSentenceTransformerProvider(settings)
