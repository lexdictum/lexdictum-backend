"""Persist document chunks in Postgres for full-text search."""

from app.pipeline.chunker import TextChunk
from supabase import Client


def remove_document_chunks(client: Client, document_id: str) -> None:
    client.table("document_chunks").delete().eq("document_id", document_id).execute()


def persist_document_chunks(
    client: Client,
    *,
    case_id: str,
    document_id: str,
    chunks: list[TextChunk],
) -> None:
    remove_document_chunks(client, document_id)
    if not chunks:
        return

    rows = [
        {
            "case_id": case_id,
            "document_id": document_id,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "page": chunk.page,
        }
        for chunk in chunks
    ]
    client.table("document_chunks").insert(rows).execute()
