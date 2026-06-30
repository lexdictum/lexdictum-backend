from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Header
from qdrant_client import QdrantClient
from supabase import Client

from app.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_supabase_jwt
from app.services.cases import CaseService, get_case_service
from app.services.chat import ChatService, get_chat_service
from app.services.conversations import ConversationService, get_conversation_service
from app.services.documents import DocumentService, get_document_service
from app.services.profiles import ProfileService, get_profile_service
from app.services.supabase import get_supabase_user
from app.vector.qdrant import get_qdrant_client


async def get_bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Se requiere token de autenticación")
    return authorization.removeprefix("Bearer ").strip()


BearerToken = Annotated[str, Depends(get_bearer_token)]


async def get_current_user(
    token: BearerToken,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return decode_supabase_jwt(token, settings)


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


async def get_current_user_id(user: CurrentUser) -> UUID:
    return UUID(user["id"])


CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]


async def get_supabase_user_client(
    token: BearerToken,
    settings: Settings = Depends(get_settings),
) -> Client:
    return get_supabase_user(token, settings)


SupabaseUserClient = Annotated[Client, Depends(get_supabase_user_client)]


def _get_qdrant_client_dep() -> QdrantClient:
    return get_qdrant_client()


async def get_case_service_dep(client: SupabaseUserClient) -> CaseService:
    return get_case_service(client)


async def get_document_service_dep(client: SupabaseUserClient) -> DocumentService:
    return get_document_service(client)


async def get_profile_service_dep(client: SupabaseUserClient) -> ProfileService:
    return get_profile_service(client)


async def get_conversation_service_dep(
    client: SupabaseUserClient,
) -> ConversationService:
    return get_conversation_service(client)


QdrantDep = Annotated[QdrantClient, Depends(_get_qdrant_client_dep)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_chat_service_dep(
    client: SupabaseUserClient,
    qdrant: QdrantDep,
) -> ChatService:
    return get_chat_service(client, qdrant, get_settings())


CaseServiceDep = Annotated[CaseService, Depends(get_case_service_dep)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service_dep)]
ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service_dep)]
ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service_dep)
]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service_dep)]
