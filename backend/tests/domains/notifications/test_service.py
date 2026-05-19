from datetime import time
from typing import Any

import pytest

from app.domains.notifications.exceptions import NotificationNotFound
from app.domains.notifications.models import Notification, NotificationType
from app.domains.notifications.schemas import LunchConfig, LunchUpdate, TransitUpdate
from app.domains.notifications.service import NotificationService


class FakeNotificationRepository:
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
async def test_update_with_wrong_type_endpoint_masks_as_not_found() -> None:
    """LUNCH 알림을 transit 엔드포인트로 갱신 시도하면 type 불일치 → 404 마스킹."""
    notification = Notification(
        user_id=7,
        type=NotificationType.LUNCH,
        enabled=True,
        config={"notify_at": "11:30:00"},
    )
    notification.id = 1
    repo = FakeNotificationRepository()
    repo.seed(notification)
    service = NotificationService(repo)  # type: ignore[arg-type]

    body = TransitUpdate(enabled=False)
    with pytest.raises(NotificationNotFound):
        await service.update_for_user(
            user_id=7,
            notification_id=1,
            expected_type=NotificationType.TRANSIT,
            body=body,
        )


@pytest.mark.asyncio
async def test_update_lunch_config_normalized_to_json() -> None:
    """LunchConfig의 time 값이 JSONB에 안전한 문자열로 dump되는지 확인."""
    notification = Notification(
        user_id=7,
        type=NotificationType.LUNCH,
        enabled=True,
        config={"notify_at": "11:30:00"},
    )
    notification.id = 1
    repo = FakeNotificationRepository()
    repo.seed(notification)
    service = NotificationService(repo)  # type: ignore[arg-type]

    body = LunchUpdate(config=LunchConfig(notify_at=time(12, 0)))
    result = await service.update_for_user(
        user_id=7,
        notification_id=1,
        expected_type=NotificationType.LUNCH,
        body=body,
    )
    assert result.config["notify_at"] == "12:00:00"
