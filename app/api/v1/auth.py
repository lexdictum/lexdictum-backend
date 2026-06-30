from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUser, ProfileServiceDep
from app.models.profile import AuthMeResponse, ProfileResponse, ProfileUpdate, UserInfo

router = APIRouter()


@router.get("/me", response_model=AuthMeResponse)
async def get_me(
    user: CurrentUser,
    profile_service: ProfileServiceDep,
) -> AuthMeResponse:
    user_id = UUID(user["id"])
    profile = profile_service.get_profile(user_id)
    return AuthMeResponse(
        user=UserInfo(
            id=user_id,
            email=user.get("email"),
            role=user["role"],
        ),
        profile=profile,
    )
