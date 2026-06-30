from dataclasses import dataclass
from uuid import UUID

from qdrant_client import QdrantClient

from app.config import Settings, get_settings
from app.core.telemetry import trace_span
from app.pipeline.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.search.fts import FtsChunk, search_case_chunks_fts
from app.services.search.hybrid import RankedResult, reciprocal_rank_fusion
from app.vector.qdrant import ScoredChunk, search_case_chunks
from supabase import Client


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: str
    filename: str | None
    chunk_index: int
    text: str
    page: int | None
    score: float


@dataclass(frozen=True)
class _ChunkPayload:
    text: str
    page: int | None


class RAGService:
    def __init__(
        self,
        client: Client,
        qdrant: QdrantClient,
        settings: Settings | None = None,
        embedder: EmbeddingProvider | None = None,
    ) -> None:
        self._client = client
        self._qdrant = qdrant
        self._settings = settings or get_settings()
        self._embedder = embedder or get_embedding_provider(self._settings)

    def retrieve_context(
        self,
        case_id: UUID,
        query: str,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        limit = top_k or self._settings.rag_top_k
        with trace_span(
            "rag.retrieve",
            case_id=str(case_id),
            top_k=limit,
            hybrid=self._settings.rag_use_hybrid_search,
        ):
            if self._settings.rag_use_hybrid_search:
                return self._retrieve_hybrid(case_id, query, limit)
            return self._retrieve_vector_only(case_id, query, limit)

    def _retrieve_vector_only(
        self,
        case_id: UUID,
        query: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        scored = self._search_vectors(case_id, query, limit)
        if not scored:
            return []
        filenames = self._load_document_filenames(scored)
        return [
            RetrievedChunk(
                document_id=chunk.document_id,
                filename=filenames.get(chunk.document_id),
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                page=chunk.page,
                score=chunk.score,
            )
            for chunk in scored
        ]

    def _retrieve_hybrid(
        self,
        case_id: UUID,
        query: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        pool_size = max(limit * 2, limit)
        vector_hits = self._search_vectors(case_id, query, pool_size)
        fts_hits = search_case_chunks_fts(
            self._client, case_id, query, pool_size
        )

        if not vector_hits and not fts_hits:
            return []

        vector_ranked = [
            RankedResult(
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                score=chunk.score,
                source="vector",
            )
            for chunk in vector_hits
        ]
        fts_ranked = [
            RankedResult(
                document_id=chunk.document_id,
                chunk_index=chunk.chunk_index,
                score=chunk.rank,
                source="fts",
            )
            for chunk in fts_hits
        ]

        fused = reciprocal_rank_fusion(
            vector_ranked,
            fts_ranked,
            k=self._settings.rag_rrf_k,
        )[:limit]

        payloads = self._merge_chunk_payloads(vector_hits, fts_hits)
        document_ids = {item.document_id for item in fused}
        filenames = self._load_document_filenames_by_ids(document_ids)

        results: list[RetrievedChunk] = []
        for item in fused:
            key = (item.document_id, item.chunk_index)
            payload = payloads.get(key)
            if payload is None:
                continue
            results.append(
                RetrievedChunk(
                    document_id=item.document_id,
                    filename=filenames.get(item.document_id),
                    chunk_index=item.chunk_index,
                    text=payload.text,
                    page=payload.page,
                    score=item.score,
                )
            )
        return results

    def _search_vectors(
        self,
        case_id: UUID,
        query: str,
        limit: int,
    ) -> list[ScoredChunk]:
        query_vector = self._embedder.embed([query])[0]
        return search_case_chunks(
            self._qdrant,
            self._settings.qdrant_collection,
            str(case_id),
            query_vector,
            limit,
        )

    @staticmethod
    def _merge_chunk_payloads(
        vector_hits: list[ScoredChunk],
        fts_hits: list[FtsChunk],
    ) -> dict[tuple[str, int], _ChunkPayload]:
        payloads: dict[tuple[str, int], _ChunkPayload] = {}
        for chunk in fts_hits:
            key = (chunk.document_id, chunk.chunk_index)
            payloads[key] = _ChunkPayload(text=chunk.text, page=chunk.page)
        for chunk in vector_hits:
            key = (chunk.document_id, chunk.chunk_index)
            payloads[key] = _ChunkPayload(text=chunk.text, page=chunk.page)
        return payloads

    def _load_document_filenames(
        self, chunks: list[ScoredChunk]
    ) -> dict[str, str]:
        document_ids = {chunk.document_id for chunk in chunks if chunk.document_id}
        return self._load_document_filenames_by_ids(document_ids)

    def _load_document_filenames_by_ids(
        self, document_ids: set[str]
    ) -> dict[str, str]:
        if not document_ids:
            return {}

        response = (
            self._client.table("documents")
            .select("id, filename")
            .in_("id", list(document_ids))
            .execute()
        )
        return {
            str(row["id"]): row["filename"]
            for row in response.data or []
            if row.get("filename")
        }


def get_rag_service(
    client: Client,
    qdrant: QdrantClient,
    settings: Settings | None = None,
) -> RAGService:
    return RAGService(client, qdrant, settings)
