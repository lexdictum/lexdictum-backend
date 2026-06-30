from uuid import UUID

from fastapi import APIRouter, Response, status

from app.dependencies import CaseServiceDep, CurrentUserId
from app.models.case import CaseCreate, CaseListResponse, CaseResponse, CaseUpdate

router = APIRouter()


@router.get("", response_model=CaseListResponse)
async def list_cases(user_id: CurrentUserId, service: CaseServiceDep) -> CaseListResponse:
    return service.list_cases(user_id)


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    user_id: CurrentUserId,
    service: CaseServiceDep,
) -> CaseResponse:
    return service.create_case(user_id, payload)


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    user_id: CurrentUserId,
    service: CaseServiceDep,
) -> CaseResponse:
    return service.get_case(case_id, user_id)


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: UUID,
    payload: CaseUpdate,
    user_id: CurrentUserId,
    service: CaseServiceDep,
) -> CaseResponse:
    return service.update_case(case_id, user_id, payload)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: UUID,
    user_id: CurrentUserId,
    service: CaseServiceDep,
) -> Response:
    service.delete_case(case_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
