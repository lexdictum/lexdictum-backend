from fastapi import APIRouter

from app.dependencies import CurrentUserId, ProfileServiceDep
from app.models.profile import ProfileResponse, ProfileUpdate

router = APIRouter()


@router.get("/me", response_model=ProfileResponse)
async def get_own_profile(
    user_id: CurrentUserId,
    service: ProfileServiceDep,
) -> ProfileResponse:
    return service.get_profile(user_id)


@router.patch("/me", response_model=ProfileResponse)
async def update_own_profile(
    payload: ProfileUpdate,
    user_id: CurrentUserId,
    service: ProfileServiceDep,
) -> ProfileResponse:
    return service.update_profile(user_id, payload)
