from uuid import UUID

from app.core.exceptions import NotFoundError
from app.models.profile import ProfileResponse, ProfileUpdate
from supabase import Client


class ProfileService:
    def __init__(self, client: Client) -> None:
        self._client = client

    def get_profile(self, user_id: UUID) -> ProfileResponse:
        response = (
            self._client.table("profiles")
            .select("*")
            .eq("id", str(user_id))
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise NotFoundError("Perfil no encontrado")
        return ProfileResponse.model_validate(response.data)

    def update_profile(self, user_id: UUID, payload: ProfileUpdate) -> ProfileResponse:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self.get_profile(user_id)
        response = (
            self._client.table("profiles")
            .update(updates)
            .eq("id", str(user_id))
            .select("*")
            .single()
            .execute()
        )
        return ProfileResponse.model_validate(response.data)


def get_profile_service(client: Client) -> ProfileService:
    return ProfileService(client)
