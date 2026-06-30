from functools import lru_cache

from supabase import Client, create_client

from app.config import Settings, get_settings


@lru_cache
def _get_supabase_admin_cached() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_supabase_admin(settings: Settings | None = None) -> Client:
    """Service-role client for workers and system tasks only."""
    if settings is None:
        return _get_supabase_admin_cached()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_supabase_user(access_token: str, settings: Settings | None = None) -> Client:
    """User-scoped client; PostgREST and Storage enforce RLS via the JWT."""
    settings = settings or get_settings()
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(access_token)
    return client


def get_supabase_client(settings: Settings | None = None) -> Client:
    """Deprecated alias for admin client; prefer get_supabase_admin()."""
    return get_supabase_admin(settings)
