from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Response
from pydantic import BaseModel

from app.domains.notifications.dependencies import get_notification_service
from app.domains.users.dependencies import get_current_user
from app.domains.notifications.models import NotificationType
from app.domains.notifications.schemas import (
    LibraryUpdate,
    LunchUpdate,
    NotificationCreate,
    NotificationRead,
    TransitUpdate,
    _LibraryRead,
    _LunchRead,
    _TransitRead,
    read_from_orm,
)
from app.domains.notifications.service import NotificationService
from app.domains.users.models import User

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


_AUTH_401 = {"description": "JWT 누락·만료·서명오류 또는 USER_DELETED"}
_FORBIDDEN_403 = {
    "description": "본인 소유가 아닌 알림 설정에 접근 (NOTIFICATION_FORBIDDEN)",
}
_NOT_FOUND_404 = {
    "description": "지정한 알림 설정이 존재하지 않음 (NOTIFICATION_NOT_FOUND)",
}
_VALIDATION_422 = {"description": "요청 본문 또는 config 스키마 검증 실패"}


@router.get(
    "",
    response_model=list[NotificationRead],
    status_code=200,
    summary="내 알림 목록",
    description=(
        "현재 사용자가 등록한 모든 알림 설정을 반환한다. 응답 배열의 각 항목은 "
        "`type` discriminator 로 TRANSIT / LUNCH / LIBRARY 중 하나의 스키마를 따른다."
    ),
    response_description="사용자가 보유한 모든 알림 설정 배열",
    responses={401: _AUTH_401},
)
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[BaseModel]:
    """현재 사용자의 모든 알림 설정을 반환한다."""
    notifications = await service.list_for_user(current_user.id)
    return [read_from_orm(n) for n in notifications]


@router.post(
    "",
    response_model=NotificationRead,
    status_code=201,
    summary="알림 설정 생성",
    description=(
        "새 알림 설정을 등록한다. 본문은 `type` 으로 분기되는 discriminated union "
        "(`TRANSIT` / `LUNCH` / `LIBRARY`). 동일 type 의 다중 등록을 허용한다 — "
        "예: 출근·퇴근용 교통 알림 2 개. config 스키마는 type 별로 다르며 "
        "Swagger 의 oneOf 로 노출된다."
    ),
    response_description="생성된 알림 설정 (id, timestamps 포함)",
    responses={401: _AUTH_401, 422: _VALIDATION_422},
)
async def create_notification(
    body: Annotated[NotificationCreate, Body(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> BaseModel:
    """새 알림 설정을 생성한다. type별 config 스키마는 Swagger의 oneOf로 노출된다."""
    notification = await service.create_for_user(current_user.id, body)
    return read_from_orm(notification)


@router.get(
    "/transit",
    response_model=list[_TransitRead],
    status_code=200,
    summary="교통 알림 목록만",
    description="F-06 단발 도착·F-07 정기 간격 교통 알림(TRANSIT)만 반환한다.",
    response_description="사용자의 교통 알림 설정 배열",
    responses={401: _AUTH_401},
)
async def list_transit_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[BaseModel]:
    """현재 사용자의 교통 알림 설정만 반환한다."""
    notifications = await service.list_for_user_by_type(
        current_user.id, NotificationType.TRANSIT
    )
    return [read_from_orm(n) for n in notifications]


@router.get(
    "/lunch",
    response_model=list[_LunchRead],
    status_code=200,
    summary="점심 알림 목록만",
    description="F-09~F-12 점심 알림(LUNCH)만 반환한다.",
    response_description="사용자의 점심 알림 설정 배열",
    responses={401: _AUTH_401},
)
async def list_lunch_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[BaseModel]:
    """현재 사용자의 점심 알림 설정만 반환한다."""
    notifications = await service.list_for_user_by_type(
        current_user.id, NotificationType.LUNCH
    )
    return [read_from_orm(n) for n in notifications]


@router.get(
    "/library",
    response_model=list[_LibraryRead],
    status_code=200,
    summary="도서관 알림 목록만",
    description="F-13~F-15 도서관 좌석 알림(LIBRARY)만 반환한다.",
    response_description="사용자의 도서관 알림 설정 배열",
    responses={401: _AUTH_401},
)
async def list_library_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[BaseModel]:
    """현재 사용자의 도서관 알림 설정만 반환한다."""
    notifications = await service.list_for_user_by_type(
        current_user.id, NotificationType.LIBRARY
    )
    return [read_from_orm(n) for n in notifications]


@router.get(
    "/{notification_id}",
    response_model=NotificationRead,
    status_code=200,
    summary="단일 알림 조회",
    description=(
        "지정한 알림 설정 1 건을 반환한다. 본인 소유가 아니면 403, 존재하지 않으면 404."
    ),
    response_description="단일 알림 설정",
    responses={
        401: _AUTH_401,
        403: _FORBIDDEN_403,
        404: _NOT_FOUND_404,
    },
)
async def get_notification(
    notification_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> BaseModel:
    """단일 알림 설정을 반환한다."""
    notification = await service.get_for_user(current_user.id, notification_id)
    return read_from_orm(notification)


@router.patch(
    "/transit/{notification_id}",
    response_model=NotificationRead,
    status_code=200,
    summary="교통 알림 수정",
    description=(
        "교통 알림 설정을 부분 수정한다. `enabled` 만 변경하거나, `config` 를 같이 보내면 "
        "**기존 config 를 통째로 대체** 한다(부분 merge X). type 변경은 지원하지 않는다 — "
        "다른 type 으로 바꾸려면 삭제 후 재생성."
    ),
    response_description="수정된 교통 알림 설정",
    responses={
        401: _AUTH_401,
        403: _FORBIDDEN_403,
        404: _NOT_FOUND_404,
        422: _VALIDATION_422,
    },
)
async def update_transit_notification(
    notification_id: Annotated[int, Path(ge=1)],
    body: TransitUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> BaseModel:
    """교통 알림 설정을 부분 수정한다. config는 전체 교체."""
    notification = await service.update_for_user(
        current_user.id, notification_id, NotificationType.TRANSIT, body
    )
    return read_from_orm(notification)


@router.patch(
    "/lunch/{notification_id}",
    response_model=NotificationRead,
    status_code=200,
    summary="점심 알림 수정",
    description=(
        "점심 알림 설정을 부분 수정한다. `config` 는 전체 교체 (부분 merge X)."
    ),
    response_description="수정된 점심 알림 설정",
    responses={
        401: _AUTH_401,
        403: _FORBIDDEN_403,
        404: _NOT_FOUND_404,
        422: _VALIDATION_422,
    },
)
async def update_lunch_notification(
    notification_id: Annotated[int, Path(ge=1)],
    body: LunchUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> BaseModel:
    """점심 알림 설정을 부분 수정한다. config는 전체 교체."""
    notification = await service.update_for_user(
        current_user.id, notification_id, NotificationType.LUNCH, body
    )
    return read_from_orm(notification)


@router.patch(
    "/library/{notification_id}",
    response_model=NotificationRead,
    status_code=200,
    summary="도서관 알림 수정",
    description=("도서관 알림 설정을 부분 수정한다. `config` 는 전체 교체."),
    response_description="수정된 도서관 알림 설정",
    responses={
        401: _AUTH_401,
        403: _FORBIDDEN_403,
        404: _NOT_FOUND_404,
        422: _VALIDATION_422,
    },
)
async def update_library_notification(
    notification_id: Annotated[int, Path(ge=1)],
    body: LibraryUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> BaseModel:
    """도서관 알림 설정을 부분 수정한다. config는 전체 교체."""
    notification = await service.update_for_user(
        current_user.id, notification_id, NotificationType.LIBRARY, body
    )
    return read_from_orm(notification)


@router.delete(
    "/{notification_id}",
    status_code=204,
    response_class=Response,
    summary="알림 삭제",
    description=(
        "지정한 알림 설정 1 건을 삭제한다. 본인 소유가 아니면 403, 존재하지 않으면 404. "
        "발송 이력(`notification_history`) 도 함께 정리된다 (cascade)."
    ),
    response_description="삭제 완료. 본문 없음",
    responses={
        401: _AUTH_401,
        403: _FORBIDDEN_403,
        404: _NOT_FOUND_404,
    },
)
async def delete_notification(
    notification_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> Response:
    """알림 설정을 삭제한다."""
    await service.delete_for_user(current_user.id, notification_id)
    return Response(status_code=204)
