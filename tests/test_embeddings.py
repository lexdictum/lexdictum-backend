"""Tests for embedding providers and chunk persistence."""

from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.pipeline.chunk_store import persist_document_chunks, remove_document_chunks
from app.pipeline.chunker import TextChunk
from app.pipeline.embeddings import (
    HttpEmbeddingProvider,
    LocalSentenceTransformerProvider,
    get_embedding_provider,
)


class TestEmbeddingProviders:
    def test_get_embedding_provider_local(self, settings: Settings):
        provider = get_embedding_provider(settings)
        assert isinstance(provider, LocalSentenceTransformerProvider)

    def test_get_embedding_provider_http(self, settings: Settings):
        http_settings = settings.model_copy(
            update={
                "embedding_provider": "http",
                "embedding_service_url": "http://embedder:8080",
            }
        )
        provider = get_embedding_provider(http_settings)
        assert isinstance(provider, HttpEmbeddingProvider)

    def test_get_embedding_provider_rejects_unknown(self, settings: Settings):
        bad_settings = settings.model_copy(update={"embedding_provider": "unknown"})
        with pytest.raises(ValueError, match="no soportado"):
            get_embedding_provider(bad_settings)

    def test_http_provider_requires_service_url(self, settings: Settings):
        http_settings = settings.model_copy(
            update={"embedding_provider": "http", "embedding_service_url": None}
        )
        with pytest.raises(ValueError, match="EMBEDDING_SERVICE_URL"):
            HttpEmbeddingProvider(http_settings)

    def test_http_provider_embed(self, settings: Settings):
        http_settings = settings.model_copy(
            update={
                "embedding_provider": "http",
                "embedding_service_url": "http://embedder:8080",
            }
        )
        provider = HttpEmbeddingProvider(http_settings)

        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response) as mock_post:
            vectors = provider.embed(["uno", "dos"])

        assert vectors == [[0.1, 0.2], [0.3, 0.4]]
        mock_post.assert_called_once_with(
            "http://embedder:8080/embed",
            json={"texts": ["uno", "dos"]},
            timeout=60.0,
        )

    def test_http_provider_empty_texts(self, settings: Settings):
        http_settings = settings.model_copy(
            update={
                "embedding_provider": "http",
                "embedding_service_url": "http://embedder:8080",
            }
        )
        provider = HttpEmbeddingProvider(http_settings)
        assert provider.embed([]) == []

    def test_http_provider_invalid_response(self, settings: Settings):
        http_settings = settings.model_copy(
            update={
                "embedding_provider": "http",
                "embedding_service_url": "http://embedder:8080",
            }
        )
        provider = HttpEmbeddingProvider(http_settings)

        mock_response = MagicMock()
        mock_response.json.return_value = {"vectors": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response):
            with pytest.raises(ValueError, match="inválida"):
                provider.embed(["uno"])

    def test_local_provider_delegates_to_embed_texts(self, settings: Settings):
        provider = LocalSentenceTransformerProvider(settings)
        with patch(
            "app.pipeline.embedder.embed_texts",
            return_value=[[0.5] * 768],
        ) as mock_embed:
            vectors = provider.embed(["texto legal"])

        assert vectors == [[0.5] * 768]
        mock_embed.assert_called_once_with(["texto legal"], settings=settings)


class TestChunkStore:
    def test_remove_document_chunks(self):
        client = MagicMock()
        remove_document_chunks(client, "doc-123")
        client.table.assert_called_with("document_chunks")
        client.table.return_value.delete.return_value.eq.assert_called_with(
            "document_id", "doc-123"
        )

    def test_persist_document_chunks_inserts_rows(self):
        client = MagicMock()
        chunks = [
            TextChunk(text="Fragmento uno", chunk_index=0, page=1),
            TextChunk(text="Fragmento dos", chunk_index=1, page=2),
        ]

        persist_document_chunks(
            client,
            case_id="case-1",
            document_id="doc-1",
            chunks=chunks,
        )

        client.table.return_value.delete.return_value.eq.assert_called_with(
            "document_id", "doc-1"
        )
        inserted = client.table.return_value.insert.call_args.args[0]
        assert len(inserted) == 2
        assert inserted[0]["chunk_index"] == 0
        assert inserted[1]["text"] == "Fragmento dos"

    def test_persist_document_chunks_skips_insert_when_empty(self):
        client = MagicMock()
        persist_document_chunks(
            client,
            case_id="case-1",
            document_id="doc-1",
            chunks=[],
        )
        client.table.return_value.insert.assert_not_called()
