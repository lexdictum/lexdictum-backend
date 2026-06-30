from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.exceptions import NotFoundError
from app.models.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageListResponse,
    MessageResponse,
    MessageRole,
)
from supabase import Client

DEFAULT_CONVERSATION_TITLE = "Nueva conversación"


class ConversationService:
    def __init__(self, client: Client) -> None:
        self._client = client

    def list_conversations(
        self, case_id: UUID, user_id: UUID
    ) -> ConversationListResponse:
        self._verify_case_access(case_id, user_id)
        response = (
            self._client.table("conversations")
            .select("*", count="exact")
            .eq("case_id", str(case_id))
            .eq("user_id", str(user_id))
            .order("updated_at", desc=True)
            .execute()
        )
        items = [
            ConversationResponse.model_validate(row) for row in response.data or []
        ]
        return ConversationListResponse(items=items, total=response.count or len(items))

    def create_conversation(
        self, case_id: UUID, user_id: UUID, payload: ConversationCreate
    ) -> ConversationResponse:
        self._verify_case_access(case_id, user_id)
        now = datetime.now(UTC).isoformat()
        row = {
            "id": str(uuid4()),
            "case_id": str(case_id),
            "user_id": str(user_id),
            "title": payload.title or DEFAULT_CONVERSATION_TITLE,
            "created_at": now,
            "updated_at": now,
        }
        response = (
            self._client.table("conversations")
            .insert(row)
            .select("*")
            .single()
            .execute()
        )
        return ConversationResponse.model_validate(response.data)

    def get_conversation(
        self, conversation_id: UUID, user_id: UUID
    ) -> ConversationResponse:
        response = (
            self._client.table("conversations")
            .select("*")
            .eq("id", str(conversation_id))
            .eq("user_id", str(user_id))
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise NotFoundError("Conversación no encontrada")
        return ConversationResponse.model_validate(response.data)

    def update_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
        payload: ConversationUpdate,
    ) -> ConversationResponse:
        self.get_conversation(conversation_id, user_id)
        updates = payload.model_dump(exclude_unset=True)
        updates["updated_at"] = datetime.now(UTC).isoformat()
        response = (
            self._client.table("conversations")
            .update(updates)
            .eq("id", str(conversation_id))
            .eq("user_id", str(user_id))
            .select("*")
            .single()
            .execute()
        )
        return ConversationResponse.model_validate(response.data)

    def delete_conversation(self, conversation_id: UUID, user_id: UUID) -> None:
        self.get_conversation(conversation_id, user_id)
        self._client.table("conversations").delete().eq(
            "id", str(conversation_id)
        ).eq("user_id", str(user_id)).execute()

    def list_messages(
        self, conversation_id: UUID, user_id: UUID
    ) -> MessageListResponse:
        self.get_conversation(conversation_id, user_id)
        response = (
            self._client.table("messages")
            .select("*", count="exact")
            .eq("conversation_id", str(conversation_id))
            .order("created_at", desc=False)
            .execute()
        )
        items = [MessageResponse.model_validate(row) for row in response.data or []]
        return MessageListResponse(items=items, total=response.count or len(items))

    def get_recent_messages(
        self,
        conversation_id: UUID,
        user_id: UUID,
        limit: int,
    ) -> list[MessageResponse]:
        self.get_conversation(conversation_id, user_id)
        response = (
            self._client.table("messages")
            .select("*")
            .eq("conversation_id", str(conversation_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = response.data or []
        rows.reverse()
        return [MessageResponse.model_validate(row) for row in rows]

    def save_message(
        self,
        conversation_id: UUID,
        user_id: UUID,
        role: MessageRole,
        content: str,
        metadata: dict | None = None,
    ) -> MessageResponse:
        self.get_conversation(conversation_id, user_id)
        now = datetime.now(UTC).isoformat()
        row = {
            "id": str(uuid4()),
            "conversation_id": str(conversation_id),
            "role": role.value,
            "content": content,
            "metadata": metadata or {},
            "created_at": now,
        }
        response = (
            self._client.table("messages").insert(row).select("*").single().execute()
        )
        self._client.table("conversations").update(
            {"updated_at": datetime.now(UTC).isoformat()}
        ).eq("id", str(conversation_id)).eq("user_id", str(user_id)).execute()
        return MessageResponse.model_validate(response.data)

    def _verify_case_access(self, case_id: UUID, user_id: UUID) -> None:
        response = (
            self._client.table("cases")
            .select("id")
            .eq("id", str(case_id))
            .eq("user_id", str(user_id))
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise NotFoundError("Expediente no encontrado")


def get_conversation_service(client: Client) -> ConversationService:
    return ConversationService(client)
