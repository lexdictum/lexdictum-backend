from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentResponse(BaseModel):
    id: UUID
    case_id: UUID
    user_id: UUID
    filename: str
    storage_path: str
    mime_type: str | None = None
    status: DocumentStatus
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    message: str = Field(default="Documento recibido. Procesamiento en cola.")


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


class DocumentStatusResponse(BaseModel):
    id: UUID
    status: DocumentStatus
    chunk_count: int = 0
    updated_at: datetime


class DocumentDownloadResponse(BaseModel):
    url: str
    expires_at: datetime


class DocumentReprocessResponse(BaseModel):
    document: DocumentResponse
    message: str = Field(default="Documento en cola para reprocesamiento.")
