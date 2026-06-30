import httpx
import redis

from app.config import Settings
from app.vector.qdrant import get_qdrant_client

PLACEHOLDER_SUPABASE_URL = "https://your-project.supabase.co"


def check_redis(settings: Settings) -> dict[str, str]:
    try:
        client = redis.from_url(settings.redis_url)
        client.ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def check_qdrant(settings: Settings) -> dict[str, str]:
    try:
        client = get_qdrant_client(settings)
        client.get_collections()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


async def check_supabase(settings: Settings) -> dict[str, str]:
    if settings.supabase_url.rstrip("/") == PLACEHOLDER_SUPABASE_URL:
        return {"status": "skipped", "message": "Supabase no configurado"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/",
                headers={"apikey": settings.supabase_anon_key},
            )
        if response.status_code < 500:
            return {"status": "ok"}
        return {"status": "error", "message": f"HTTP {response.status_code}"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def is_critical_check(name: str, result: dict[str, str]) -> bool:
    if name == "supabase":
        return False
    return result.get("status") == "error"
