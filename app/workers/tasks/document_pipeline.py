"""Document processing pipeline worker tasks."""

from arq.worker import Retry

from app.config import get_settings
from app.core.telemetry import init_telemetry, trace_span
from app.models.document import DocumentStatus
from app.pipeline.chunk_store import persist_document_chunks, remove_document_chunks
from app.pipeline.chunker import chunk_text
from app.pipeline.embeddings import get_embedding_provider
from app.pipeline.extractors import extract_text
from app.pipeline.indexer import index_document_chunks, remove_document_vectors
from app.services.storage import StorageService
from app.services.supabase import get_supabase_admin
from app.vector.qdrant import ensure_collection, get_qdrant_client


async def process_document(ctx: dict, document_id: str) -> dict[str, str | int]:
    settings = get_settings()
    init_telemetry(settings)
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
        remove_document_chunks(client, document_id)
        ensure_collection(qdrant, settings.qdrant_collection)

        content = storage.download(storage_path)
        with trace_span("worker.extract_text", document_id=document_id):
            blocks = extract_text(
                content,
                mime_type,
                ocr_enabled=settings.ocr_enabled,
                tesseract_lang=settings.tesseract_lang,
            )
        chunks = chunk_text(blocks, settings=settings)

        if chunks:
            embedder = get_embedding_provider(settings)
            with trace_span("worker.embed", document_id=document_id, chunks=len(chunks)):
                vectors = embedder.embed([chunk.text for chunk in chunks])
            index_document_chunks(
                qdrant,
                case_id=case_id,
                document_id=document_id,
                chunks=chunks,
                vectors=vectors,
                settings=settings,
            )
            persist_document_chunks(
                client,
                case_id=case_id,
                document_id=document_id,
                chunks=chunks,
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
