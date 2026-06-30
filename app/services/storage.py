from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.exceptions import StorageError
from supabase import Client


class StorageService:
    BUCKET = "documents"

    def __init__(self, client: Client) -> None:
        self._client = client

    def build_path(self, user_id: UUID, case_id: UUID, filename: str) -> str:
        return f"{user_id}/{case_id}/{uuid4()}_{filename}"

    async def upload(self, path: str, content: bytes, content_type: str | None) -> str:
        try:
            self._client.storage.from_(self.BUCKET).upload(
                path,
                content,
                file_options={
                    "content-type": content_type or "application/octet-stream",
                    "upsert": "true",
                },
            )
        except Exception as exc:
            raise StorageError(
                f"No se pudo subir el archivo: {exc}"
            ) from exc
        return path

    def get_signed_url(self, path: str, expires_in: int) -> tuple[str, datetime]:
        try:
            response = self._client.storage.from_(self.BUCKET).create_signed_url(
                path, expires_in
            )
        except Exception as exc:
            raise StorageError(
                f"No se pudo generar la URL de descarga: {exc}"
            ) from exc

        url = response.get("signedURL") or response.get("signedUrl")
        if not url:
            raise StorageError("No se pudo generar la URL de descarga")

        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        return url, expires_at

    def download(self, path: str) -> bytes:
        try:
            return self._client.storage.from_(self.BUCKET).download(path)
        except Exception as exc:
            raise StorageError(
                f"No se pudo descargar el archivo: {exc}"
            ) from exc

    def delete(self, path: str) -> None:
        try:
            self._client.storage.from_(self.BUCKET).remove([path])
        except Exception as exc:
            raise StorageError(
                f"No se pudo eliminar el archivo: {exc}"
            ) from exc


def get_storage_service(client: Client) -> StorageService:
    return StorageService(client)
