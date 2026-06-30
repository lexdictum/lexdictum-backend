"""Postgres full-text search for document chunks."""

from dataclasses import dataclass
from uuid import UUID

from supabase import Client


@dataclass(frozen=True)
class FtsChunk:
    document_id: str
    chunk_index: int
    text: str
    page: int | None
    rank: float


def search_case_chunks_fts(
    client: Client,
    case_id: UUID,
    query: str,
    limit: int,
) -> list[FtsChunk]:
    if not query.strip():
        return []

    response = client.rpc(
        "search_case_chunks_fts",
        {
            "p_case_id": str(case_id),
            "p_query": query,
            "p_limit": limit,
        },
    ).execute()

    results: list[FtsChunk] = []
    for row in response.data or []:
        results.append(
            FtsChunk(
                document_id=str(row["document_id"]),
                chunk_index=int(row["chunk_index"]),
                text=str(row["text"]),
                page=row.get("page"),
                rank=float(row.get("rank") or 0.0),
            )
        )
    return results
