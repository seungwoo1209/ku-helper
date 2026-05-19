import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.domains.immediate_send.models import ImmediateSendRequest
from app.domains.notifications.models import NotificationType
from app.domains.users.models import User, UserStatus
from app.main import app

_PATH = "/api/v1/me/immediate-send/lunch"


@pytest.mark.asyncio
async def test_dispatch_lunch_now_returns_202_and_inserts_row(
    authed_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
) -> None:
    client, user = authed_client
    response = await client.post(_PATH)
    assert response.status_code == 202
    body = response.json()
    assert isinstance(body["request_id"], int)
    assert "requested_at" in body

    result = await db_session.execute(
        select(ImmediateSendRequest).where(
            ImmediateSendRequest.id == body["request_id"]
        )
    )
    row = result.scalar_one()
    assert row.user_id == user.id
    assert row.type == NotificationType.LUNCH
    assert row.payload == {}


@pytest.mark.asyncio
async def test_dispatch_lunch_now_requires_auth(client: AsyncClient) -> None:
    response = await client.post(_PATH)
    # get_current_user 가 토큰 부재 시 401.
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dispatch_lunch_now_blocks_deleted_user(
    client: AsyncClient,
    user_factory,
    db_session: AsyncSession,
) -> None:
    deleted = await user_factory(discord_username="ghost", status=UserStatus.DELETED)
    # authed_client 픽스처는 ACTIVE 만 다루므로 수동 override.
    db_session.expunge(deleted)

    async def _override_get_current_user() -> User:
        from app.domains.users.exceptions import UserDeleted

        raise UserDeleted()

    app.dependency_overrides[get_current_user] = _override_get_current_user
    response = await client.post(_PATH)
    assert response.status_code == 401
    assert response.json()["code"] == "USER_DELETED"
