from dataclasses import dataclass
from uuid import UUID

from qdrant_client import QdrantClient
from supabase import Client

from app.config import Settings, get_settings
from app.pipeline.embedder import embed_texts
from app.vector.qdrant import ScoredChunk, search_case_chunks


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: str
    filename: str | None
    chunk_index: int
    text: str
    page: int | None
    score: float


class RAGService:
    def __init__(
        self,
        client: Client,
        qdrant: QdrantClient,
        settings: Settings | None = None,
    ) -> None:
        self._client = client
        self._qdrant = qdrant
        self._settings = settings or get_settings()

    def retrieve_context(
        self,
        case_id: UUID,
        query: str,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        limit = top_k or self._settings.rag_top_k
        query_vector = embed_texts([query], settings=self._settings)[0]
        scored = search_case_chunks(
            self._qdrant,
            self._settings.qdrant_collection,
            str(case_id),
            query_vector,
            limit,
        )
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

    def _load_document_filenames(
        self, chunks: list[ScoredChunk]
    ) -> dict[str, str]:
        document_ids = list({chunk.document_id for chunk in chunks if chunk.document_id})
        if not document_ids:
            return {}

        response = (
            self._client.table("documents")
            .select("id, filename")
            .in_("id", document_ids)
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
