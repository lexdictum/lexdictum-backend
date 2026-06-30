from datetime import UTC, datetime
from uuid import UUID, uuid4

from qdrant_client import QdrantClient

from app.config import Settings, effective_allowed_upload_mime_types, get_settings
from app.core.exceptions import NotFoundError, StorageError
from app.core.validators import validate_upload_file
from app.models.document import (
    DocumentDownloadResponse,
    DocumentListResponse,
    DocumentReprocessResponse,
    DocumentResponse,
    DocumentStatus,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.pipeline.chunk_store import remove_document_chunks
from app.pipeline.indexer import remove_document_vectors
from app.services.storage import StorageService, get_storage_service
from app.vector.qdrant import get_qdrant_client
from supabase import Client


class DocumentService:
    def __init__(
        self,
        client: Client,
        storage: StorageService | None = None,
        settings: Settings | None = None,
        qdrant: QdrantClient | None = None,
    ) -> None:
        self._client = client
        self._storage = storage or get_storage_service(client)
        self._settings = settings or get_settings()
        self._qdrant = qdrant or get_qdrant_client()

    def list_documents(self, case_id: UUID, user_id: UUID) -> DocumentListResponse:
        response = (
            self._client.table("documents")
            .select("*", count="exact")
            .eq("case_id", str(case_id))
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .execute()
        )
        items = [DocumentResponse.model_validate(row) for row in response.data or []]
        return DocumentListResponse(items=items, total=response.count or len(items))

    def get_document(self, document_id: UUID, user_id: UUID) -> DocumentResponse:
        response = (
            self._client.table("documents")
            .select("*")
            .eq("id", str(document_id))
            .eq("user_id", str(user_id))
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise NotFoundError("Documento no encontrado")
        return DocumentResponse.model_validate(response.data)

    def get_document_status(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentStatusResponse:
        document = self.get_document(document_id, user_id)
        return DocumentStatusResponse(
            id=document.id,
            status=document.status,
            chunk_count=document.chunk_count,
            updated_at=document.updated_at,
        )

    def get_download_url(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentDownloadResponse:
        document = self.get_document(document_id, user_id)
        expires_in = self._settings.signed_url_expires_seconds
        url, expires_at = self._storage.get_signed_url(
            document.storage_path, expires_in
        )
        return DocumentDownloadResponse(url=url, expires_at=expires_at)

    def update_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        *,
        chunk_count: int | None = None,
    ) -> None:
        updates: dict[str, object] = {
            "status": status.value,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if chunk_count is not None:
            updates["chunk_count"] = chunk_count
        self._client.table("documents").update(updates).eq(
            "id", str(document_id)
        ).execute()

    async def upload_document(
        self,
        case_id: UUID,
        user_id: UUID,
        filename: str,
        content: bytes,
        mime_type: str | None,
    ) -> DocumentUploadResponse:
        allowed_mimes = effective_allowed_upload_mime_types(self._settings)
        resolved_mime = validate_upload_file(
            filename,
            content,
            mime_type,
            max_size_bytes=self._settings.max_upload_size_bytes,
            allowed_mime_types=allowed_mimes,
        )

        storage_path = self._storage.build_path(user_id, case_id, filename)
        try:
            await self._storage.upload(storage_path, content, resolved_mime)
        except StorageError:
            raise

        now = datetime.now(UTC).isoformat()
        row = {
            "id": str(uuid4()),
            "case_id": str(case_id),
            "user_id": str(user_id),
            "filename": filename,
            "storage_path": storage_path,
            "mime_type": resolved_mime,
            "status": DocumentStatus.PENDING.value,
            "chunk_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        try:
            response = (
                self._client.table("documents")
                .insert(row)
                .select("*")
                .single()
                .execute()
            )
        except Exception:
            try:
                self._storage.delete(storage_path)
            except StorageError:
                pass
            raise

        document = DocumentResponse.model_validate(response.data)
        return DocumentUploadResponse(document=document)

    def reprocess_document(
        self, document_id: UUID, user_id: UUID
    ) -> DocumentReprocessResponse:
        document = self.get_document(document_id, user_id)
        remove_document_vectors(
            self._qdrant,
            str(document.id),
            settings=self._settings,
        )
        remove_document_chunks(self._client, str(document.id))
        now = datetime.now(UTC).isoformat()
        response = (
            self._client.table("documents")
            .update(
                {
                    "status": DocumentStatus.PENDING.value,
                    "chunk_count": 0,
                    "updated_at": now,
                }
            )
            .eq("id", str(document_id))
            .eq("user_id", str(user_id))
            .select("*")
            .single()
            .execute()
        )
        updated = DocumentResponse.model_validate(response.data)
        return DocumentReprocessResponse(document=updated)

    def delete_document(self, document_id: UUID, user_id: UUID) -> None:
        document = self.get_document(document_id, user_id)
        remove_document_vectors(
            self._qdrant,
            str(document.id),
            settings=self._settings,
        )
        remove_document_chunks(self._client, str(document.id))
        try:
            self._storage.delete(document.storage_path)
        except StorageError:
            pass
        self._client.table("documents").delete().eq("id", str(document_id)).eq(
            "user_id", str(user_id)
        ).execute()


def get_document_service(client: Client) -> DocumentService:
    return DocumentService(client)
