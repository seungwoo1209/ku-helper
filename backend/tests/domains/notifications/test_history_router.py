"""F-17 알림 발송 이력 조회 (`GET /me/notifications/history`) 회귀 가드.

봇이 적재한다고 가정된 `notification_history` row 들을 `notification_history_factory`
로 직접 INSERT 한 뒤 라우터 응답을 검증한다. 정책(타 유저 격리·관리자 row 제외·30일
상한·limit cap·JOIN COALESCE 로 type 도출) 마다 한 건씩 분리.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.domains.notifications.models import (
    NotificationDeliveryStatus,
    NotificationType,
)
from app.domains.users.models import User
from tests.domains.notifications.conftest import (
    ImmediateSendRequestFactory,
    NotificationFactory,
    NotificationHistoryFactory,
)

UserFactory = Callable[..., Awaitable[User]]

_BASE = "/api/v1/me/notifications/history"


@pytest.mark.asyncio
async def test_list_history_empty(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authed_client
    response = await client.get(_BASE)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_history_orders_desc_and_resolves_recurring_type(
    authed_client: tuple[AsyncClient, User],
    notification_factory: NotificationFactory,
    notification_history_factory: NotificationHistoryFactory,
) -> None:
    """정기 알림 3건의 sent_at DESC 정렬 + `Notification.type` 으로 type 도출."""
    client, user = authed_client
    notif = await notification_factory(user_id=user.id, type_=NotificationType.TRANSIT)
    now = datetime.now(tz=timezone.utc)
    for offset in (0, 60, 120):  # minutes
        await notification_history_factory(
            user_id=user.id,
            notification_id=notif.id,
            sent_at=now - timedelta(minutes=offset),
        )

    response = await client.get(_BASE)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    sent_ats = [row["sent_at"] for row in body]
    assert sent_ats == sorted(sent_ats, reverse=True)
    assert {row["type"] for row in body} == {"TRANSIT"}


@pytest.mark.asyncio
async def test_list_history_type_filter_lunch(
    authed_client: tuple[AsyncClient, User],
    notification_factory: NotificationFactory,
    notification_history_factory: NotificationHistoryFactory,
) -> None:
    """`?type=LUNCH` 가 LUNCH 만 반환하는지 (LEFT JOIN COALESCE 검증)."""
    client, user = authed_client
    transit = await notification_factory(
        user_id=user.id, type_=NotificationType.TRANSIT
    )
    lunch = await notification_factory(user_id=user.id, type_=NotificationType.LUNCH)
    library = await notification_factory(
        user_id=user.id, type_=NotificationType.LIBRARY
    )
    for n in (transit, lunch, library):
        await notification_history_factory(user_id=user.id, notification_id=n.id)

    response = await client.get(_BASE, params={"type": "LUNCH"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["type"] == "LUNCH"


@pytest.mark.asyncio
async def test_list_history_status_filter_failed(
    authed_client: tuple[AsyncClient, User],
    notification_factory: NotificationFactory,
    notification_history_factory: NotificationHistoryFactory,
) -> None:
    client, user = authed_client
    notif = await notification_factory(user_id=user.id)
    await notification_history_factory(
        user_id=user.id,
        notification_id=notif.id,
        status=NotificationDeliveryStatus.SUCCESS,
    )
    await notification_history_factory(
        user_id=user.id,
        notification_id=notif.id,
        status=NotificationDeliveryStatus.FAILED,
        failure_reason="Cannot send messages to this user",
    )

    response = await client.get(_BASE, params={"status": "FAILED"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "FAILED"
    assert body[0]["failure_reason"] == "Cannot send messages to this user"


@pytest.mark.asyncio
async def test_list_history_date_range_inclusive_to(
    authed_client: tuple[AsyncClient, User],
    notification_factory: NotificationFactory,
    notification_history_factory: NotificationHistoryFactory,
) -> None:
    """`date_to` 가 inclusive day 인지 — 종료일 23:59 발송 row 가 포함되어야 한다."""
    client, user = authed_client
    notif = await notification_factory(user_id=user.id)
    # 종료일 같은 날 23:30 UTC.
    target = datetime(2026, 5, 20, 23, 30, tzinfo=timezone.utc)
    await notification_history_factory(
        user_id=user.id, notification_id=notif.id, sent_at=target
    )
    # 종료일 다음날 자정 직후 — 포함되면 안 됨.
    just_after = datetime(2026, 5, 21, 0, 0, 5, tzinfo=timezone.utc)
    await notification_history_factory(
        user_id=user.id, notification_id=notif.id, sent_at=just_after
    )

    response = await client.get(
        _BASE,
        params={"date_from": "2026-05-15", "date_to": "2026-05-20"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["sent_at"].startswith("2026-05-20T23:30")


@pytest.mark.asyncio
async def test_list_history_excludes_other_user(
    authed_client: tuple[AsyncClient, User],
    user_factory: UserFactory,
    notification_factory: NotificationFactory,
    notification_history_factory: NotificationHistoryFactory,
) -> None:
    client, me = authed_client
    other = await user_factory(discord_username="other")
    other_notif = await notification_factory(user_id=other.id)
    await notification_history_factory(user_id=other.id, notification_id=other_notif.id)
    # 본인 데이터는 0건이라 응답도 0건이어야 한다 (타 유저 누설 가드).
    response = await client.get(_BASE)
    assert response.status_code == 200
    assert response.json() == []
    assert me.id != other.id


@pytest.mark.asyncio
async def test_list_history_excludes_admin_rows(
    authed_client: tuple[AsyncClient, User],
    notification_history_factory: NotificationHistoryFactory,
) -> None:
    """관리자 알림(F-22) row — 양 FK 가 모두 NULL — 은 응답에서 제외."""
    client, user = authed_client
    await notification_history_factory(
        user_id=user.id,
        notification_id=None,
        immediate_send_request_id=None,
        payload={"admin": True, "reason": "crawler_failure"},
    )
    response = await client.get(_BASE)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_history_immediate_send_type_resolved(
    authed_client: tuple[AsyncClient, User],
    immediate_send_request_factory: ImmediateSendRequestFactory,
    notification_history_factory: NotificationHistoryFactory,
) -> None:
    """`immediate_send_request_id` 만 채워진 row 의 type 이 `ImmediateSendRequest.type`
    에서 도출되는지."""
    client, user = authed_client
    request = await immediate_send_request_factory(
        user_id=user.id, type_=NotificationType.LIBRARY
    )
    await notification_history_factory(
        user_id=user.id,
        immediate_send_request_id=request.id,
        payload={"room_number": 1, "available": 12, "total": 200},
    )

    response = await client.get(_BASE)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["type"] == "LIBRARY"
    assert body[0]["immediate_send_request_id"] == request.id
    assert body[0]["notification_id"] is None


@pytest.mark.asyncio
async def test_list_history_limit_cap_422(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authed_client
    response = await client.get(_BASE, params={"limit": 200})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_history_range_over_30_days_422(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authed_client
    response = await client.get(
        _BASE,
        params={"date_from": "2026-04-25", "date_to": "2026-05-26"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_HISTORY_DATE_RANGE"


@pytest.mark.asyncio
async def test_list_history_inverted_range_422(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authed_client
    response = await client.get(
        _BASE,
        params={"date_from": "2026-05-20", "date_to": "2026-05-10"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_HISTORY_DATE_RANGE"
