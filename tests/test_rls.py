"""RLS isolation tests.

Unit-level checks verify the user-scoped client pattern.
Integration tests require Supabase local (`SUPABASE_LOCAL=1 supabase start`).
"""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from app.core.exceptions import NotFoundError
from app.services.cases import CaseService
from app.services.documents import DocumentService
from app.services.profiles import ProfileService
from app.services.supabase import get_supabase_admin, get_supabase_user
from tests.helpers.supabase_seed import (
    create_case,
    create_test_user,
    delete_test_user,
    user_client,
)


def test_user_client_uses_anon_key_and_sets_auth(settings):
    token = "test-user-jwt"
    with patch("app.services.supabase.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        client = get_supabase_user(token, settings)

        mock_create.assert_called_once_with(
            settings.supabase_url,
            settings.supabase_anon_key,
        )
        mock_client.postgrest.auth.assert_called_once_with(token)
        assert client is mock_client


def test_admin_client_uses_service_role_key(settings):
    with patch("app.services.supabase.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        client = get_supabase_admin(settings)

        mock_create.assert_called_once_with(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        assert client is mock_client


def test_case_service_uses_injected_client():
    mock_client = MagicMock()
    service = CaseService(mock_client)
    assert service._client is mock_client


def test_document_service_uses_injected_client():
    mock_client = MagicMock()
    service = DocumentService(mock_client)
    assert service._client is mock_client


def test_profile_service_uses_injected_client():
    mock_client = MagicMock()
    service = ProfileService(mock_client)
    assert service._client is mock_client


@pytest.mark.integration
class TestRLSIsolation:
    """End-to-end RLS checks against Supabase local.

    Run with: SUPABASE_LOCAL=1 pytest tests/test_rls.py --run-integration -k TestRLSIsolation
    """

    def test_user_cannot_read_other_users_case(
        self,
        supabase_integration_settings,
        supabase_local_available,
    ):
        if not supabase_local_available:
            pytest.skip("Set SUPABASE_LOCAL=1 with supabase start")

        settings = supabase_integration_settings
        user_a = create_test_user(settings)
        user_b = create_test_user(settings)

        try:
            case_id = create_case(settings, user_a, title="Expediente privado A")

            service_b = CaseService(user_client(settings, user_b.access_token))
            with pytest.raises(NotFoundError, match="Expediente no encontrado"):
                service_b.get_case(case_id, user_b.user_id)

            listed = service_b.list_cases(user_b.user_id)
            assert all(item.id != case_id for item in listed.items)
        finally:
            delete_test_user(settings, user_a.user_id)
            delete_test_user(settings, user_b.user_id)

    def test_user_cannot_read_other_users_document_metadata(
        self,
        supabase_integration_settings,
        supabase_local_available,
    ):
        if not supabase_local_available:
            pytest.skip("Set SUPABASE_LOCAL=1 with supabase start")

        settings = supabase_integration_settings
        user_a = create_test_user(settings)
        user_b = create_test_user(settings)

        try:
            case_id = create_case(settings, user_a)
            admin = get_supabase_admin(settings)
            document_id = admin.table("documents").insert(
                {
                    "case_id": str(case_id),
                    "user_id": str(user_a.user_id),
                    "filename": "contrato.pdf",
                    "storage_path": f"{user_a.user_id}/{case_id}/contrato.pdf",
                    "mime_type": "application/pdf",
                    "status": "pending",
                    "chunk_count": 0,
                }
            ).execute().data[0]["id"]

            service_b = DocumentService(user_client(settings, user_b.access_token))
            with pytest.raises(NotFoundError, match="Documento no encontrado"):
                service_b.get_document(UUID(document_id), user_b.user_id)
        finally:
            delete_test_user(settings, user_a.user_id)
            delete_test_user(settings, user_b.user_id)

    def test_user_cannot_update_other_users_profile(
        self,
        supabase_integration_settings,
        supabase_local_available,
    ):
        if not supabase_local_available:
            pytest.skip("Set SUPABASE_LOCAL=1 with supabase start")

        from app.models.profile import ProfileUpdate

        settings = supabase_integration_settings
        user_a = create_test_user(settings)
        user_b = create_test_user(settings)

        try:
            service_b = ProfileService(user_client(settings, user_b.access_token))
            with pytest.raises(NotFoundError, match="Perfil no encontrado"):
                service_b.update_profile(
                    user_a.user_id,
                    ProfileUpdate(full_name="Intruso"),
                )
        finally:
            delete_test_user(settings, user_a.user_id)
            delete_test_user(settings, user_b.user_id)
