from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.rag import RAGService, RetrievedChunk
from app.vector.qdrant import ScoredChunk, search_case_chunks


class TestSearchCaseChunks:
    def test_search_applies_case_id_filter(self):
        case_id = str(uuid4())
        document_id = str(uuid4())
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True

        mock_point = MagicMock()
        mock_point.score = 0.95
        mock_point.payload = {
            "case_id": case_id,
            "document_id": document_id,
            "chunk_index": 0,
            "text": "Fragmento legal relevante",
            "page": 5,
        }
        mock_client.search.return_value = [mock_point]

        results = search_case_chunks(
            mock_client,
            "case_document_chunks",
            case_id,
            [0.1] * 768,
            top_k=5,
        )

        assert len(results) == 1
        assert results[0].case_id == case_id
        assert results[0].document_id == document_id
        assert results[0].page == 5

        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["limit"] == 5
        filter_must = call_kwargs["query_filter"].must
        assert filter_must[0].key == "case_id"
        assert filter_must[0].match.value == case_id

    def test_search_returns_empty_when_collection_missing(self):
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False

        results = search_case_chunks(
            mock_client,
            "case_document_chunks",
            str(uuid4()),
            [0.1] * 768,
            top_k=3,
        )

        assert results == []
        mock_client.search.assert_not_called()


class TestRAGService:
    @patch("app.services.rag.embed_texts")
    @patch("app.services.rag.search_case_chunks")
    def test_retrieve_context_maps_filenames(
        self, mock_search, mock_embed, settings
    ):
        case_id = uuid4()
        document_id = str(uuid4())
        mock_embed.return_value = [[0.1] * 768]
        mock_search.return_value = [
            ScoredChunk(
                case_id=str(case_id),
                document_id=document_id,
                chunk_index=1,
                text="Artículo 123 del Código Civil",
                page=10,
                score=0.88,
            )
        ]

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=[{"id": document_id, "filename": "codigo.pdf"}]
        )
        mock_qdrant = MagicMock()

        service = RAGService(mock_client, mock_qdrant, settings)
        chunks = service.retrieve_context(case_id, "¿Qué dice el artículo 123?")

        assert len(chunks) == 1
        assert isinstance(chunks[0], RetrievedChunk)
        assert chunks[0].filename == "codigo.pdf"
        assert chunks[0].text == "Artículo 123 del Código Civil"
        mock_search.assert_called_once()
        mock_embed.assert_called_once()

    @patch("app.services.rag.embed_texts")
    @patch("app.services.rag.search_case_chunks")
    def test_retrieve_context_respects_top_k(
        self, mock_search, mock_embed, settings
    ):
        case_id = uuid4()
        mock_embed.return_value = [[0.1] * 768]
        mock_search.return_value = []

        mock_client = MagicMock()
        mock_qdrant = MagicMock()
        service = RAGService(mock_client, mock_qdrant, settings)

        service.retrieve_context(case_id, "consulta", top_k=3)

        mock_search.assert_called_once()
        assert mock_search.call_args.args[4] == 3
