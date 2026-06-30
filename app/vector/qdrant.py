import uuid
from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import Settings, get_settings

DEFAULT_VECTOR_SIZE = 768


@dataclass(frozen=True)
class ChunkRecord:
    case_id: str
    document_id: str
    chunk_index: int
    text: str
    page: int | None
    vector: list[float]


@lru_cache
def get_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    settings = settings or get_settings()
    return QdrantClient(url=settings.qdrant_url)


def chunk_point_id(document_id: str, chunk_index: int) -> str:
    namespace = uuid.UUID(document_id)
    return str(uuid.uuid5(namespace, str(chunk_index)))


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int = DEFAULT_VECTOR_SIZE,
) -> None:
    if client.collection_exists(collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def upsert_chunks(
    client: QdrantClient,
    collection: str,
    chunks: list[ChunkRecord],
) -> None:
    if not chunks:
        return

    points = [
        PointStruct(
            id=chunk_point_id(chunk.document_id, chunk.chunk_index),
            vector=chunk.vector,
            payload={
                "case_id": chunk.case_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "page": chunk.page,
            },
        )
        for chunk in chunks
    ]
    client.upsert(collection_name=collection, points=points)


def delete_document_vectors(
    client: QdrantClient,
    collection: str,
    document_id: str,
) -> None:
    if not client.collection_exists(collection):
        return

    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id),
                )
            ]
        ),
    )


def setup_qdrant(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    try:
        client = get_qdrant_client(settings)
        ensure_collection(client, settings.qdrant_collection)
    except Exception:
        if settings.app_env == "development":
            return
        raise
