import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications.models import (
    Notification,
    NotificationDeliveryStatus,
    NotificationHistory,
    NotificationType,
)
from app.domains.users.models import User, UserStatus


@pytest.mark.asyncio
async def test_get_me_returns_current_user(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, user = authed_client
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 200
    assert response.json()["discord_id"] == user.discord_id


@pytest.mark.asyncio
async def test_delete_me_marks_status_deleted(
    authed_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
) -> None:
    """회귀 가드 (c): get_current_user가 detached User를 service에 넘기는
    경로에서도 soft_delete가 status를 DELETED로 영속화해야 한다."""
    client, user = authed_client

    response = await client.delete("/api/v1/users/me")
    assert response.status_code == 204

    stored = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert stored.status == UserStatus.DELETED


@pytest.mark.asyncio
async def test_delete_me_cascades_notifications(
    authed_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
) -> None:
    client, user = authed_client
    db_session.add_all(
        [
            Notification(
                user_id=user.id,
                type=NotificationType.TRANSIT,
                config={
                    "station_name": "건대입구",
                    "line": "2",
                    "include_congestion": True,
                },
            ),
            Notification(
                user_id=user.id,
                type=NotificationType.LUNCH,
                config={"notify_at": "11:30:00", "recommend_count": 3},
            ),
        ]
    )
    await db_session.flush()

    response = await client.delete("/api/v1/users/me")
    assert response.status_code == 204

    remaining = (
        (
            await db_session.execute(
                select(Notification).where(Notification.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_me_cascades_notification_history(
    authed_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
) -> None:
    """탈퇴 시 발송 이력도 물리 삭제되어야 한다. notification_history는
    notification_id ON DELETE SET NULL이라 notifications만 지우면 row가 잔존하므로
    service가 별도 호출로 정리한다."""
    client, user = authed_client

    notification = Notification(
        user_id=user.id,
        type=NotificationType.TRANSIT,
        config={"station_name": "건대입구", "line": "2"},
    )
    db_session.add(notification)
    await db_session.flush()

    db_session.add_all(
        [
            NotificationHistory(
                notification_id=notification.id,
                user_id=user.id,
                status=NotificationDeliveryStatus.SUCCESS,
                payload={"summary": "transit ok"},
            ),
            # notification_id=None인 standalone history (예: 설정이 먼저 삭제된 케이스)
            NotificationHistory(
                notification_id=None,
                user_id=user.id,
                status=NotificationDeliveryStatus.FAILED,
                failure_reason="dm closed",
                payload={"summary": "orphaned"},
            ),
        ]
    )
    await db_session.flush()

    response = await client.delete("/api/v1/users/me")
    assert response.status_code == 204

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(NotificationHistory)
            .where(NotificationHistory.user_id == user.id)
        )
    ).scalar_one()
    assert count == 0
