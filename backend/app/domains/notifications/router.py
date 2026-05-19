from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Response
from pydantic import BaseModel

from app.core.security import get_current_user
from app.domains.notifications.dependencies import get_notification_service
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


@router.get("", response_model=list[NotificationRead], status_code=200)
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[BaseModel]:
    """현재 사용자의 모든 알림 설정을 반환한다."""
    notifications = await service.list_for_user(current_user.id)
    return [read_from_orm(n) for n in notifications]


@router.post("", response_model=NotificationRead, status_code=201)
async def create_notification(
    body: Annotated[NotificationCreate, Body(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> BaseModel:
    """새 알림 설정을 생성한다. type별 config 스키마는 Swagger의 oneOf로 노출된다."""
    notification = await service.create_for_user(current_user.id, body)
    return read_from_orm(notification)


@router.get("/transit", response_model=list[_TransitRead], status_code=200)
async def list_transit_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[BaseModel]:
    """현재 사용자의 교통 알림 설정만 반환한다."""
    notifications = await service.list_for_user_by_type(
        current_user.id, NotificationType.TRANSIT
    )
    return [read_from_orm(n) for n in notifications]


@router.get("/lunch", response_model=list[_LunchRead], status_code=200)
async def list_lunch_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[BaseModel]:
    """현재 사용자의 점심 알림 설정만 반환한다."""
    notifications = await service.list_for_user_by_type(
        current_user.id, NotificationType.LUNCH
    )
    return [read_from_orm(n) for n in notifications]


@router.get("/library", response_model=list[_LibraryRead], status_code=200)
async def list_library_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[BaseModel]:
    """현재 사용자의 도서관 알림 설정만 반환한다."""
    notifications = await service.list_for_user_by_type(
        current_user.id, NotificationType.LIBRARY
    )
    return [read_from_orm(n) for n in notifications]


@router.get("/{notification_id}", response_model=NotificationRead, status_code=200)
async def get_notification(
    notification_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> BaseModel:
    """단일 알림 설정을 반환한다."""
    notification = await service.get_for_user(current_user.id, notification_id)
    return read_from_orm(notification)


@router.patch(
    "/transit/{notification_id}", response_model=NotificationRead, status_code=200
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
    "/lunch/{notification_id}", response_model=NotificationRead, status_code=200
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
    "/library/{notification_id}", response_model=NotificationRead, status_code=200
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


@router.delete("/{notification_id}", status_code=204, response_class=Response)
async def delete_notification(
    notification_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> Response:
    """알림 설정을 삭제한다."""
    await service.delete_for_user(current_user.id, notification_id)
    return Response(status_code=204)
