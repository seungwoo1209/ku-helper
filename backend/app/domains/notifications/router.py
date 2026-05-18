from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Response

from app.core.security import get_current_user
from app.domains.notifications.dependencies import get_notification_service
from app.domains.notifications.schemas import (
    NotificationCreate,
    NotificationRead,
    NotificationUpdate,
)
from app.domains.notifications.service import NotificationService
from app.domains.users.models import User

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead], status_code=200)
async def list_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[NotificationRead]:
    """현재 사용자의 모든 알림 설정을 반환한다."""
    notifications = await service.list_for_user(current_user.id)
    return [NotificationRead.model_validate(n) for n in notifications]


@router.post("", response_model=NotificationRead, status_code=201)
async def create_notification(
    body: Annotated[NotificationCreate, Body(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationRead:
    """새 알림 설정을 생성한다."""
    notification = await service.create_for_user(current_user.id, body)
    return NotificationRead.model_validate(notification)


@router.get("/{notification_id}", response_model=NotificationRead, status_code=200)
async def get_notification(
    notification_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationRead:
    """단일 알림 설정을 반환한다."""
    notification = await service.get_for_user(current_user.id, notification_id)
    return NotificationRead.model_validate(notification)


@router.patch("/{notification_id}", response_model=NotificationRead, status_code=200)
async def update_notification(
    notification_id: Annotated[int, Path(ge=1)],
    body: NotificationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationRead:
    """알림 설정을 부분 수정한다. config는 전체 교체."""
    notification = await service.update_for_user(current_user.id, notification_id, body)
    return NotificationRead.model_validate(notification)


@router.delete("/{notification_id}", status_code=204, response_class=Response)
async def delete_notification(
    notification_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> Response:
    """알림 설정을 삭제한다."""
    await service.delete_for_user(current_user.id, notification_id)
    return Response(status_code=204)
