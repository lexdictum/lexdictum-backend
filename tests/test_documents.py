from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, effective_allowed_upload_mime_types, get_settings
from app.core.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError
from app.core.validators import validate_upload_file
from app.dependencies import get_document_service_dep
from app.main import app
from app.models.document import (
    DocumentDownloadResponse,
    DocumentStatus,
    DocumentStatusResponse,
)
from app.services.documents import DocumentService
from app.services.storage import StorageService


@pytest.fixture
def mock_document_service():
    return MagicMock(spec=DocumentService)


@pytest.fixture
def authenticated_client(test_client: TestClient, auth_headers: dict[str, str]):
    return test_client, auth_headers


class TestUploadValidation:
    def test_rejects_oversized_file(self, settings: Settings):
        content = b"x" * (settings.max_upload_size_bytes + 1)
        with pytest.raises(PayloadTooLargeError, match="supera el tamaño máximo"):
            validate_upload_file(
                "informe.pdf",
                content,
                "application/pdf",
                max_size_bytes=settings.max_upload_size_bytes,
            )

    def test_rejects_invalid_mime_and_extension(self, settings: Settings):
        with pytest.raises(UnsupportedMediaTypeError, match="no permitido"):
            validate_upload_file(
                "malware.exe",
                b"content",
                "application/x-msdownload",
                max_size_bytes=settings.max_upload_size_bytes,
            )

    def test_accepts_pdf_by_mime(self, settings: Settings):
        mime = validate_upload_file(
            "contrato.pdf",
            b"%PDF-1.4",
            "application/pdf",
            max_size_bytes=settings.max_upload_size_bytes,
        )
        assert mime == "application/pdf"

    def test_accepts_docx_by_extension_when_mime_generic(self, settings: Settings):
        mime = validate_upload_file(
            "escrito.docx",
            b"PK\x03\x04",
            "application/octet-stream",
            max_size_bytes=settings.max_upload_size_bytes,
        )
        assert (
            mime
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_rejects_png_when_ocr_disabled(self, settings: Settings):
        with pytest.raises(UnsupportedMediaTypeError, match="no permitido"):
            validate_upload_file(
                "prueba.png",
                b"\x89PNG\r\n",
                "image/png",
                max_size_bytes=settings.max_upload_size_bytes,
                allowed_mime_types=effective_allowed_upload_mime_types(settings),
            )

    def test_accepts_png_when_ocr_enabled(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OCR_ENABLED", "true")
        get_settings.cache_clear()
        settings = get_settings()
        mime = validate_upload_file(
            "escaneo.png",
            b"\x89PNG\r\n",
            "image/png",
            max_size_bytes=settings.max_upload_size_bytes,
            allowed_mime_types=effective_allowed_upload_mime_types(settings),
        )
        assert mime == "image/png"
        get_settings.cache_clear()

    def test_rejects_empty_file(self, settings: Settings):
        with pytest.raises(UnsupportedMediaTypeError, match="vacío"):
            validate_upload_file(
                "vacio.pdf",
                b"",
                "application/pdf",
                max_size_bytes=settings.max_upload_size_bytes,
            )

    def test_rejects_path_traversal_filename(self, settings: Settings):
        with pytest.raises(UnsupportedMediaTypeError, match="no válido"):
            validate_upload_file(
                "../../etc/passwd.pdf",
                b"%PDF-1.4",
                "application/pdf",
                max_size_bytes=settings.max_upload_size_bytes,
            )


class TestStorageService:
    def test_get_signed_url(self):
        expires_in = 3600
        signed_at = datetime.now(UTC)
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.create_signed_url.return_value = {
            "signedURL": "https://example.com/signed/doc.pdf?token=abc"
        }
        mock_client.storage.from_.return_value = mock_bucket

        service = StorageService(mock_client)
        url, expires_at = service.get_signed_url("user/case/doc.pdf", expires_in)

        assert url == "https://example.com/signed/doc.pdf?token=abc"
        assert expires_at >= signed_at + timedelta(seconds=expires_in - 1)
        mock_bucket.create_signed_url.assert_called_once_with(
            "user/case/doc.pdf", expires_in
        )

    def test_delete_removes_object(self):
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.storage.from_.return_value = mock_bucket

        service = StorageService(mock_client)
        service.delete("user/case/doc.pdf")

        mock_bucket.remove.assert_called_once_with(["user/case/doc.pdf"])


class TestDocumentServiceDownload:
    def test_get_download_url(self, user_id, settings: Settings):
        document_id = uuid4()
        case_id = uuid4()
        now = datetime.now(UTC)

        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_storage.get_signed_url.return_value = (
            "https://example.com/signed/doc.pdf?token=abc",
            now + timedelta(seconds=settings.signed_url_expires_seconds),
        )
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={
                "id": str(document_id),
                "case_id": str(case_id),
                "user_id": str(user_id),
                "filename": "contrato.pdf",
                "storage_path": f"{user_id}/{case_id}/doc.pdf",
                "mime_type": "application/pdf",
                "status": DocumentStatus.READY.value,
                "chunk_count": 0,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )

        service = DocumentService(mock_client, storage=mock_storage, settings=settings)
        result = service.get_download_url(document_id, user_id)

        assert isinstance(result, DocumentDownloadResponse)
        assert result.url.startswith("https://example.com/signed/")
        mock_storage.get_signed_url.assert_called_once_with(
            f"{user_id}/{case_id}/doc.pdf",
            settings.signed_url_expires_seconds,
        )


class TestDocumentEndpoints:
    def test_upload_rejects_invalid_type(
        self, test_client: TestClient, auth_headers: dict[str, str], settings: Settings
    ):
        response = test_client.post(
            f"/api/v1/documents/case/{uuid4()}/upload",
            headers=auth_headers,
            files={"file": ("virus.exe", b"bad", "application/x-msdownload")},
        )
        assert response.status_code == 415
        assert "no permitido" in response.json()["detail"]

    def test_upload_rejects_oversized_file(
        self, test_client: TestClient, auth_headers: dict[str, str], settings: Settings
    ):
        oversized = b"x" * (settings.max_upload_size_bytes + 1)
        response = test_client.post(
            f"/api/v1/documents/case/{uuid4()}/upload",
            headers=auth_headers,
            files={"file": ("grande.pdf", oversized, "application/pdf")},
        )
        assert response.status_code == 413
        assert "supera el tamaño máximo" in response.json()["detail"]

    def test_download_returns_signed_url(
        self, test_client: TestClient, auth_headers: dict[str, str], mock_document_service
    ):
        document_id = uuid4()
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        mock_document_service.get_download_url.return_value = DocumentDownloadResponse(
            url="https://example.com/signed/doc.pdf?token=abc",
            expires_at=expires_at,
        )

        app.dependency_overrides[get_document_service_dep] = lambda: mock_document_service
        try:
            response = test_client.get(
                f"/api/v1/documents/{document_id}/download",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["url"] == "https://example.com/signed/doc.pdf?token=abc"
        assert "expires_at" in body
        mock_document_service.get_download_url.assert_called_once()

    def test_status_endpoint(
        self, test_client: TestClient, auth_headers: dict[str, str], mock_document_service
    ):
        document_id = uuid4()
        updated_at = datetime.now(UTC)
        mock_document_service.get_document_status.return_value = DocumentStatusResponse(
            id=document_id,
            status=DocumentStatus.PROCESSING,
            chunk_count=0,
            updated_at=updated_at,
        )

        app.dependency_overrides[get_document_service_dep] = lambda: mock_document_service
        try:
            response = test_client.get(
                f"/api/v1/documents/{document_id}/status",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == DocumentStatus.PROCESSING.value
        assert body["id"] == str(document_id)
        mock_document_service.get_document_status.assert_called_once()

    def test_delete_document(
        self, test_client: TestClient, auth_headers: dict[str, str], mock_document_service
    ):
        document_id = uuid4()

        app.dependency_overrides[get_document_service_dep] = lambda: mock_document_service
        try:
            response = test_client.delete(
                f"/api/v1/documents/{document_id}",
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 204
        mock_document_service.delete_document.assert_called_once()

    def test_endpoints_require_auth(self, test_client: TestClient):
        document_id = uuid4()
        assert test_client.get(f"/api/v1/documents/{document_id}/status").status_code == 401
        assert test_client.get(f"/api/v1/documents/{document_id}/download").status_code == 401
        assert test_client.delete(f"/api/v1/documents/{document_id}").status_code == 401
