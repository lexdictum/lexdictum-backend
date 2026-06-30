from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileBase(BaseModel):
    full_name: str | None = None
    firm_name: str | None = None
    bar_number: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    firm_name: str | None = None
    bar_number: str | None = None
    metadata: dict[str, Any] | None = None


class ProfileResponse(ProfileBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserInfo(BaseModel):
    id: UUID
    email: str | None = None
    role: str


class AuthMeResponse(BaseModel):
    user: UserInfo
    profile: ProfileResponse
