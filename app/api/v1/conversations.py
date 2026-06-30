from uuid import UUID

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import StreamingResponse

from app.core.rate_limit import RateLimitInfo
from app.dependencies import (
    ChatRateLimitDep,
    ChatServiceDep,
    ConversationServiceDep,
    CurrentUserId,
)
from app.models.conversation import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageListResponse,
)

router = APIRouter()
case_router = APIRouter()


def _rate_limit_headers(request: Request) -> dict[str, str]:
    info: RateLimitInfo | None = getattr(request.state, "rate_limit", None)
    if info is None:
        return {}
    return {
        "X-RateLimit-Limit": str(info.limit),
        "X-RateLimit-Remaining": str(info.remaining),
        "X-RateLimit-Reset": str(info.reset),
    }


@case_router.get("/{case_id}/conversations", response_model=ConversationListResponse)
async def list_case_conversations(
    case_id: UUID,
    user_id: CurrentUserId,
    service: ConversationServiceDep,
) -> ConversationListResponse:
    return service.list_conversations(case_id, user_id)


@case_router.post(
    "/{case_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    case_id: UUID,
    payload: ConversationCreate,
    user_id: CurrentUserId,
    service: ConversationServiceDep,
) -> ConversationResponse:
    return service.create_conversation(case_id, user_id, payload)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    user_id: CurrentUserId,
    service: ConversationServiceDep,
) -> ConversationResponse:
    return service.get_conversation(conversation_id, user_id)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    user_id: CurrentUserId,
    service: ConversationServiceDep,
) -> ConversationResponse:
    return service.update_conversation(conversation_id, user_id, payload)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    user_id: CurrentUserId,
    service: ConversationServiceDep,
) -> Response:
    service.delete_conversation(conversation_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: UUID,
    user_id: CurrentUserId,
    service: ConversationServiceDep,
) -> MessageListResponse:
    return service.list_messages(conversation_id, user_id)


@router.post("/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: UUID,
    payload: ChatRequest,
    request: Request,
    user_id: CurrentUserId,
    chat_service: ChatServiceDep,
    _: ChatRateLimitDep,
) -> StreamingResponse:
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        **_rate_limit_headers(request),
    }
    return StreamingResponse(
        chat_service.chat_stream(conversation_id, user_id, payload.content),
        media_type="text/event-stream",
        headers=headers,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: UUID,
    payload: ChatRequest,
    request: Request,
    response: Response,
    user_id: CurrentUserId,
    chat_service: ChatServiceDep,
    _: ChatRateLimitDep,
) -> ChatResponse:
    for key, value in _rate_limit_headers(request).items():
        response.headers[key] = value
    return await chat_service.chat(conversation_id, user_id, payload.content)
