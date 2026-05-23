import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.immediate_send.models import ImmediateSendRequest
from app.domains.users.dependencies import get_current_user
from app.domains.notifications.models import NotificationType
from app.domains.users.models import User, UserStatus
from app.main import app

_PATH = "/api/v1/me/immediate-send/lunch"
_TRANSIT_PATH = "/api/v1/me/immediate-send/transit"
_TRANSIT_BODY = {"station_name": "강남", "line": "2호선"}
_LIBRARY_PATH = "/api/v1/me/immediate-send/library"
_LIBRARY_BODY = {"reading_room_id": 1}


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
    await user_factory(discord_username="ghost", status=UserStatus.DELETED)

    async def _override_get_current_user() -> User:
        from app.domains.users.exceptions import UserDeleted

        raise UserDeleted()

    app.dependency_overrides[get_current_user] = _override_get_current_user
    response = await client.post(_PATH)
    assert response.status_code == 401
    assert response.json()["code"] == "USER_DELETED"


@pytest.mark.asyncio
async def test_dispatch_transit_now_returns_202_and_inserts_row(
    authed_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
) -> None:
    client, user = authed_client
    response = await client.post(_TRANSIT_PATH, json=_TRANSIT_BODY)
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
    assert row.type == NotificationType.TRANSIT
    assert row.payload == {"station_name": "강남", "line": "2호선"}


@pytest.mark.asyncio
async def test_dispatch_transit_now_requires_auth(client: AsyncClient) -> None:
    response = await client.post(_TRANSIT_PATH, json=_TRANSIT_BODY)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dispatch_transit_now_blocks_deleted_user(
    client: AsyncClient,
    user_factory,
    db_session: AsyncSession,
) -> None:
    await user_factory(discord_username="ghost2", status=UserStatus.DELETED)

    async def _override_get_current_user() -> User:
        from app.domains.users.exceptions import UserDeleted

        raise UserDeleted()

    app.dependency_overrides[get_current_user] = _override_get_current_user
    response = await client.post(_TRANSIT_PATH, json=_TRANSIT_BODY)
    assert response.status_code == 401
    assert response.json()["code"] == "USER_DELETED"


@pytest.mark.asyncio
async def test_dispatch_transit_now_rejects_empty_station(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authed_client
    response = await client.post(
        _TRANSIT_PATH, json={"station_name": "", "line": "2호선"}
    )
    # Pydantic min_length=1 위반 → 422.
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_dispatch_library_now_returns_202_and_inserts_row(
    authed_client: tuple[AsyncClient, User],
    db_session: AsyncSession,
) -> None:
    client, user = authed_client
    response = await client.post(_LIBRARY_PATH, json=_LIBRARY_BODY)
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
    assert row.type == NotificationType.LIBRARY
    assert row.payload == {"reading_room_id": 1}


@pytest.mark.asyncio
async def test_dispatch_library_now_requires_auth(client: AsyncClient) -> None:
    response = await client.post(_LIBRARY_PATH, json=_LIBRARY_BODY)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dispatch_library_now_blocks_deleted_user(
    client: AsyncClient,
    user_factory,
    db_session: AsyncSession,
) -> None:
    await user_factory(discord_username="ghost3", status=UserStatus.DELETED)

    async def _override_get_current_user() -> User:
        from app.domains.users.exceptions import UserDeleted

        raise UserDeleted()

    app.dependency_overrides[get_current_user] = _override_get_current_user
    response = await client.post(_LIBRARY_PATH, json=_LIBRARY_BODY)
    assert response.status_code == 401
    assert response.json()["code"] == "USER_DELETED"


@pytest.mark.asyncio
async def test_dispatch_library_now_rejects_invalid_room(
    authed_client: tuple[AsyncClient, User],
) -> None:
    client, _ = authed_client
    # 제4열람실은 미운영이라 Literal[0,1,2,3,5] 위반 → 422.
    response = await client.post(_LIBRARY_PATH, json={"reading_room_id": 4})
    assert response.status_code == 422
