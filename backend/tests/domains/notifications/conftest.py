from collections.abc import Awaitable, Callable
from typing import Any

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications.models import Notification, NotificationType

NotificationFactory = Callable[..., Awaitable[Notification]]


@pytest_asyncio.fixture
async def notification_factory(db_session: AsyncSession) -> NotificationFactory:
    async def _create(
        *,
        user_id: int,
        type_: NotificationType = NotificationType.TRANSIT,
        enabled: bool = True,
        config: dict[str, Any] | None = None,
    ) -> Notification:
        if config is None:
            config = {
                NotificationType.TRANSIT: {
                    "station_name": "건대입구",
                    "line": "2",
                    "include_congestion": True,
                },
                NotificationType.LUNCH: {
                    "notify_at": "11:30:00",
                    "recommend_count": 3,
                },
                NotificationType.LIBRARY: {
                    "reading_room_id": "R-101",
                    "threshold": 5,
                },
            }[type_]
        notification = Notification(
            user_id=user_id, type=type_, enabled=enabled, config=config
        )
        db_session.add(notification)
        await db_session.flush()
        return notification

    return _create
