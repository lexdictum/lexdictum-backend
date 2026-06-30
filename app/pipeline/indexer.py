from qdrant_client import QdrantClient

from app.config import Settings, get_settings
from app.pipeline.chunker import TextChunk
from app.vector.qdrant import ChunkRecord, delete_document_vectors, upsert_chunks


def index_document_chunks(
    client: QdrantClient,
    *,
    case_id: str,
    document_id: str,
    chunks: list[TextChunk],
    vectors: list[list[float]],
    collection: str | None = None,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    collection_name = collection or settings.qdrant_collection

    records = [
        ChunkRecord(
            case_id=case_id,
            document_id=document_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            page=chunk.page,
            vector=vector,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    upsert_chunks(client, collection_name, records)


def remove_document_vectors(
    client: QdrantClient,
    document_id: str,
    *,
    collection: str | None = None,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    collection_name = collection or settings.qdrant_collection
    delete_document_vectors(client, collection_name, document_id)
