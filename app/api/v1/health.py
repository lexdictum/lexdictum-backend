from fastapi import APIRouter, Response, status

from app.config import get_settings, is_production
from app.services.health_checks import (
    check_qdrant,
    check_redis,
    check_supabase,
    is_critical_check,
)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@router.get("/health/ready")
async def readiness_check(response: Response) -> dict[str, object]:
    settings = get_settings()
    checks = {
        "redis": check_redis(settings),
        "qdrant": check_qdrant(settings),
        "supabase": await check_supabase(settings),
    }

    failed_critical = any(
        is_critical_check(name, result) for name, result in checks.items()
    )
    overall_status = "error" if failed_critical else "ok"

    if failed_critical and is_production(settings):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": overall_status, "checks": checks}
