"""Document processing pipeline worker tasks."""

from arq.worker import Retry

from app.config import get_settings
from app.models.document import DocumentStatus
from app.pipeline.chunker import chunk_text
from app.pipeline.extractors import extract_text
from app.pipeline.indexer import index_document_chunks, remove_document_vectors
from app.services.storage import StorageService
from app.services.supabase import get_supabase_admin
from app.vector.qdrant import ensure_collection, get_qdrant_client


async def process_document(ctx: dict, document_id: str) -> dict[str, str | int]:
    settings = get_settings()
    job_try = ctx.get("job_try", 1)
    max_tries = settings.arq_max_tries
    client = get_supabase_admin()
    qdrant = get_qdrant_client()
    storage = StorageService(client)

    response = (
        client.table("documents")
        .select("*")
        .eq("id", document_id)
        .maybe_single()
        .execute()
    )
    if not response.data:
        return {"status": "not_found", "document_id": document_id}

    document = response.data
    case_id = document["case_id"]
    storage_path = document["storage_path"]
    mime_type = document.get("mime_type")

    client.table("documents").update(
        {"status": DocumentStatus.PROCESSING.value}
    ).eq("id", document_id).execute()

    try:
        remove_document_vectors(qdrant, document_id, settings=settings)
        ensure_collection(qdrant, settings.qdrant_collection)

        content = storage.download(storage_path)
        blocks = extract_text(content, mime_type)
        chunks = chunk_text(blocks, settings=settings)

        if chunks:
            from app.pipeline.embedder import embed_texts

            vectors = embed_texts(
                [chunk.text for chunk in chunks],
                settings=settings,
            )
            index_document_chunks(
                qdrant,
                case_id=case_id,
                document_id=document_id,
                chunks=chunks,
                vectors=vectors,
                settings=settings,
            )

        chunk_count = len(chunks)
        client.table("documents").update(
            {
                "status": DocumentStatus.READY.value,
                "chunk_count": chunk_count,
            }
        ).eq("id", document_id).execute()

        return {
            "status": "ready",
            "document_id": document_id,
            "chunk_count": chunk_count,
        }
    except Exception as exc:
        if job_try >= max_tries:
            client.table("documents").update(
                {"status": DocumentStatus.FAILED.value}
            ).eq("id", document_id).execute()
            raise

        raise Retry(defer=settings.arq_retry_delay_seconds) from exc
