from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, File, Response, UploadFile, status

from app.config import get_settings
from app.dependencies import CurrentUserId, DocumentServiceDep
from app.models.document import (
    DocumentDownloadResponse,
    DocumentListResponse,
    DocumentReprocessResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)

router = APIRouter()


async def _enqueue_document_processing(document_id: UUID) -> None:
    settings = get_settings()
    redis = RedisSettings.from_dsn(settings.redis_url)
    pool = await create_pool(redis)
    await pool.enqueue_job("process_document", str(document_id))
    await pool.close()


@router.get("/case/{case_id}", response_model=DocumentListResponse)
async def list_case_documents(
    case_id: UUID,
    user_id: CurrentUserId,
    service: DocumentServiceDep,
) -> DocumentListResponse:
    return service.list_documents(case_id, user_id)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: UUID,
    user_id: CurrentUserId,
    service: DocumentServiceDep,
) -> DocumentStatusResponse:
    return service.get_document_status(document_id, user_id)


@router.get("/{document_id}/download", response_model=DocumentDownloadResponse)
async def download_document(
    document_id: UUID,
    user_id: CurrentUserId,
    service: DocumentServiceDep,
) -> DocumentDownloadResponse:
    return service.get_download_url(document_id, user_id)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    user_id: CurrentUserId,
    service: DocumentServiceDep,
) -> DocumentResponse:
    return service.get_document(document_id, user_id)


@router.post(
    "/case/{case_id}/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    case_id: UUID,
    user_id: CurrentUserId,
    service: DocumentServiceDep,
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    content = await file.read()
    result = await service.upload_document(
        case_id=case_id,
        user_id=user_id,
        filename=file.filename or "documento",
        content=content,
        mime_type=file.content_type,
    )
    await _enqueue_document_processing(result.document.id)
    return result


@router.post(
    "/{document_id}/reprocess",
    response_model=DocumentReprocessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_document(
    document_id: UUID,
    user_id: CurrentUserId,
    service: DocumentServiceDep,
) -> DocumentReprocessResponse:
    result = service.reprocess_document(document_id, user_id)
    await _enqueue_document_processing(document_id)
    return result


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user_id: CurrentUserId,
    service: DocumentServiceDep,
) -> Response:
    service.delete_document(document_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
