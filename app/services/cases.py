from datetime import UTC, datetime
from uuid import UUID, uuid4

from supabase import Client

from app.core.exceptions import NotFoundError
from app.models.case import CaseCreate, CaseListResponse, CaseResponse, CaseUpdate


class CaseService:
    def __init__(self, client: Client) -> None:
        self._client = client

    def list_cases(self, user_id: UUID) -> CaseListResponse:
        response = (
            self._client.table("cases")
            .select("*", count="exact")
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .execute()
        )
        items = [CaseResponse.model_validate(row) for row in response.data or []]
        return CaseListResponse(items=items, total=response.count or len(items))

    def get_case(self, case_id: UUID, user_id: UUID) -> CaseResponse:
        response = (
            self._client.table("cases")
            .select("*")
            .eq("id", str(case_id))
            .eq("user_id", str(user_id))
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise NotFoundError("Expediente no encontrado")
        return CaseResponse.model_validate(response.data)

    def create_case(self, user_id: UUID, payload: CaseCreate) -> CaseResponse:
        now = datetime.now(UTC).isoformat()
        row = {
            "id": str(uuid4()),
            "user_id": str(user_id),
            "title": payload.title,
            "description": payload.description,
            "status": payload.status.value,
            "metadata": payload.metadata,
            "created_at": now,
            "updated_at": now,
        }
        response = self._client.table("cases").insert(row).select("*").single().execute()
        return CaseResponse.model_validate(response.data)

    def update_case(
        self, case_id: UUID, user_id: UUID, payload: CaseUpdate
    ) -> CaseResponse:
        self.get_case(case_id, user_id)
        updates = payload.model_dump(exclude_unset=True)
        if "status" in updates and updates["status"] is not None:
            updates["status"] = updates["status"].value
        updates["updated_at"] = datetime.now(UTC).isoformat()
        response = (
            self._client.table("cases")
            .update(updates)
            .eq("id", str(case_id))
            .eq("user_id", str(user_id))
            .select("*")
            .single()
            .execute()
        )
        return CaseResponse.model_validate(response.data)

    def delete_case(self, case_id: UUID, user_id: UUID) -> None:
        self.get_case(case_id, user_id)
        self._client.table("cases").delete().eq("id", str(case_id)).eq(
            "user_id", str(user_id)
        ).execute()


def get_case_service(client: Client) -> CaseService:
    return CaseService(client)
