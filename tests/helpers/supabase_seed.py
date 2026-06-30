"""Helpers for Supabase local integration tests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from uuid import UUID

from app.config import Settings
from app.models.case import CaseCreate
from app.services.cases import CaseService
from app.services.supabase import get_supabase_admin, get_supabase_user
from supabase import Client, create_client


@dataclass(frozen=True)
class SeededUser:
    user_id: UUID
    email: str
    password: str
    access_token: str


def create_test_user(
    settings: Settings,
    *,
    email: str | None = None,
    password: str = "integration-test-password",
) -> SeededUser:
    """Create a confirmed Supabase Auth user and return a signed-in session."""
    admin = get_supabase_admin(settings)
    address = email or f"test-{uuid.uuid4().hex[:12]}@lexdictum.local"

    response = admin.auth.admin.create_user(
        {
            "email": address,
            "password": password,
            "email_confirm": True,
        }
    )
    user_id = UUID(response.user.id)

    anon = create_client(settings.supabase_url, settings.supabase_anon_key)
    session = anon.auth.sign_in_with_password(
        {"email": address, "password": password}
    )
    token = session.session.access_token

    return SeededUser(
        user_id=user_id,
        email=address,
        password=password,
        access_token=token,
    )


def delete_test_user(settings: Settings, user_id: UUID) -> None:
    admin = get_supabase_admin(settings)
    admin.auth.admin.delete_user(str(user_id))


def user_client(settings: Settings, access_token: str) -> Client:
    return get_supabase_user(access_token, settings)


def create_case(
    settings: Settings,
    user: SeededUser,
    *,
    title: str = "Expediente de prueba",
) -> UUID:
    service = CaseService(user_client(settings, user.access_token))
    case = service.create_case(user.user_id, CaseCreate(title=title))
    return case.id
