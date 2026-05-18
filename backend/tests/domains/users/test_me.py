import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications.models import (
    Notification,
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
