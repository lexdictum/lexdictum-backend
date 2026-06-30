"""RLS isolation tests.

Unit-level checks verify the user-scoped client pattern.
Integration tests require Supabase local (`SUPABASE_LOCAL=1 supabase start`).
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.cases import CaseService
from app.services.documents import DocumentService
from app.services.profiles import ProfileService
from app.services.supabase import get_supabase_admin, get_supabase_user


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

    Run with: SUPABASE_LOCAL=1 pytest tests/test_rls.py --run-integration
    """

    def test_user_cannot_read_other_users_case(
        self, supabase_local_available, run_integration
    ):
        if not run_integration:
            pytest.skip("Pass --run-integration to execute")
        if not supabase_local_available:
            pytest.skip("Set SUPABASE_LOCAL=1 with supabase start")

        # TODO(Phase 3+): seed two users via Supabase Auth, create case for user A,
        # assert user B's JWT client returns empty / 404 for that case.
        pytest.skip("Requires Supabase Auth seed helpers (Phase 3)")

