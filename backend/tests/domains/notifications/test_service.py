from typing import Any

import pytest

from app.domains.notifications.exceptions import InvalidNotificationConfig
from app.domains.notifications.models import Notification, NotificationType
from app.domains.notifications.schemas import NotificationUpdate
from app.domains.notifications.service import NotificationService


class FakeNotificationRepository:
    """update_for_user의 검증 경로만 다루는 최소 fake."""

    def __init__(self) -> None:
        self._store: dict[int, Notification] = {}

    def seed(self, notification: Notification) -> None:
        self._store[notification.id] = notification

    async def get_by_id(self, notification_id: int) -> Notification | None:
        return self._store.get(notification_id)

    async def update(
        self,
        notification: Notification,
        *,
        enabled: bool | None = None,
        config: dict[str, Any] | None = None,
    ) -> Notification:
        if enabled is not None:
            notification.enabled = enabled
        if config is not None:
            notification.config = config
        return notification


@pytest.mark.asyncio
async def test_update_invalid_config_raises_domain_error() -> None:
    notification = Notification(
        user_id=7,
        type=NotificationType.TRANSIT,
        enabled=True,
        config={"station_name": "건대입구", "line": "2"},
    )
    notification.id = 1
    repo = FakeNotificationRepository()
    repo.seed(notification)
    service = NotificationService(repo)  # type: ignore[arg-type]

    body = NotificationUpdate(config={"notify_at": "11:30:00"})
    with pytest.raises(InvalidNotificationConfig):
        await service.update_for_user(user_id=7, notification_id=1, body=body)
