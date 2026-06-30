from fastapi import APIRouter

from app.api.v1 import auth, cases, documents, health, profiles

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
router.include_router(cases.router, prefix="/cases", tags=["cases"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
