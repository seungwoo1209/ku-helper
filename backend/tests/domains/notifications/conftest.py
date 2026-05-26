from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.immediate_send.models import ImmediateSendRequest
from app.domains.notifications.models import (
    Notification,
    NotificationDeliveryStatus,
    NotificationHistory,
    NotificationType,
)

NotificationFactory = Callable[..., Awaitable[Notification]]
ImmediateSendRequestFactory = Callable[..., Awaitable[ImmediateSendRequest]]
NotificationHistoryFactory = Callable[..., Awaitable[NotificationHistory]]


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
                    "mode": "arrival",
                    "station_name": "건대입구",
                    "line": "2",
                    "direction": "내선",
                    "start_time": "08:00:00",
                    "end_time": "10:00:00",
                    "minutes_before": 10,
                    "include_congestion": True,
                },
                NotificationType.LUNCH: {
                    "notify_at": "11:30:00",
                    "recommend_count": 3,
                    "highlight_today_pick": True,
                },
                NotificationType.LIBRARY: {
                    "reading_room_id": 1,
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


@pytest_asyncio.fixture
async def immediate_send_request_factory(
    db_session: AsyncSession,
) -> ImmediateSendRequestFactory:
    async def _create(
        *,
        user_id: int,
        type_: NotificationType = NotificationType.LUNCH,
        payload: dict[str, Any] | None = None,
    ) -> ImmediateSendRequest:
        request = ImmediateSendRequest(
            user_id=user_id,
            type=type_,
            payload=payload if payload is not None else {},
        )
        db_session.add(request)
        await db_session.flush()
        return request

    return _create


@pytest_asyncio.fixture
async def notification_history_factory(
    db_session: AsyncSession,
) -> NotificationHistoryFactory:
    """발송 이력 row 직접 INSERT. 봇이 적재하는 경로를 모방한다 (F-17 회귀 가드용).

    `notification_id` 또는 `immediate_send_request_id` 중 정확히 한쪽만 지정하는 게
    정상 경로. 둘 다 NULL 인 관리자 알림(F-22) 도 명시적으로 만들 수 있다.
    """

    async def _create(
        *,
        user_id: int,
        notification_id: int | None = None,
        immediate_send_request_id: int | None = None,
        sent_at: datetime | None = None,
        status: NotificationDeliveryStatus = NotificationDeliveryStatus.SUCCESS,
        failure_reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> NotificationHistory:
        row = NotificationHistory(
            user_id=user_id,
            notification_id=notification_id,
            immediate_send_request_id=immediate_send_request_id,
            sent_at=sent_at if sent_at is not None else datetime.now(tz=timezone.utc),
            status=status,
            failure_reason=failure_reason,
            payload=payload if payload is not None else {},
        )
        db_session.add(row)
        await db_session.flush()
        return row

    return _create
