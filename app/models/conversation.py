from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Citation(BaseModel):
    document_id: UUID
    filename: str | None = None
    page: int | None = None
    chunk_index: int
    text_snippet: str


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)


class ConversationResponse(BaseModel):
    id: UUID
    case_id: UUID
    user_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int


class ChatRequest(BaseModel):
    content: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    citations: list[Citation] = Field(default_factory=list)
