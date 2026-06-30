#!/usr/bin/env python3
"""Backfill document_chunks from Qdrant payloads for hybrid search FTS."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.config import get_settings
from app.models.document import DocumentStatus
from app.pipeline.chunk_store import persist_document_chunks
from app.pipeline.chunker import TextChunk
from app.services.supabase import get_supabase_admin
from app.vector.qdrant import get_qdrant_client


@dataclass(frozen=True)
class BackfillStats:
    documents_scanned: int = 0
    documents_backfilled: int = 0
    chunks_inserted: int = 0
    documents_skipped: int = 0


def fetch_ready_documents(client) -> list[dict]:
    response = (
        client.table("documents")
        .select("id, case_id, chunk_count")
        .eq("status", DocumentStatus.READY.value)
        .execute()
    )
    return response.data or []


def fetch_existing_chunk_indices(client, document_id: str) -> set[int]:
    response = (
        client.table("document_chunks")
        .select("chunk_index")
        .eq("document_id", document_id)
        .execute()
    )
    return {int(row["chunk_index"]) for row in response.data or []}


def fetch_qdrant_chunks(
    qdrant: QdrantClient,
    collection: str,
    document_id: str,
) -> list[TextChunk]:
    if not qdrant.collection_exists(collection):
        return []

    chunks: list[TextChunk] = []
    offset = None
    scroll_filter = Filter(
        must=[
            FieldCondition(
                key="document_id",
                match=MatchValue(value=document_id),
            )
        ]
    )

    while True:
        records, offset = qdrant.scroll(
            collection_name=collection,
            scroll_filter=scroll_filter,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in records:
            payload = point.payload or {}
            text = payload.get("text")
            if not text:
                continue
            chunks.append(
                TextChunk(
                    text=str(text),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    page=payload.get("page"),
                )
            )
        if offset is None:
            break

    chunks.sort(key=lambda chunk: chunk.chunk_index)
    return chunks


def backfill_document(
    client,
    qdrant: QdrantClient,
    collection: str,
    document: dict,
    *,
    dry_run: bool,
) -> tuple[int, bool]:
    document_id = str(document["id"])
    case_id = str(document["case_id"])
    existing = fetch_existing_chunk_indices(client, document_id)
    qdrant_chunks = fetch_qdrant_chunks(qdrant, collection, document_id)

    if not qdrant_chunks:
        return 0, False

    missing = [chunk for chunk in qdrant_chunks if chunk.chunk_index not in existing]
    if not missing:
        return 0, False

    if dry_run:
        return len(missing), True

    persist_document_chunks(
        client,
        case_id=case_id,
        document_id=document_id,
        chunks=qdrant_chunks,
    )
    return len(missing), True


def run_backfill(*, dry_run: bool = False) -> BackfillStats:
    settings = get_settings()
    client = get_supabase_admin()
    qdrant = get_qdrant_client(settings)

    documents = fetch_ready_documents(client)

    backfilled = 0
    inserted = 0
    skipped = 0

    for document in documents:
        chunk_count, changed = backfill_document(
            client,
            qdrant,
            settings.qdrant_collection,
            document,
            dry_run=dry_run,
        )
        if changed:
            backfilled += 1
            inserted += chunk_count
        else:
            skipped += 1

    return BackfillStats(
        documents_scanned=len(documents),
        documents_backfilled=backfilled,
        chunks_inserted=inserted,
        documents_skipped=skipped,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill document_chunks from Qdrant for hybrid FTS search."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report missing chunks without writing to Postgres",
    )
    args = parser.parse_args()

    stats = run_backfill(dry_run=args.dry_run)
    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(
        f"[{mode}] documents={stats.documents_scanned} "
        f"backfilled={stats.documents_backfilled} "
        f"chunks={stats.chunks_inserted} "
        f"skipped={stats.documents_skipped}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
